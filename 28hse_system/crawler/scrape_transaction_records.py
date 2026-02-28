#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
屋苑成交记录爬取脚本
获取每个屋苑的买卖成交记录和租房成交记录
"""

import requests
import re
import json
import os
import time
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from datetime import datetime
import sys


class TransactionRecordScraper:
    """屋苑成交记录爬虫"""
    
    def __init__(self, max_workers: int = 3, incremental: bool = False, data_dir: str = '28hse/transaction_records'):
        """
        初始化爬虫
        
        Args:
            max_workers: 并发线程数，默认3（成交记录数据量大，降低并发避免被限制）
            incremental: 是否启用增量爬取模式
            data_dir: 数据存储目录
        """
        self.base_url = "https://www.28hse.com"
        self.api_url = f"{self.base_url}/estate/detail_doaction"
        self.session = requests.Session()
        self.max_workers = max_workers
        self.incremental = incremental
        self.data_dir = data_dir
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.base_url,
        })
        
    def load_estates_mapping(self, json_path: str) -> Dict[str, str]:
        """
        加载屋苑ID-名称映射
        
        Args:
            json_path: estates_mapping.json 文件路径
            
        Returns:
            {屋苑ID: 屋苑名称}
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载屋苑映射文件失败: {e}")
            return {}
    
    def is_date_after_2025(self, date_str: str) -> bool:
        """
        检查日期是否在2025年之后（包括2025年）
        
        Args:
            date_str: 日期字符串，格式如 "2026-02-03", "2025-12-31", "2024-01-01"
            
        Returns:
            True表示2025年或之后，False表示2025年之前
        """
        try:
            # 解析日期字符串
            date = datetime.strptime(date_str, '%Y-%m-%d')
            # 检查年份是否 >= 2025
            return date.year >= 2025
        except Exception as e:
            # 如果解析失败，保守起见返回True（继续爬取）
            print(f"    ⚠️  日期解析失败: {date_str} - {e}")
            return True
    
    def compare_dates(self, date1: str, date2: str) -> int:
        """
        比较两个日期
        
        Args:
            date1: 日期字符串1
            date2: 日期字符串2
            
        Returns:
            1 if date1 > date2, -1 if date1 < date2, 0 if equal
        """
        try:
            d1 = datetime.strptime(date1, '%Y-%m-%d')
            d2 = datetime.strptime(date2, '%Y-%m-%d')
            if d1 > d2:
                return 1
            elif d1 < d2:
                return -1
            else:
                return 0
        except Exception:
            return 0
    
    def load_existing_data(self, estate_id: str, field: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        加载现有的交易记录数据
        
        Args:
            estate_id: 屋苑ID
            field: 'buy' 或 'rent'
            
        Returns:
            (现有数据字典, 最新记录的日期) 或 (None, None)
        """
        file_path = os.path.join(self.data_dir, field, f"{estate_id}.json")
        
        if not os.path.exists(file_path):
            return None, None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 获取最新记录的日期（第一条记录）
            transactions = data.get('transactions', [])
            if transactions and len(transactions) > 0:
                latest_date = transactions[0].get('date', '')
                return data, latest_date
            
            return data, None
        except Exception as e:
            print(f"    ⚠️  加载现有数据失败 ({estate_id} {field}): {e}")
            return None, None
    
    def merge_transactions(self, existing_data: Dict, new_transactions: List[Dict]) -> Dict:
        """
        合并新旧交易记录，去重并按日期排序
        
        Args:
            existing_data: 现有数据
            new_transactions: 新获取的交易记录
            
        Returns:
            合并后的完整数据
        """
        existing_transactions = existing_data.get('transactions', [])
        
        # 创建一个集合用于去重（基于关键字段）
        seen = set()
        merged = []
        
        # 首先添加所有新记录
        for trans in new_transactions:
            key = (trans.get('unit_location', ''), 
                   trans.get('date', ''), 
                   trans.get('total_price') or trans.get('total_rent', ''))
            if key not in seen:
                seen.add(key)
                merged.append(trans)
        
        # 然后添加现有记录（如果不重复）
        for trans in existing_transactions:
            key = (trans.get('unit_location', ''), 
                   trans.get('date', ''), 
                   trans.get('total_price') or trans.get('total_rent', ''))
            if key not in seen:
                seen.add(key)
                merged.append(trans)
        
        # 按日期从新到旧排序
        merged.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # 更新数据
        result = existing_data.copy()
        result['transactions'] = merged
        result['total_records'] = len(merged)
        
        return result
    
    def filter_transactions_by_date(self, transactions: List[Dict]) -> Tuple[List[Dict], bool]:
        """
        过滤交易记录，只保留2025年及之后的记录
        
        Args:
            transactions: 交易记录列表
            
        Returns:
            (过滤后的记录列表, 是否全部记录都在2025年之前)
        """
        filtered = []
        all_before_2025 = True
        
        for trans in transactions:
            date_str = trans.get('date', '')
            if date_str and self.is_date_after_2025(date_str):
                filtered.append(trans)
                all_before_2025 = False
        
        return filtered, all_before_2025
    
    def fetch_transaction_page(self, estate_id: str, page: int, field: str) -> Optional[str]:
        """
        获取指定页面的成交记录HTML
        
        Args:
            estate_id: 屋苑ID
            page: 页码（从1开始）
            field: 'buy' 或 'rent'
            
        Returns:
            HTML内容，失败返回None
        """
        # 直接构造form data参数（不需要form_data包装）
        data = {
            'action': 'get_trans',
            'cat_id': estate_id,
            'state_no': '0',
            'page': str(page),
            'field': field,
            'isPagination': '1'
        }
        
        try:
            response = self.session.post(
                self.api_url,
                data=data,
                timeout=30
            )
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            # 解析JSON响应
            result = response.json()
            
            # API返回格式：{"status": 1, "data": {"results": {"html": "<html内容>"}}}
            if result.get('status') == 1 and 'data' in result:
                data_obj = result['data']
                if isinstance(data_obj, dict) and 'results' in data_obj:
                    results = data_obj['results']
                    if isinstance(results, dict) and 'html' in results:
                        return results['html']
            
            # 如果响应格式不对，记录错误信息
            if 'result_error_msg' in result and result['result_error_msg']:
                print(f"  ⚠️  API错误: {result['result_error_msg']}")
            else:
                print(f"  ⚠️  API响应格式不正确: {list(result.keys())}")
            
            return None
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 请求失败 (estate_id={estate_id}, page={page}, field={field}): {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"  ❌ JSON解析失败: {e}")
            return None
        except Exception as e:
            print(f"  ❌ 未知错误: {e}")
            return None
    
    def parse_buy_transactions(self, html: str) -> List[Dict]:
        """
        解析买卖成交记录
            
        Args:
            html: HTML内容
                
        Returns:
            成交记录列表
        """
        soup = BeautifulSoup(html, 'lxml')
        transactions = []
            
        # 查找成交记录表格：<table class="ui celled striped table">
        table = soup.find('table', class_='ui')
        if not table:
            return transactions
            
        # 查找表体
        tbody = table.find('tbody')
        if not tbody:
            return transactions
            
        # 遍历所有数据行
        rows = tbody.find_all('tr')
            
        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                    
                # 第1列：物业地址（复杂结构）
                address_cell = cells[0]
                    
                # 提取房间位置（在 div.header > a 中）
                header_div = address_cell.find('div', class_='header')
                unit_location = ''
                if header_div:
                    link = header_div.find('a')
                    if link:
                        unit_location = link.get_text(strip=True)
                        # 如果有title属性，优先使用
                        full_address = link.get('title', '')
                        if full_address:
                            unit_location = full_address
                    
                # 提取标签信息（在 div.labels 中）
                labels_div = address_cell.find('div', class_='labels')
                date = ''
                transaction_type = ''
                room_type = ''
                    
                if labels_div:
                    labels = labels_div.find_all('div', class_='label')
                    if len(labels) >= 1:
                        # 第1个label：成交日期（去除icon）
                        date_label = labels[0]
                        # 移除icon
                        for icon in date_label.find_all('i'):
                            icon.decompose()
                        date = date_label.get_text(strip=True)
                        
                    if len(labels) >= 2:
                        # 第2个label：成交类型
                        transaction_type = labels[1].get_text(strip=True)
                        
                    if len(labels) >= 3:
                        # 第3个label：房型
                        room_type = labels[2].get_text(strip=True)
                    
                # 第2列：面积
                area = cells[1].get_text(strip=True)
                    
                # 第3列：成交价钱（复杂结构）
                price_cell = cells[2]
                    
                # 总价（在 div.price 中）
                price_div = price_cell.find('div', class_='price')
                total_price = ''
                if price_div:
                    total_price = price_div.get_text(strip=True)
                    
                # 尺价（在 span.unit_price 中）
                unit_price_span = price_cell.find('span', class_='unit_price')
                price_per_sqft = ''
                if unit_price_span:
                    # 移除@符号
                    for at_symbol in unit_price_span.find_all('span', class_='at-symbol'):
                        at_symbol.decompose()
                    price_per_sqft = unit_price_span.get_text(strip=True)
                    
                # 第4列：盈利/蝕让
                profit_loss_cell = cells[3]
                profit_loss_span = profit_loss_cell.find('span', class_='less_span')
                profit_loss_rate = ''
                if profit_loss_span:
                    profit_loss_rate = profit_loss_span.get_text(strip=True)
                    
                # 构造成交记录
                transaction = {
                    'unit_location': unit_location,           # 房间位置（如：第九期 9座 13楼 A室）
                    'date': date,                             # 成交日期
                    'transaction_type': transaction_type,     # 成交类型（註冊處成交/市場成交）
                    'room_type': room_type,                   # 房型（3房/2房等）
                    'area': area,                             # 面积
                    'total_price': total_price,               # 总价
                    'price_per_sqft': price_per_sqft,         # 尺价
                    'profit_loss_rate': profit_loss_rate      # 盈利/蝕让率
                }
                    
                transactions.append(transaction)
            except Exception as e:
                print(f"    ⚠️  解析买卖记录行失败: {e}")
                continue
            
        return transactions
    
    def parse_rent_transactions(self, html: str) -> List[Dict]:
        """
        解析租房成交记录
        
        Args:
            html: HTML内容
            
        Returns:
            成交记录列表
        """
        soup = BeautifulSoup(html, 'lxml')
        transactions = []
        
        # 查找成交记录表格：<table class="ui celled striped table">
        table = soup.find('table', class_='ui')
        if not table:
            return transactions
        
        # 查找表体
        tbody = table.find('tbody')
        if not tbody:
            return transactions
        
        # 遍历所有数据行
        rows = tbody.find_all('tr')
        
        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                # 第1列：物业地址（复杂结构）
                address_cell = cells[0]
                
                # 提取房间位置（在 div.header > a 中）
                header_div = address_cell.find('div', class_='header')
                unit_location = ''
                if header_div:
                    link = header_div.find('a')
                    if link:
                        unit_location = link.get_text(strip=True)
                        # 如果有title属性，优先使用
                        full_address = link.get('title', '')
                        if full_address:
                            unit_location = full_address
                
                # 提取标签信息（在 div.labels 中）
                labels_div = address_cell.find('div', class_='labels')
                date = ''
                transaction_type = ''
                room_type = ''
                
                if labels_div:
                    labels = labels_div.find_all('div', class_='label')
                    if len(labels) >= 1:
                        # 第1个label：成交日期（去除icon）
                        date_label = labels[0]
                        # 移除icon
                        for icon in date_label.find_all('i'):
                            icon.decompose()
                        date = date_label.get_text(strip=True)
                    
                    if len(labels) >= 2:
                        # 第2个label：成交类型
                        transaction_type = labels[1].get_text(strip=True)
                    
                    if len(labels) >= 3:
                        # 第3个label：房型
                        room_type = labels[2].get_text(strip=True)
                
                # 第2列：面积
                area = cells[1].get_text(strip=True)
                
                # 第3列：租金价钱（复杂结构）
                price_cell = cells[2]
                
                # 租金总价（在 div.price 中）
                price_div = price_cell.find('div', class_='price')
                total_rent = ''
                if price_div:
                    total_rent = price_div.get_text(strip=True)
                
                # 租金尺价（在 span.unit_price 中）
                unit_price_span = price_cell.find('span', class_='unit_price')
                rent_per_sqft = ''
                if unit_price_span:
                    # 移除@符号
                    for at_symbol in unit_price_span.find_all('span', class_='at-symbol'):
                        at_symbol.decompose()
                    rent_per_sqft = unit_price_span.get_text(strip=True)
                
                # 第4列：租赁记录通常为空或"-"
                # 不需要提取profit_loss_rate
                
                # 构造成交记录
                transaction = {
                    'unit_location': unit_location,           # 房间位置
                    'date': date,                             # 成交日期
                    'transaction_type': transaction_type,     # 成交类型
                    'room_type': room_type,                   # 房型
                    'area': area,                             # 面积
                    'total_rent': total_rent,                 # 租金总价
                    'rent_per_sqft': rent_per_sqft            # 租金尺价
                }
                
                transactions.append(transaction)
            except Exception as e:
                print(f"    ⚠️  解析租房记录行失败: {e}")
                continue
        
        return transactions
    
    def get_total_pages(self, html: str) -> int:
        """
        从HTML中提取总页数
        
        Args:
            html: HTML内容
            
        Returns:
            总页数，失败返回1
        """
        soup = BeautifulSoup(html, 'lxml')
        
    def get_total_pages(self, html: str) -> int:
        """
        从TML中提取总页数
        
        Args:
            html: HTML内容
            
        Returns:
            总页数，失败返回1
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # 查找分页信息
        # 可能的位置：
        # 1. <div class="pagination"> 中的最后一页链接
        # 2. <span class="page-info"> 显示 "第1页/共X页"
        # 3. <a> 标签中的 data-page 属性
        
        # 方法1: 查找分页容器（包拮pagination class的div）
        pagination_divs = soup.find_all('div', class_=re.compile(r'pagination'))
        
        max_page = 1
        for pagination in pagination_divs:
            # 查找所有页码链接 <a class="item">
            page_items = pagination.find_all('a', class_='item')
            
            for item in page_items:
                # 跳过disabled的按钮（...）
                if 'disabled' in item.get('class', []):
                    continue
                
                text = item.get_text(strip=True)
                # 尝试提取数字
                if text.isdigit():
                    page_num = int(text)
                    max_page = max(max_page, page_num)
        
        if max_page > 1:
            return max_page
        
        # 方法2: 查找 "第X页/共Y页" 格式
        page_info = soup.find(string=re.compile(r'共\s*(\d+)\s*頁'))
        if page_info:
            match = re.search(r'共\s*(\d+)\s*頁', page_info)
            if match:
                return int(match.group(1))
        
        # 方法3: 查找所有包含页码的元素
        all_text = soup.get_text()
        matches = re.findall(r'(\d+)\s*頁', all_text)
        if matches:
            return max(int(m) for m in matches)
        
        return 1
    
    def scrape_estate_transactions(self, estate_name: str, estate_id: str, 
                                   field: str) -> Tuple[List[Dict], bool]:
        """
        爬取单个屋苑的2025年及之后的成交记录（支持增量模式）
        
        Args:
            estate_name: 屋苑名称
            estate_id: 屋苑ID
            field: 'buy' 或 'rent'
            
        Returns:
            (所有2025年及之后的成交记录列表, 是否为增量更新)
        """
        print(f"  正在爬取: {estate_name} ({field}记录)")
        
        # 增量模式：加载现有数据
        cutoff_date = None
        is_incremental_update = False
        
        if self.incremental:
            existing_data, latest_date = self.load_existing_data(estate_id, field)
            if existing_data and latest_date:
                cutoff_date = latest_date
                is_incremental_update = True
                print(f"    🔄 增量模式: 现有数据最新日期 = {cutoff_date}")
        
        all_transactions = []
        
        # 先获取第1页，确定总页数
        first_page_html = self.fetch_transaction_page(estate_id, 1, field)
        if not first_page_html:
            print(f"    ⚠️  无法获取第1页数据")
            return all_transactions, is_incremental_update
        
        # 解析第1页数据
        if field == 'buy':
            page_transactions = self.parse_buy_transactions(first_page_html)
        else:
            page_transactions = self.parse_rent_transactions(first_page_html)
        
        # 增量模式：检查是否有比cutoff_date更新的记录
        if cutoff_date:
            new_records = []
            reached_cutoff = False
            
            for trans in page_transactions:
                trans_date = trans.get('date', '')
                if not trans_date:
                    continue
                
                # 如果记录日期 <= cutoff_date，停止
                if self.compare_dates(trans_date, cutoff_date) <= 0:
                    reached_cutoff = True
                    break
                
                # 只保禙2025年及之后的记录
                if self.is_date_after_2025(trans_date):
                    new_records.append(trans)
            
            all_transactions.extend(new_records)
            print(f"    第1页: {len(page_transactions)} 条记录 (新增: {len(new_records)} 条)")
            
            # 如果第1页就达到了cutoff，直接返回
            if reached_cutoff:
                print(f"    ✓ 已达到现有数据日期，停止爬取")
                print(f"    ✓ 完成: 新增 {len(all_transactions)} 条{field}记录")
                return all_transactions, is_incremental_update
        else:
            # 非增量模式：过滤日期
            filtered_transactions, all_before_2025 = self.filter_transactions_by_date(page_transactions)
            all_transactions.extend(filtered_transactions)
            
            print(f"    第1页: {len(page_transactions)} 条记录 (过滤后: {len(filtered_transactions)} 条)")
            
            # 如果第1页全部是2025年之前的记录，直接返回
            if all_before_2025:
                print(f"    ℹ️  第1页全部是2025年之前的记录，停止爬取")
                print(f"    ✓ 完成: 共 {len(all_transactions)} 条{field}记录 (2025年及之后)")
                return all_transactions, is_incremental_update
        
        # 获取总页数
        total_pages = self.get_total_pages(first_page_html)
        print(f"    总页数: {total_pages}")
        
        # 爬取剩余页面
        for page in range(2, total_pages + 1):
            time.sleep(0.5)  # 降低请求频率
            
            html = self.fetch_transaction_page(estate_id, page, field)
            if not html:
                print(f"    ⚠️  第{page}页获取失败，跳过")
                continue
            
            # 解析数据
            if field == 'buy':
                page_transactions = self.parse_buy_transactions(html)
            else:
                page_transactions = self.parse_rent_transactions(html)
            
            # 增量模式：检查cutoff
            if cutoff_date:
                new_records = []
                reached_cutoff = False
                
                for trans in page_transactions:
                    trans_date = trans.get('date', '')
                    if not trans_date:
                        continue
                    
                    if self.compare_dates(trans_date, cutoff_date) <= 0:
                        reached_cutoff = True
                        break
                    
                    if self.is_date_after_2025(trans_date):
                        new_records.append(trans)
                
                all_transactions.extend(new_records)
                print(f"    第{page}页: {len(page_transactions)} 条记录 (新增: {len(new_records)} 条)")
                
                # 达到cutoff，停止爬取
                if reached_cutoff:
                    print(f"    ✓ 已达到现有数据日期，停止爬取")
                    break
            else:
                # 非增量模式
                filtered_transactions, all_before_2025 = self.filter_transactions_by_date(page_transactions)
                all_transactions.extend(filtered_transactions)
                
                print(f"    第{page}页: {len(page_transactions)} 条记录 (过滤后: {len(filtered_transactions)} 条)")
                
                # 早停机制
                if all_before_2025:
                    print(f"    ℹ️  第{page}页全部是2025年之前的记录，停止爬取")
                    break
        
        print(f"    ✓ 完成: 共 {len(all_transactions)} 条{field}记录")
        return all_transactions, is_incremental_update
    
    def save_transactions(self, estate_id: str, transactions: List[Dict], 
                         field: str, output_dir: str, is_incremental: bool = False):
        """
        保存成交记录到JSON文件（支持增量更新）
        
        Args:
            estate_id: 屋苑ID
            transactions: 成交记录列表
            field: 'buy' 或 'rent'
            output_dir: 输出目录
            is_incremental: 是否为增量更新
        """
        # 创建子文件夹
        folder_name = 'buy' if field == 'buy' else 'rent'
        folder_path = os.path.join(output_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(folder_path, f"{estate_id}.json")
        
        try:
            # 增量模式：合并现有数据
            if is_incremental:
                existing_data, _ = self.load_existing_data(estate_id, field)
                print(f"      🔄 更新前: 现有数据共{existing_data['total_records']}条")
                if existing_data:
                    merged_data = self.merge_transactions(existing_data, transactions)
                    print(f"      🔄 增量更新: 新增{len(transactions)}条, 合并后共{merged_data['total_records']}条")
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(merged_data, f, ensure_ascii=False, indent=2)
                    print(f"      ✓ 已保存到: {file_path}")
                    return
            
            # 非增量模式或无现有数据：直接保存
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'estate_id': estate_id,
                    'record_type': field,
                    'total_records': len(transactions),
                    'transactions': transactions
                }, f, ensure_ascii=False, indent=2)
            print(f"      ✓ 已保存到: {file_path}")
        except Exception as e:
            print(f"      ❌ 保存失败: {e}")
    
    def scrape_all(self, estates_mapping: Dict[str, str], output_dir: str = 'transaction_records'):
        """
        爬取所有屋苑的成交记录
        
        Args:
            estates_mapping: {屋苑名称: 屋苑ID}
            output_dir: 输出目录
        """
        total = len(estates_mapping)
        print(f"\n{'='*60}")
        print(f"开始爬取 {total} 个屋苑的成交记录")
        print(f"{'='*60}\n")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        completed = 0
        
        def process_estate(estate_name, estate_id):
            """处理单个屋苑"""
            try:
                # 爬取买卖记录
                buy_records, is_incremental_buy = self.scrape_estate_transactions(estate_name, estate_id, 'buy')
                # if buy_records:
                self.save_transactions(estate_id, buy_records, 'buy', output_dir, is_incremental_buy)
                
                time.sleep(1)  # 两种记录之间间隔
                
                # 爬取租房记录
                rent_records, is_incremental_rent = self.scrape_estate_transactions(estate_name, estate_id, 'rent')
                # if rent_records:
                self.save_transactions(estate_id, rent_records, 'rent', output_dir, is_incremental_rent)
                
                return True
            except Exception as e:
                print(f"  ❌ 处理失败 ({estate_name}): {e}")
                return False
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(process_estate, name, eid): (name, eid)
                for eid, name in estates_mapping.items()
            }
            
            for future in as_completed(futures):
                completed += 1
                estate_name, estate_id = futures[future]
                
                try:
                    success = future.result()
                    status = "✓" if success else "✗"
                    print(f"\n进度: {completed}/{total} ({completed*100//total}%) {status}\n")
                except Exception as e:
                    print(f"\n  ❌ 异常: {estate_name} - {e}\n")
        
        print(f"\n{'='*60}")
        print(f"爬取完成！")
        print(f"  输出目录: {output_dir}")
        print(f"  买卖记录: {output_dir}/buy/")
        print(f"  租房记录: {output_dir}/rent/")
        print(f"{'='*60}\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='屋苑成交记录爬虫 (支持增量更新)')
    parser.add_argument('--mapping', type=str, default='estates_mapping.json',
                       help='屋苑映射文件路径 (默认: estates_mapping.json)')
    parser.add_argument('--output', type=str, default='transaction_records',
                       help='输出目录 (默认: transaction_records)')
    parser.add_argument('--data-dir', type=str, default='28hse/transaction_records',
                       help='现有数据目录，用于增量模式 (默认: 28hse/transaction_records)')
    parser.add_argument('--workers', type=int, default=3,
                       help='并发线程数 (默认: 3)')
    parser.add_argument('--limit', type=int, default=0,
                       help='限制处理的屋苑数量，0表示全部 (默认: 0)')
    parser.add_argument('--incremental', action='store_true',
                       help='启用增量爬取模式，只爬取比现有数据更新的记录')
    
    args = parser.parse_args()
    
    # 创建爬虫实例
    scraper = TransactionRecordScraper(
        max_workers=args.workers,
        incremental=args.incremental,
        data_dir=args.data_dir
    )
    
    # 显示模式
    if args.incremental:
        print("\n🔄 增量爬取模式已启用")
        print(f"   现有数据目录: {args.data_dir}")
        print(f"   将只爬取比现有数据更新的记录\n")
    else:
        print("\n🆕 全量爬取模式")
        print("   将爬取2025年及之后的所有记录\n")
    
    # 加载屋苑映射
    print("正在加载屋苑映射...")
    estates_mapping = scraper.load_estates_mapping(args.mapping)
    
    if not estates_mapping:
        print("❌ 未找到屋苑映射数据")
        return
    
    print(f"✓ 已加载 {len(estates_mapping)} 个屋苑")
    
    # 如果设置了限制，只处理前N个
    if args.limit > 0:
        estates_mapping = dict(list(estates_mapping.items())[:args.limit])
        print(f"  (限制处理前 {args.limit} 个屋苑)")
    
    # 开始爬取
    scraper.scrape_all(estates_mapping, args.output)


if __name__ == '__main__':
    main()
