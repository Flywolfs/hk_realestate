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
    
    def __init__(
        self, 
        request_interval: float = 1.0, 
        max_retries: int = 3,
        estate_info_path: str = None,
        output_dir: str = None,
        workers: int = 5
    ):
        """
        初始化爬虫
        
        Args:
            request_interval: 请求间隔时间（秒），默认1.0秒
            max_retries: 最大重试次数，默认3次
            estate_info_path: 屋苑信息JSON文件路径
            output_dir: 输出目录，默认为当前目录下的transaction_record_[日期]
            workers: 并发线程数，默认5
        """
        self.session = requests.Session()
        self.request_interval = request_interval
        self.max_retries = max_retries
        self.workers = workers
        
        # 线程锁，用于保护共享资源
        self._lock = threading.Lock()
        self._progress_lock = threading.Lock()
        
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
        size: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定屋苑的交易记录
        
        Args:
            estate_type_code: 屋苑ID（typeCode）
            post_type: 记录类型 ("Sale" 或 "Rent")
            offset: 分页偏移量
            size: 每页数据量
            
        Returns:
            API响应数据，失败返回None
        """
        payload = {
            "postType": post_type,
            "day": self.DAY_RANGE,
            "sort": "InsOrRegDate",
            "order": "Descending",
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
    
    def fetch_all_transactions_for_estate(
        self, 
        estate: Dict[str, Any],
        post_type: str
    ) -> List[Dict[str, Any]]:
        """
        获取指定屋苑的所有交易记录（支持分页）
        
        Args:
            estate: 屋苑信息字典
            post_type: 记录类型 ("Sale" 或 "Rent")
            
        Returns:
            交易记录列表
        """
        estate_type_code = estate.get('typeCode', '')
        estate_name = estate.get('estateName', '未知屋苑')
        
        all_records = []
        
        # 第一次请求，获取总记录数
        first_response = self.fetch_transactions(
            estate_type_code=estate_type_code,
            post_type=post_type,
            offset=0,
            size=self.MAX_PAGE_SIZE
        )
        
        if not first_response:
            self._print_safe(f"    ✗ 获取 {estate_name} 的{self._get_post_type_name(post_type)}记录失败")
            return []
        
        # 获取总记录数
        total_count = first_response.get('count', 0)
        
        if total_count == 0:
            return []
        
        # 添加第一批数据
        if 'data' in first_response and isinstance(first_response['data'], list):
            all_records.extend(first_response['data'])
        
        # 计算是否需要分页
        if total_count <= self.MAX_PAGE_SIZE:
            self._print_safe(f"    ✓ {self._get_post_type_name(post_type)}记录: {len(all_records)} 条 (共1页)")
            return all_records
        
        # 计算需要的页数
        total_pages = (total_count + self.MAX_PAGE_SIZE - 1) // self.MAX_PAGE_SIZE
        
        # 显示分页进度（第一页已获取）
        self._print_safe(f"    {self._get_post_type_name(post_type)}记录: 共 {total_count} 条, {total_pages} 页")
        
        # 获取剩余页面
        for page in range(1, total_pages):
            offset = page * self.MAX_PAGE_SIZE
            
            # 请求间隔
            time.sleep(self.request_interval)
            
            response = self.fetch_transactions(
                estate_type_code=estate_type_code,
                post_type=post_type,
                offset=offset,
                size=self.MAX_PAGE_SIZE
            )
            
            if response and 'data' in response and isinstance(response['data'], list):
                all_records.extend(response['data'])
            else:
                self._print_safe(f"    ⚠ 获取 {estate_name} 第 {page + 1} 页数据失败")
        
        self._print_safe(f"    ✓ {self._get_post_type_name(post_type)}记录: {len(all_records)} 条")
        
        return all_records
    
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
        """线程安全的打印方法"""
        with self._progress_lock:
            print(message)
    
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
        
        self._print_safe(f"  [{thread_idx}/{total}] 处理: {estate_name} ({estate_type_code})")
        
        try:
            # 爬取销售记录
            self._print_safe(f"    [{thread_idx}] 获取销售记录...")
            sale_records = self.fetch_all_transactions_for_estate(
                estate=estate,
                post_type=self.POST_TYPE_SALE
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
            
            # 请求间隔
            time.sleep(self.request_interval)
            
            # 爬取租赁记录
            self._print_safe(f"    [{thread_idx}] 获取租赁记录...")
            rent_records = self.fetch_all_transactions_for_estate(
                estate=estate,
                post_type=self.POST_TYPE_RENT
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
        
        self.stats['start_time'] = datetime.now()
        
        # 确定要爬取的屋苑范围
        total_to_process = len(self.estates) - start_from
        if max_estates:
            total_to_process = min(total_to_process, max_estates)
        
        end_index = start_from + total_to_process
        estates_to_process = self.estates[start_from:end_index]
        
        print(f"\n屋苑总数: {len(self.estates)}")
        print(f"起始位置: {start_from}")
        print(f"计划爬取: {total_to_process} 个屋苑")
        print(f"并发线程: {self.workers}")
        print(f"输出目录: {os.path.abspath(self.output_base_dir)}")
        print(f"请求间隔: {self.request_interval} 秒\n")
        
        # 创建输出目录
        os.makedirs(os.path.join(self.output_base_dir, 'sale'), exist_ok=True)
        os.makedirs(os.path.join(self.output_base_dir, 'rent'), exist_ok=True)
        
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
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --workers 10
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --max-estates 100
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --start-from 500
  python scrape_centanet_transactions.py --estate-info estate_info_20260221.json --interval 2.0
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
    
    args = parser.parse_args()
    
    # 创建爬虫实例
    scraper = CentanetTransactionScraper(
        request_interval=args.interval,
        max_retries=args.retries,
        estate_info_path=args.estate_info,
        output_dir=args.output_dir,
        workers=args.workers
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
