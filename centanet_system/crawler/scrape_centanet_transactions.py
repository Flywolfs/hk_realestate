#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中原地产屋苑交易记录爬取脚本
通过API获取香港屋苑的销售和租赁记录
"""

import requests
import json
import time
import sys
import os
import urllib3
import ssl
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

# 禁用SSL警告（用于解决SSL连接问题）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TooManyRequestsError(Exception):
    """当API返回429 Too Many Requests错误时抛出此异常"""
    pass


class TLSAdapter(HTTPAdapter):
    """自定义TLS适配器以解决SSL连接问题"""
    
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # 设置TLS选项
        ctx.options |= ssl.OP_NO_SSLv2
        ctx.options |= ssl.OP_NO_SSLv3
        ctx.options |= ssl.OP_NO_COMPRESSION
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


class CentanetTransactionScraper:
    """中原地产交易记录爬虫"""
    
    # API端点
    API_URL = "https://hk.centanet.com/findproperty/api/Transaction/Search"
    
    # 记录类型
    POST_TYPE_SALE = "Sale"
    POST_TYPE_RENT = "Rent"
    
    # 时间范围（3年）
    DAY_RANGE = "Day1095"
    
    # 每页最大数据量
    MAX_PAGE_SIZE = 100
    
    # API分页上限：offset + size 不得超过此值（实测验证，超过返回空）
    MAX_OFFSET_LIMIT = 10000
    
    # 双向爬取交界冗余条数：API对同一天内的记录排序不稳定（实测），
    # 升序补抓时多抓此条数以确保与降序流在日期上有重叠，避免交界处缺漏
    PAGE_OVERLAP_BUFFER = 1000
    
    def __init__(
        self, 
        request_interval: float = 1.0, 
        max_retries: int = 3,
        estate_info_path: str = None,
        output_dir: str = None,
        workers: int = 5,
        skip_existing_files: bool = False,
        skip_finished_file: str = None,
        earliest_date: str = None,
        history_dir: str = None,
        skip_empty_file: str = None,
        all_history: bool = False
    ):
        """
        初始化爬虫
        
        Args:
            request_interval: 请求间隔时间（秒），默认1.0秒
            max_retries: 最大重试次数，默认3次
            estate_info_path: 屋苑信息JSON文件路径
            output_dir: 输出目录，默认为当前目录下的transaction_record_[日期]
            workers: 并发线程数，默认5
            skip_existing_files: 是否跳过已存在记录文件的屋苑
            skip_finished_file: 已完成屋苑ID记录文件路径
            earliest_date: 最早日期字符串（格式 'YYYY-MM-DD'），用于过滤交易记录
            history_dir: 历史记录目录（上一次爬取的输出目录），用于增量更新
            skip_empty_file: 空屋苑记录文件路径，跳过其中记录的无记录屋苑
            all_history: 是否爬取全部历史成交记录。实测API在day=Day1095时仅返回近3年数据，
                        不传day参数则返回全部历史（可追溯到1995年），超过10000条的屋苑
                        自动双向爬取（降序取最新+升序取最老）后按ID去重
        """
        self.session = requests.Session()
        self.request_interval = request_interval
        self.max_retries = max_retries
        self.workers = workers
        self.skip_existing_files = skip_existing_files
        self.skip_finished_file = skip_finished_file
        self.earliest_date = earliest_date
        self.history_dir = history_dir
        self.skip_empty_file = skip_empty_file
        self.all_history = all_history
        
        # 空屋苑ID集合（从 skip_empty_file 加载）
        self._empty_estate_ids: set = set()
        if skip_empty_file:
            self._empty_estate_ids = self._load_empty_estate_ids(skip_empty_file)
        
        # 空屋苑记录文件路径（固定路径，运行时追加写入）
        self._empty_estate_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'empty_estate.txt'
        )
        
        # 线程锁，用于保护共享资源
        self._lock = threading.Lock()
        self._progress_lock = threading.Lock()
        self._file_lock = threading.Lock()  # 用于进度文件写入
        
        # 停止标志（当遇到Too Many Requests时设置为True）
        self._stop_flag = threading.Event()
        
        # 线程本地存储，每个线程独立的session
        self._thread_local = threading.local()
        
        # 使用自定义TLS适配器解决SSL问题
        self.session.mount('https://', TLSAdapter())
        
        # 设置请求头，模拟浏览器
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-HK,zh-TW;q=0.9,zh;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://hk.centanet.com',
            'Referer': 'https://hk.centanet.com/findproperty/',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Connection': 'keep-alive'
        })
        
        # 统计信息（必须在加载屋苑信息之前初始化）
        self.stats = {
            'total_estates': 0,
            'processed_estates': 0,
            'sale_records': 0,
            'rent_records': 0,
            'failed_estates': [],
            'start_time': None,
            'end_time': None
        }
        
        # 加载屋苑信息
        self.estates: List[Dict[str, Any]] = []
        if estate_info_path:
            self.load_estate_info(estate_info_path)
        
        # 设置输出目录
        if output_dir:
            self.output_base_dir = output_dir
        else:
            today = datetime.now().strftime('%Y%m%d')
            self.output_base_dir = f"transaction_record_{today}"
        
        # 进度记录文件（在爬取开始时创建）
        self.progress_file = None
        
        # 已跳过的屋苑统计
        self.stats['skipped_estates'] = 0
    
    def _load_empty_estate_ids(self, file_path: str) -> set:
        """
        从空屋苑记录文件加载屋苑ID集合
        
        Args:
            file_path: 空屋苑记录文件路径
            
        Returns:
            屋苑ID集合
        """
        ids = set()
        if not os.path.exists(file_path):
            print(f"⚠ 空屋苑记录文件不存在: {file_path}")
            return ids
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ids.add(line)
            print(f"✓ 从空屋苑记录文件加载了 {len(ids)} 个屋苑ID: {file_path}")
        except Exception as e:
            print(f"✗ 读取空屋苑记录文件失败: {e}")
        return ids
    
    def _record_empty_estate(self, type_code: str):
        """
        将无记录的屋苑ID追加写入 empty_estate.txt（线程安全）
        
        Args:
            type_code: 屋苑ID
        """
        with self._file_lock:
            with open(self._empty_estate_file, 'a', encoding='utf-8') as f:
                f.write(f"{type_code}\n")
    
    def _init_progress_file(self):
        """初始化进度记录文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.progress_file = os.path.join(
            self.output_base_dir, 
            f"finish_crawling_{timestamp}.txt"
        )
        # 确保目录存在
        os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
        print(f"✓ 进度文件已创建: {self.progress_file}")
    
    def _record_finished_estate(self, type_code: str):
        """
        记录已完成的屋苑ID到进度文件（线程安全）
        
        Args:
            type_code: 屋苑ID
        """
        with self._file_lock:
            with open(self.progress_file, 'a', encoding='utf-8') as f:
                f.write(f"{type_code}\n")
    
    def get_finished_estates_from_files(self) -> set:
        """
        从输出目录中已存在的JSON文件提取已完成的屋苑ID
        
        Returns:
            已完成屋苑ID集合
        """
        finished = set()
        
        # 检查 sale 目录
        sale_dir = os.path.join(self.output_base_dir, 'sale')
        if os.path.exists(sale_dir):
            for filename in os.listdir(sale_dir):
                if filename.endswith('.json'):
                    type_code = filename[:-5]  # 移除 .json 后缀
                    finished.add(type_code)
        
        # 检查 rent 目录
        rent_dir = os.path.join(self.output_base_dir, 'rent')
        if os.path.exists(rent_dir):
            for filename in os.listdir(rent_dir):
                if filename.endswith('.json'):
                    type_code = filename[:-5]  # 移除 .json 后缀
                    finished.add(type_code)
        
        return finished
    
    def get_finished_estates_from_progress_file(self, progress_file_path: str) -> set:
        """
        从进度记录文件中读取已完成的屋苑ID
        
        Args:
            progress_file_path: 进度文件路径
            
        Returns:
            已完成屋苑ID集合
        """
        finished = set()
        
        if not os.path.exists(progress_file_path):
            print(f"⚠ 进度文件不存在: {progress_file_path}")
            return finished
        
        try:
            with open(progress_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释行和空行
                    if line and not line.startswith('#'):
                        finished.add(line)
            print(f"✓ 从进度文件加载了 {len(finished)} 个已完成屋苑ID")
        except Exception as e:
            print(f"✗ 读取进度文件失败: {e}")
        
        return finished
    
    def filter_estates(self, estates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        过滤已完成的屋苑
        
        Args:
            estates: 原始屋苑列表
            
        Returns:
            过滤后的屋苑列表
        """
        finished_ids = set()
        
        # 方式一：从已存在的文件中提取
        if self.skip_existing_files:
            file_finished = self.get_finished_estates_from_files()
            finished_ids.update(file_finished)
            print(f"  从已存在文件中找到 {len(file_finished)} 个已完成屋苑")
        
        # 方式二：从进度文件中读取
        if self.skip_finished_file:
            progress_finished = self.get_finished_estates_from_progress_file(self.skip_finished_file)
            finished_ids.update(progress_finished)
        
        # 过滤
        if finished_ids:
            filtered = [e for e in estates if e.get('typeCode') not in finished_ids]
            skipped = len(estates) - len(filtered)
            self.stats['skipped_estates'] = skipped
            print(f"  跳过 {skipped} 个已完成的屋苑，剩余 {len(filtered)} 个待处理")
            return filtered
        
        return estates
    
    def load_history_records(
        self, 
        estate_type_code: str,
        post_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        从历史目录中加载指定屋苑的历史记录
        
        Args:
            estate_type_code: 屋苑ID
            post_type: 记录类型 ("Sale" 或 "Rent")
            
        Returns:
            历史记录字典（来自历史JSON文件的原始结构），不存在则返回None
        """
        if not self.history_dir:
            return None
        
        sub_dir = "sale" if post_type == self.POST_TYPE_SALE else "rent"
        history_file = os.path.join(self.history_dir, sub_dir, f"{estate_type_code}.json")
        
        if not os.path.exists(history_file):
            return None
        
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self._print_safe(f"    ⚠ 加载历史记录失败 ({estate_type_code}/{sub_dir}): {e}")
            return None
    
    def _get_session(self) -> requests.Session:
        """
        获取当前线程的Session对象
        每个线程使用独立的Session以保证线程安全
        
        Returns:
            当前线程的Session对象
        """
        if not hasattr(self._thread_local, 'session'):
            # 为当前线程创建新的Session
            session = requests.Session()
            session.mount('https://', TLSAdapter())
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-HK,zh-TW;q=0.9,zh;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Content-Type': 'application/json;charset=UTF-8',
                'Origin': 'https://hk.centanet.com',
                'Referer': 'https://hk.centanet.com/findproperty/',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Connection': 'keep-alive'
            })
            self._thread_local.session = session
        return self._thread_local.session
    
    def load_estate_info(self, estate_info_path: str):
        """
        加载屋苑信息文件
        
        Args:
            estate_info_path: 屋苑信息JSON文件路径
        """
        print(f"正在加载屋苑信息: {estate_info_path}")
        
        try:
            with open(estate_info_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'data' in data and isinstance(data['data'], list):
                self.estates = data['data']
                self.stats['total_estates'] = len(self.estates)
                print(f"✓ 成功加载 {len(self.estates)} 个屋苑信息")
            else:
                raise ValueError("屋苑信息文件格式不正确，缺少 'data' 字段")
                
        except FileNotFoundError:
            raise FileNotFoundError(f"屋苑信息文件不存在: {estate_info_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"屋苑信息文件JSON解析失败: {e}")
    
    def fetch_transactions(
        self, 
        estate_type_code: str, 
        post_type: str,
        offset: int = 0,
        size: int = 100,
        order: str = "Descending"
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定屋苑的交易记录
        
        Args:
            estate_type_code: 屋苑ID（typeCode）
            post_type: 记录类型 ("Sale" 或 "Rent")
            offset: 分页偏移量
            size: 每页数据量
            order: 排序方向 ("Descending" 最新在前 或 "Ascending" 最老在前)
            
        Returns:
            API响应数据，失败返回None
        """
        payload = {
            "postType": post_type,
            "sort": "InsOrRegDate",
            "order": order,
            "size": size,
            "offset": offset,
            "pageSource": "search",
            "bigestAndEstate": [estate_type_code],
            "bigPhotoMode": False,
            "hmas": [],
            "mtrs": [],
            "primarySchoolNets": [],
            "markets": [],
            "universities": [],
            "phaseAndEstate": []
        }
        
        # 全量历史模式不传 day 参数（实测：day=Day1095 仅返回近3年，不传则返回全部历史）
        if not self.all_history:
            payload["day"] = self.DAY_RANGE
        
        for attempt in range(self.max_retries):
            try:
                response = self._get_session().post(
                    self.API_URL,
                    json=payload,
                    timeout=30,
                    verify=False  # 禁用SSL验证以解决连接问题
                )
                response.raise_for_status()
                
                data = response.json()
                return data
                
            except requests.exceptions.RequestException as e:
                error_str = str(e)
                # 检测 429 Too Many Requests 错误
                if "Too Many Requests" in error_str or "429" in error_str:
                    self._stop_flag.set()
                    raise TooManyRequestsError(
                        f"API返回429 Too Many Requests错误，爬取已停止。错误信息: {e}"
                    )
                
                if attempt < self.max_retries - 1:
                    wait_time = self.request_interval * (attempt + 1) * 2
                    self._print_safe(f"    ⚠ 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    self._print_safe(f"    等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    self._print_safe(f"    ✗ 请求失败，已达最大重试次数: {e}")
                    return None
                    
            except json.JSONDecodeError as e:
                self._print_safe(f"    ✗ JSON解析失败: {e}")
                return None
                
        return None
    
    def _parse_date(self, date_str: str) -> Optional[Any]:
        """
        解析日期字符串，返回可比较的日期对象
        
        Args:
            date_str: 日期字符串（格式可能是 'YYYY-MM-DD' 或 'YYYY-MM-DDTHH:MM:SS'）
            
        Returns:
            date对象，解析失败返回None
        """
        if not date_str:
            return None
        try:
            # 尝试解析 ISO 格式 (YYYY-MM-DDTHH:MM:SS)
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            # 尝试解析简单格式 (YYYY-MM-DD)
            return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None
    
    def _fetch_pages(
        self,
        estate_type_code: str,
        post_type: str,
        total_count: int,
        order: str,
        max_records: int = None
    ) -> List[Dict[str, Any]]:
        """
        按指定排序方向分页抓取交易记录
        
        Args:
            estate_type_code: 屋苑ID（typeCode）
            post_type: 记录类型 ("Sale" 或 "Rent")
            total_count: 总记录数
            order: 排序方向 ("Ascending" 或 "Descending")
            max_records: 最多抓取条数，默认抓取全部（不超过API分页上限）
            
        Returns:
            抓取到的记录列表
        """
        records = []
        limit = total_count
        if max_records is not None:
            limit = min(total_count, max_records)
        # API限制 offset + size <= MAX_OFFSET_LIMIT
        limit = min(limit, self.MAX_OFFSET_LIMIT)
        total_pages = (limit + self.MAX_PAGE_SIZE - 1) // self.MAX_PAGE_SIZE
        
        for page in range(total_pages):
            if page > 0:
                time.sleep(self.request_interval)
            response = self.fetch_transactions(
                estate_type_code=estate_type_code,
                post_type=post_type,
                offset=page * self.MAX_PAGE_SIZE,
                size=self.MAX_PAGE_SIZE,
                order=order
            )
            if response and 'data' in response and isinstance(response['data'], list):
                page_records = response['data']
                records.extend(page_records)
                self._print_safe(f"    {order} 第 {page + 1}/{total_pages} 页: +{len(page_records)} 条 (累计 {len(records)})")
            else:
                self._print_safe(f"    ⚠ 获取第 {page + 1}/{total_pages} 页数据失败，停止分页")
                break
        return records
    
    def _merge_dedup(
        self,
        desc_records: List[Dict[str, Any]],
        asc_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        合并降序与升序记录并按记录ID去重
        
        Args:
            desc_records: 降序（最新→最老）记录
            asc_records: 升序（最老→最新）记录
            
        Returns:
            去重合并后的记录列表
        """
        seen = set()
        merged = []
        for record in list(desc_records) + list(asc_records):
            record_id = record.get('id')
            if record_id:
                if record_id in seen:
                    continue
                seen.add(record_id)
            merged.append(record)
        return merged
    
    def _fetch_full_history(
        self,
        estate: Dict[str, Any],
        post_type: str,
        earliest_date: str = None
    ) -> List[Dict[str, Any]]:
        """
        爬取屋苑全部历史成交记录（全量历史模式）
        
        实测API行为：
        1. 不传 day 参数时返回全部历史记录（day=Day1095 仅返回近3年）
        2. 分页限制 offset + size <= 10000，单方向最多取10000条
        3. 超过10000条的屋苑需双向爬取（降序取最新10000条 + 升序取最老部分）再按ID去重
        
        Args:
            estate: 屋苑信息字典
            post_type: 记录类型 ("Sale" 或 "Rent")
            earliest_date: 可选最早日期过滤（格式 'YYYY-MM-DD'）
            
        Returns:
            完整历史记录列表
        """
        estate_type_code = estate.get('typeCode', '')
        estate_name = estate.get('estateName', '未知屋苑')
        type_name = self._get_post_type_name(post_type)
        
        first_response = self.fetch_transactions(
            estate_type_code=estate_type_code,
            post_type=post_type,
            offset=0,
            size=self.MAX_PAGE_SIZE
        )
        
        if not first_response:
            self._print_safe(f"    ✗ 获取 {estate_name} 的{type_name}记录失败")
            return []
        
        total_count = first_response.get('count', 0)
        
        if total_count == 0:
            self._record_empty_estate(estate_type_code)
            self._print_safe(f"    ℹ {estate_name} ({estate_type_code}) {type_name}无记录，已写入 empty_estate.txt")
            return []
        
        self._print_safe(f"    {type_name}记录: 共 {total_count} 条 (全量历史模式)")
        
        # 降序：从最新记录开始，最多取 MAX_OFFSET_LIMIT 条
        desc_records = self._fetch_pages(
            estate_type_code=estate_type_code,
            post_type=post_type,
            total_count=total_count,
            order="Descending",
            max_records=self.MAX_OFFSET_LIMIT
        )
        
        # 超过分页上限时，升序补抓最老的部分（含冗余重叠，防止同日排序抖动导致缺漏）
        asc_records = []
        if total_count > self.MAX_OFFSET_LIMIT:
            oldest_count = total_count - self.MAX_OFFSET_LIMIT
            asc_total = oldest_count + self.PAGE_OVERLAP_BUFFER
            self._print_safe(f"    {type_name}记录超过API分页上限({self.MAX_OFFSET_LIMIT}条)，"
                             f"升序补抓最老的 {asc_total} 条 (含{self.PAGE_OVERLAP_BUFFER}条冗余)")
            asc_records = self._fetch_pages(
                estate_type_code=estate_type_code,
                post_type=post_type,
                total_count=asc_total,
                order="Ascending"
            )
            if len(asc_records) < asc_total:
                self._print_safe(f"    ⚠ 升序补抓不完整({len(asc_records)}/{asc_total})，"
                                 f"中间部分记录可能缺失")
        
        # 超过双向爬取可覆盖范围(2*MAX_OFFSET_LIMIT)的超级屋苑，中间部分无法获取
        if total_count > 2 * self.MAX_OFFSET_LIMIT:
            missing = total_count - 2 * self.MAX_OFFSET_LIMIT
            self._print_safe(f"    ⚠ {type_name}记录多达 {total_count} 条，超过双向爬取覆盖范围，"
                             f"中间约 {missing} 条记录无法获取（建议按期数 phaseAndEstate 拆分爬取）")
        
        records = self._merge_dedup(desc_records, asc_records)
        
        # 完整性检查：合并后数量与API总数对比
        if len(records) < total_count:
            missing = total_count - len(records)
            self._print_safe(f"    ⚠ 合并后 {len(records)} 条，与API总数 {total_count} 条相差 {missing} 条"
                             f"（可能因同日记录排序抖动缺漏或API计数含重复）")
        
        # 最早日期过滤（全量爬取后统一过滤）
        if earliest_date:
            earliest_date_obj = self._parse_date(earliest_date)
            if earliest_date_obj:
                filtered = []
                for record in records:
                    record_date_str = record.get('insDate')
                    record_date = self._parse_date(record_date_str) if record_date_str else None
                    if record_date and record_date >= earliest_date_obj:
                        filtered.append(record)
                skipped = len(records) - len(filtered)
                records = filtered
                self._print_safe(f"    最早日期过滤 {earliest_date}: 保留 {len(records)} 条, 过滤 {skipped} 条")
        
        self._print_safe(f"    ✓ {type_name}记录: {len(records)} 条 (全量)")
        return records
    
    def fetch_all_transactions_for_estate(
        self, 
        estate: Dict[str, Any],
        post_type: str,
        earliest_date: str = None,
        history_records: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取指定屋苑的所有交易记录（支持分页、日期过滤、增量更新）
        
        Args:
            estate: 屋苑信息字典
            post_type: 记录类型 ("Sale" 或 "Rent")
            earliest_date: 最早日期字符串（格式 'YYYY-MM-DD'），记录按日期降序排列，
                          当最后一条记录日期早于此日期时停止获取
            history_records: 历史记录列表（来自 history_dir 的历史文件），
                          第一条记录的 id 即为屋苑上一次爬取的最新交易记录
            
        Returns:
            最终记录列表（增量新记录 + 历史记录，或仅新记录）
        """
        estate_type_code = estate.get('typeCode', '')
        estate_name = estate.get('estateName', '未知屋苑')
        type_name = self._get_post_type_name(post_type)
        
        # 全量历史模式：不传day参数获取全部历史记录（双向爬取绕过API分页上限）
        if self.all_history:
            return self._fetch_full_history(
                estate=estate,
                post_type=post_type,
                earliest_date=earliest_date
            )
        
        # 解析最早日期
        earliest_date_obj = None
        if earliest_date:
            earliest_date_obj = self._parse_date(earliest_date)
            if earliest_date_obj:
                self._print_safe(f"    最早日期过滤: {earliest_date}")
        
        # 获取历史最新记录ID（第一条记录，即日期最新）
        history_latest_id = None
        if history_records:
            history_latest_id = history_records[0].get('id')
            if history_latest_id:
                self._print_safe(f"    增量模式: 历史最新记录ID={history_latest_id}")
        
        new_records = []       # 本次新报溢出来的记录
        stopped_by_date = False
        stopped_by_id = False
        
        # 第一次请求，获取总记录数
        first_response = self.fetch_transactions(
            estate_type_code=estate_type_code,
            post_type=post_type,
            offset=0,
            size=self.MAX_PAGE_SIZE
        )
        
        if not first_response:
            self._print_safe(f"    ✗ 获取 {estate_name} 的{type_name}记录失败")
            # 请求失败时，若有历史记录则直接返回历史记录
            return history_records if history_records else []
        
        # 获取总记录数
        total_count = first_response.get('count', 0)
        
        if total_count == 0:
            # 记录到 empty_estate.txt（sale 和 rent 都无记录时各记一次，以 post_type 区分）
            self._record_empty_estate(f"{estate_type_code}")
            self._print_safe(f"    ℹ {estate_name} ({estate_type_code}) {type_name}无记录，已写入 empty_estate.txt")
            # API无记录，直接返回历史记录
            return history_records if history_records else []
        
        # 处理第一页数据
        if 'data' in first_response and isinstance(first_response['data'], list):
            first_page_records = first_response['data']
            
            # 检查是否在第一页中应该停止（增量 ID 匹配或日期截断）
            page_new, stopped_by_id, stopped_by_date = self._filter_page_by_stop_conditions(
                page_records=first_page_records,
                history_latest_id=history_latest_id,
                earliest_date_obj=earliest_date_obj,
                earliest_date=earliest_date,
                page_num=1
            )
            new_records.extend(page_new)
        
        # 计算是否需要分页
        if total_count <= self.MAX_PAGE_SIZE or stopped_by_id or stopped_by_date:
            result = self._merge_with_history(new_records, history_records, stopped_by_id)
            suffix = self._build_stop_suffix(stopped_by_id, stopped_by_date)
            self._print_safe(f"    ✓ {type_name}记录: {len(result)} 条 (共1页{suffix})")
            return result
        
        # 计算页数
        total_pages = (total_count + self.MAX_PAGE_SIZE - 1) // self.MAX_PAGE_SIZE
        self._print_safe(f"    {type_name}记录: 共 {total_count} 条, {total_pages} 页")
        
        # 获取剩余页面
        for page in range(1, total_pages):
            time.sleep(self.request_interval)
            
            response = self.fetch_transactions(
                estate_type_code=estate_type_code,
                post_type=post_type,
                offset=page * self.MAX_PAGE_SIZE,
                size=self.MAX_PAGE_SIZE
            )
            
            if response and 'data' in response and isinstance(response['data'], list):
                page_records = response['data']
                
                page_new, stopped_by_id, stopped_by_date = self._filter_page_by_stop_conditions(
                    page_records=page_records,
                    history_latest_id=history_latest_id,
                    earliest_date_obj=earliest_date_obj,
                    earliest_date=earliest_date,
                    page_num=page + 1
                )
                new_records.extend(page_new)
                
                if stopped_by_id or stopped_by_date:
                    break
            else:
                self._print_safe(f"    ⚠ 获取 {estate_name} 第 {page + 1} 页数据失败")
        
        result = self._merge_with_history(new_records, history_records, stopped_by_id)
        suffix = self._build_stop_suffix(stopped_by_id, stopped_by_date)
        self._print_safe(f"    ✓ {type_name}记录: {len(result)} 条{suffix}")
        return result
    
    def _filter_page_by_stop_conditions(
        self,
        page_records: List[Dict[str, Any]],
        history_latest_id,
        earliest_date_obj,
        earliest_date: str,
        page_num: int
    ):
        """
        对单页记录按停止条件进行截断处理
        
        Args:
            page_records: 本页记录列表
            history_latest_id: 历史最新记录的ID
            earliest_date_obj: 最早日期对象
            earliest_date: 最早日期字符串（用于打印）
            page_num: 页码（用于打印）
            
        Returns:
            (filtered_records, stopped_by_id, stopped_by_date)
        """
        stopped_by_id = False
        stopped_by_date = False
        filtered = []
        
        for record in page_records:
            # 条件一：检查是否匹配历史最新记录ID
            if history_latest_id and record.get('id') == history_latest_id:
                stopped_by_id = True
                self._print_safe(f"    ⏹ 第{page_num}页匹配历史最新记录ID={history_latest_id}，停止新记录获取")
                break  # 这条及之后的记录都属于历史记录，不再添加
            
            # 条件二：检查日期截断
            if earliest_date_obj:
                record_date_str = record.get('insDate')
                if record_date_str:
                    record_date = self._parse_date(record_date_str)
                    if record_date and record_date < earliest_date_obj:
                        stopped_by_date = True
                        self._print_safe(
                            f"    ⏹ 第{page_num}页记录日期 {record_date} "
                            f"早于 {earliest_date}，停止获取"
                        )
                        break  # 这条及之后的记录日期更早，不再添加
            
            filtered.append(record)
        
        return filtered, stopped_by_id, stopped_by_date
    
    def _merge_with_history(
        self,
        new_records: List[Dict[str, Any]],
        history_records: Optional[List[Dict[str, Any]]],
        stopped_by_id: bool
    ) -> List[Dict[str, Any]]:
        """
        将新记录与历史记录拼接
        
        Args:
            new_records: 新爬取的记录
            history_records: 历史记录，可为None
            stopped_by_id: 是否因ID匹配而停止（才需拼接）
            
        Returns:
            拼接后的记录列表
        """
        if stopped_by_id and history_records:
            merged = new_records + history_records
            return merged
        return new_records
    
    def _build_stop_suffix(self, stopped_by_id: bool, stopped_by_date: bool) -> str:
        """生成停止原因的辅助文字"""
        if stopped_by_id:
            return " (增量更新完成)"
        if stopped_by_date:
            return " (日期截断)"
        return ""
    
    def save_records(
        self, 
        records: List[Dict[str, Any]], 
        estate_type_code: str,
        post_type: str
    ) -> str:
        """
        保存交易记录到JSON文件
        
        Args:
            records: 交易记录列表
            estate_type_code: 屋苑ID
            post_type: 记录类型 ("Sale" 或 "Rent")
            
        Returns:
            保存的文件路径
        """
        # 确定子目录名
        sub_dir = "sale" if post_type == self.POST_TYPE_SALE else "rent"
        
        # 创建完整目录路径
        full_dir = os.path.join(self.output_base_dir, sub_dir)
        os.makedirs(full_dir, exist_ok=True)
        
        # 构建输出文件路径
        output_file = os.path.join(full_dir, f"{estate_type_code}.json")
        
        # 构建输出数据结构
        output_data = {
            "typeCode": estate_type_code,
            "postType": post_type,
            "count": len(records),
            "crawlDate": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "data": records
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return output_file
    
    def _get_post_type_name(self, post_type: str) -> str:
        """获取记录类型的中文名称"""
        return "销售" if post_type == self.POST_TYPE_SALE else "租赁"
    
    def _print_safe(self, message: str):
        """线程安全的打印方法（flush=True 确保管道/重定向输出时实时可见）"""
        with self._progress_lock:
            print(message, flush=True)
    
    def scrape_estate(self, estate: Dict[str, Any], thread_idx: int = 0, total: int = 0) -> Dict[str, Any]:
        """
        爬取单个屋苑的销售和租赁记录
        
        Args:
            estate: 屋苑信息字典
            thread_idx: 当前处理的序号（用于进度显示）
            total: 总数（用于进度显示）
            
        Returns:
            爬取结果统计
        """
        estate_type_code = estate.get('typeCode', '')
        estate_name = estate.get('estateName', '未知屋苑')
        
        result = {
            'typeCode': estate_type_code,
            'estateName': estate_name,
            'sale_count': 0,
            'rent_count': 0,
            'success': True,
            'error': None
        }
        
        # 检查停止标志
        if self._stop_flag.is_set():
            result['success'] = False
            result['error'] = '爬取已被停止（Too Many Requests）'
            return result
        
        # 检查是否在空屋苑列表中
        if self._empty_estate_ids and estate_type_code in self._empty_estate_ids:
            result['skipped_empty'] = True
            self._print_safe(f"  [{thread_idx}/{total}] 跳过（空屋苑）: {estate_name} ({estate_type_code})")
            # 仍需记录进度，避免重复处理
            self._record_finished_estate(estate_type_code)
            return result
        
        self._print_safe(f"  [{thread_idx}/{total}] 处理: {estate_name} ({estate_type_code})")
        
        try:
            # 加载历史记录（增量更新用）
            sale_history = self.load_history_records(estate_type_code, self.POST_TYPE_SALE)
            history_sale_records = sale_history.get('data', []) if sale_history else None
            rent_history = self.load_history_records(estate_type_code, self.POST_TYPE_RENT)
            history_rent_records = rent_history.get('data', []) if rent_history else None
            
            # 爬取销售记录
            self._print_safe(f"    [{thread_idx}] 获取销售记录...")
            sale_records = self.fetch_all_transactions_for_estate(
                estate=estate,
                post_type=self.POST_TYPE_SALE,
                earliest_date=self.earliest_date,
                history_records=history_sale_records
            )
            
            if sale_records:
                self.save_records(
                    records=sale_records,
                    estate_type_code=estate_type_code,
                    post_type=self.POST_TYPE_SALE
                )
                result['sale_count'] = len(sale_records)
                with self._lock:
                    self.stats['sale_records'] += len(sale_records)
            else:
                self._print_safe(f"    [{thread_idx}] - 无销售记录")
            
            # 再次检查停止标志
            if self._stop_flag.is_set():
                result['success'] = False
                result['error'] = '爬取已被停止（Too Many Requests）'
                return result
            
            # 请求间隔
            time.sleep(self.request_interval)
            
            # 爬取租赁记录
            self._print_safe(f"    [{thread_idx}] 获取租赁记录...")
            rent_records = self.fetch_all_transactions_for_estate(
                estate=estate,
                post_type=self.POST_TYPE_RENT,
                earliest_date=self.earliest_date,
                history_records=history_rent_records
            )
            
            if rent_records:
                self.save_records(
                    records=rent_records,
                    estate_type_code=estate_type_code,
                    post_type=self.POST_TYPE_RENT
                )
                result['rent_count'] = len(rent_records)
                with self._lock:
                    self.stats['rent_records'] += len(rent_records)
            else:
                self._print_safe(f"    [{thread_idx}] - 无租赁记录")
            
            # 成功完成后记录进度
            self._record_finished_estate(estate_type_code)
                
        except TooManyRequestsError as e:
            # Too Many Requests 错误，标记停止
            result['success'] = False
            result['error'] = str(e)
            self._print_safe(f"\n!!! {e}")
            self._print_safe("!!! 爬取已停止，请稍后重试")
        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
            self._print_safe(f"    [{thread_idx}] ✗ 错误: {e}")
        
        return result
    
    def scrape_all_estates(self, start_from: int = 0, max_estates: int = None):
        """
        并发爬取所有屋苑的交易记录
        
        Args:
            start_from: 从第几个屋苑开始（用于断点续爬）
            max_estates: 最大爬取屋苑数量（用于测试）
        """
        print("=" * 60)
        print("开始爬取中原地产交易记录（并发模式）")
        print("=" * 60)
        
        if not self.estates:
            print("✗ 未加载屋苑信息，请先调用 load_estate_info() 或在初始化时提供 estate_info_path")
            return
        
        # 创建输出目录
        os.makedirs(os.path.join(self.output_base_dir, 'sale'), exist_ok=True)
        os.makedirs(os.path.join(self.output_base_dir, 'rent'), exist_ok=True)
        
        # 初始化进度文件
        self._init_progress_file()
        
        # 确定要爬取的屋苑范围
        estates_to_process = self.estates[start_from:]
        if max_estates:
            estates_to_process = estates_to_process[:max_estates]
        
        # 应用过滤（跳过已完成的屋苑）
        if self.skip_existing_files or self.skip_finished_file:
            print("\n正在过滤已完成的屋苑...")
            estates_to_process = self.filter_estates(estates_to_process)
        
        total_to_process = len(estates_to_process)
        
        if total_to_process == 0:
            print("\n✓ 所有屋苑已完成爬取，无需处理")
            return
        
        self.stats['start_time'] = datetime.now()
        
        print(f"\n屋苑总数: {len(self.estates)}")
        print(f"跳过屋苑: {self.stats['skipped_estates']}")
        print(f"计划爬取: {total_to_process} 个屋苑")
        print(f"并发线程: {self.workers}")
        print(f"输出目录: {os.path.abspath(self.output_base_dir)}")
        print(f"进度文件: {self.progress_file}")
        print(f"请求间隔: {self.request_interval} 秒")
        if self._empty_estate_ids:
            print(f"空屋苑跳过: 已加载 {len(self._empty_estate_ids)} 个空屋苑ID")
        print(f"空屋苑记录: {self._empty_estate_file}\n")
        
        # 重置停止标志
        self._stop_flag.clear()
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # 提交所有任务
            future_to_estate = {}
            for idx, estate in enumerate(estates_to_process, start=1):
                future = executor.submit(
                    self.scrape_estate, 
                    estate, 
                    thread_idx=idx,
                    total=total_to_process
                )
                future_to_estate[future] = estate
            
            # 收集结果
            for future in as_completed(future_to_estate):
                # 检查停止标志
                if self._stop_flag.is_set():
                    # 取消所有未完成的任务
                    for f in future_to_estate:
                        f.cancel()
                    break
                
                estate = future_to_estate[future]
                try:
                    result = future.result()
                    
                    with self._lock:
                        self.stats['processed_estates'] += 1
                        if not result['success']:
                            self.stats['failed_estates'].append(result)
                        
                        # 显示总体进度
                        processed = self.stats['processed_estates']
                        progress = processed * 100 // total_to_process
                        print(f"\n>>> 总进度: {processed}/{total_to_process} ({progress}%) - "
                              f"销售: {self.stats['sale_records']} 条, 租赁: {self.stats['rent_records']} 条")
                        
                except Exception as e:
                    with self._lock:
                        self.stats['processed_estates'] += 1
                        self.stats['failed_estates'].append({
                            'typeCode': estate.get('typeCode', ''),
                            'estateName': estate.get('estateName', '未知'),
                            'sale_count': 0,
                            'rent_count': 0,
                            'success': False,
                            'error': str(e)
                        })
        
        self.stats['end_time'] = datetime.now()
        
        # 打印统计信息
        self.print_summary()
    
    def print_summary(self):
        """打印爬取摘要"""
        duration = None
        if self.stats['start_time'] and self.stats['end_time']:
            duration = self.stats['end_time'] - self.stats['start_time']
        
        print(f"\n{'=' * 60}")
        print("爬取完成！")
        print("=" * 60)
        print(f"处理屋苑: {self.stats['processed_estates']}/{self.stats['total_estates']}")
        print(f"销售记录: {self.stats['sale_records']} 条")
        print(f"租赁记录: {self.stats['rent_records']} 条")
        print(f"失败屋苑: {len(self.stats['failed_estates'])} 个")
        
        if duration:
            print(f"总耗时: {duration}")
        
        if self.stats['failed_estates']:
            print(f"\n失败的屋苑:")
            for failed in self.stats['failed_estates']:
                print(f"  - {failed['estateName']} ({failed['typeCode']}): {failed['error']}")
        
        print(f"\n输出目录: {os.path.abspath(self.output_base_dir)}")
    
    def save_summary(self):
        """保存爬取摘要到文件"""
        summary_file = os.path.join(self.output_base_dir, "crawl_summary.json")
        
        duration = None
        if self.stats['start_time'] and self.stats['end_time']:
            duration = str(self.stats['end_time'] - self.stats['start_time'])
        
        summary = {
            "crawlDate": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "totalEstates": self.stats['total_estates'],
            "processedEstates": self.stats['processed_estates'],
            "saleRecords": self.stats['sale_records'],
            "rentRecords": self.stats['rent_records'],
            "failedEstates": len(self.stats['failed_estates']),
            "failedEstateDetails": self.stats['failed_estates'],
            "duration": duration,
            "outputDirectory": os.path.abspath(self.output_base_dir)
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 爬取摘要已保存到: {summary_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='中原地产屋苑交易记录爬虫',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本用法
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json
  
  # 设置并发线程数
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --workers 10
  
  # 跳过已存在记录文件的屋苑（断点续爬）
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --skip-existing-files
  
  # 从进度文件跳过已完成的屋苑
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --skip-finished-file finish_crawling_20260222_123456.txt
  
  # 组合使用：跳过已存在文件并从进度文件跳过
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --skip-existing-files --skip-finished-file finish_crawling_20260222_123456.txt
  
  # 使用最早日期过滤（只获取2025-01-01之后的记录）
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --earliest-date 2025-01-01
  
  # 增量更新（基于历史记录目录）
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --history-dir transaction_record_20260221
  
  # 跳过上次已确认无记录的屋苑（加速重复爬取）
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --skip-empty-file empty_estate.txt
  
  # 爬取全部历史成交记录（不传day参数，可获取1995年至今的全量数据）
  # 注意：数据量约为3年模式的10-20倍，请求量大，建议降低并发和加大间隔
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --all-history --workers 3 --interval 2.0
  
  # 分批爬取全量（推荐）：每批只爬一部分屋苑，多次运行后目录自动合并为完整数据
  # 批1：屋苑 0-1999；批2：屋苑 2000-3999（--skip-existing-files 自动跳过已完成的）
  # 中断后重跑同一批命令即可断点续爬，不会重复请求。也可直接运行 batch_crawl_all_history.sh
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --all-history --output-dir transaction_record_all_history --start-from 0 --max-estates 2000
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --all-history --output-dir transaction_record_all_history --start-from 2000 --max-estates 2000 --skip-existing-files
  
  # 其他参数
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --max-estates 100 --interval 2.0
        """
    )
    
    parser.add_argument(
        '--estate-info', 
        type=str, 
        required=True,
        help='屋苑信息JSON文件路径（必需）'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='并发线程数，默认5'
    )
    parser.add_argument(
        '--interval', 
        type=float, 
        default=1.0,
        help='请求间隔时间（秒），默认1.0'
    )
    parser.add_argument(
        '--retries', 
        type=int, 
        default=3,
        help='最大重试次数，默认3'
    )
    parser.add_argument(
        '--output-dir', 
        type=str, 
        default=None,
        help='输出目录（默认自动生成: transaction_record_YYYYMMDD）'
    )
    parser.add_argument(
        '--start-from', 
        type=int, 
        default=0,
        help='从第几个屋苑开始（用于断点续爬），默认0'
    )
    parser.add_argument(
        '--max-estates', 
        type=int, 
        default=None,
        help='最大爬取屋苑数量（用于测试），默认不限制'
    )
    parser.add_argument(
        '--skip-existing-files',
        action='store_true',
        help='跳过已存在记录文件的屋苑（扫描sale和rent目录）'
    )
    parser.add_argument(
        '--skip-finished-file',
        type=str,
        default=None,
        help='指定已完成屋苑ID记录文件路径，跳过该文件中记录的屋苑'
    )
    parser.add_argument(
        '--earliest-date',
        type=str,
        default=None,
        help='最早日期过滤（格式 YYYY-MM-DD），当记录日期早于此日期时停止获取'
    )
    parser.add_argument(
        '--history-dir',
        type=str,
        default=None,
        help='历史记录目录（上一次爬取的输出目录），用于增量更新。目录下应包含 sale/ 和 rent/ 子目录'
    )
    parser.add_argument(
        '--skip-empty-file',
        type=str,
        default=None,
        help='空屋苑记录文件路径（如 empty_estate.txt），跳过其中记录的无交易记录屋苑'
    )
    parser.add_argument(
        '--all-history',
        action='store_true',
        help='爬取全部历史成交记录（不传day参数，可获取1995年至今的全量数据；'
             '超过10000条的屋苑自动双向爬取去重）'
    )
    
    args = parser.parse_args()
    
    # 创建爬虫实例
    scraper = CentanetTransactionScraper(
        request_interval=args.interval,
        max_retries=args.retries,
        estate_info_path=args.estate_info,
        output_dir=args.output_dir,
        workers=args.workers,
        skip_existing_files=args.skip_existing_files,
        skip_finished_file=args.skip_finished_file,
        earliest_date=args.earliest_date,
        history_dir=args.history_dir,
        skip_empty_file=args.skip_empty_file,
        all_history=args.all_history
    )
    
    # 开始爬取
    scraper.scrape_all_estates(
        start_from=args.start_from,
        max_estates=args.max_estates
    )
    
    # 保存摘要
    scraper.save_summary()
    
    return scraper


if __name__ == '__main__':
    try:
        scraper = main()
        
    except KeyboardInterrupt:
        print("\n\n爬虫已被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
