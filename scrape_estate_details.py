#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
屋苑详细信息爬取脚本
获取每个屋苑的静态信息（屋苑资料、地址、坐标）和动态信息（楼价走势、租赁市场）
"""

import requests
import re
import json
import os
import time
from bs4 import BeautifulSoup
from typing import Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
import sys


class EstateDetailScraper:
    """屋苑详细信息爬虫"""
    
    def __init__(self, max_workers: int = 5):
        """
        初始化爬虫
        
        Args:
            max_workers: 并发线程数，默认5
        """
        self.base_url = "https://www.28hse.com"
        self.session = requests.Session()
        self.max_workers = max_workers
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        
        # 存储结果
        self.static_data = {}   # {estate_id: {静态信息}}
        self.dynamic_data = {}  # {estate_id: {动态信息}}
        
    def load_estates_mapping(self, json_path: str) -> Dict[str, str]:
        """
        加载屋苑名称-ID映射
        
        Args:
            json_path: estates_mapping.json 文件路径
            
        Returns:
            {屋苑名称: 屋苑ID} 字典
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def fetch_estate_detail(self, estate_name: str, estate_id: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        获取单个屋苑的详细信息
        
        Args:
            estate_name: 屋苑名称
            estate_id: 屋苑ID
            
        Returns:
            (静态信息dict, 动态信息dict) 或 (None, None) 如果失败
        """
        # 构造URL，屋苑名称需要URL编码
        url = f"{self.base_url}/estate/detail/{quote(estate_name)}-{estate_id}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # 解析HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 提取静态信息
            static_info = self._extract_static_info(soup, estate_name, estate_id, response.text)
            
            # 提取动态信息
            dynamic_info = self._extract_dynamic_info(soup)
            
            return (static_info, dynamic_info)
            
        except Exception as e:
            print(f"  ✗ 获取 {estate_name}(ID:{estate_id}) 失败: {e}")
            return (None, None)
    
    def _extract_static_info(self, soup: BeautifulSoup, estate_name: str, estate_id: str, page_text: str) -> Dict:
        """提取静态信息：屋苑资料、地址、坐标"""
        static_info = {
            'name': estate_name,
            'id': estate_id
        }
        
        # 提取地址
        address_link = soup.find('a', href=re.compile(r'#estate_id_map'))
        if address_link:
            static_info['address'] = address_link.get_text(strip=True)
        
        # 提取坐标（从JavaScript代码中）
        lat_match = re.search(r'defaultLat\s*=\s*([\d.]+)', page_text)
        lng_match = re.search(r'defaultLng\s*=\s*([\d.]+)', page_text)
        if lat_match and lng_match:
            static_info['coordinates'] = {
                'latitude': float(lng_match.group(1)),   # 注意：网站的Lng实际是纬度
                'longitude': float(lat_match.group(1))   # 网站的Lat实际是经度
            }
        
        # 提取屋苑资料
        estate_info_section = soup.find('h3', string=re.compile(r'屋苑資料'))
        if estate_info_section:
            # 找到h3所在的segment容器
            segment = estate_info_section.find_parent('div', class_='segment')
            if segment:
                basic_info = {}
                
                # 查找所有grid容器，找到包含row的那个（通常是第2个grid）
                grids = segment.find_all('div', class_='grid')
                data_grid = None
                for grid in grids:
                    # 检查这个grid是否包含row
                    rows = grid.find_all('div', class_='row', recursive=False)
                    if rows:  # 如果找到row，这就是数据grid
                        data_grid = grid
                        break
                
                if data_grid:
                    # 查找所有包含数据的row
                    for row in data_grid.find_all('div', class_='row', recursive=False):
                        # 左侧：字段标签（在 five wide column 中）
                        label_col = row.find('div', class_='five')
                        # 右侧：字段值（在 eleven wide column 中）
                        value_col = row.find('div', class_='eleven')
                        
                        if label_col and value_col:
                            # 从 less_span 中提取标签文本
                            label_span = label_col.find('span', class_='less_span')
                            if label_span:
                                label = label_span.get_text(strip=True).rstrip(':：')
                                value = value_col.get_text(strip=True)
                                
                                # 映射字段名
                                field_mapping = {
                                    '物業座數': 'building_count',
                                    '入伙年份': 'establish_year',
                                    '發展商': 'developer',
                                    '單位數目': 'units',
                                    '小學校網': 'primary_school',
                                    '中學校網': 'middle_school',
                                    '管理公司': 'management_company',
                                    '屋苑期數': 'phases',
                                    '實用面積範圍': 'area_range',
                                    '住客會所': 'facilities',
                                    '住客會所設施': 'facilities',
                                    '車位': 'parking_spaces',
                                    '樓齡': 'building_age',
                                    '成交活躍度': 'transaction_activity',
                                    '屋苑規模分類': 'estate_scale'
                                }
                                
                                field_key = field_mapping.get(label, label)
                                basic_info[field_key] = value
                
                static_info['basic_info'] = basic_info
                
                # 单独提取几个关键字段到顶层（为了向后兼容）
                if 'building_count' in basic_info:
                    static_info['building_count'] = basic_info['building_count']
                if 'establish_year' in basic_info:
                    static_info['establish_year'] = basic_info['establish_year']
                if 'developer' in basic_info:
                    static_info['developer'] = basic_info['developer']
                if 'units' in basic_info:
                    static_info['units'] = basic_info['units']
                if 'primary_school' in basic_info:
                    static_info['primary_school'] = basic_info['primary_school']
                if 'middle_school' in basic_info:
                    static_info['middle_school'] = basic_info['middle_school']
        
        return static_info
    
    def _extract_dynamic_info(self, soup: BeautifulSoup) -> Dict:
        """提取动态信息：楼价走势和租赁市场"""
        dynamic_info = {}
        
        # 提取最新楼价走势
        # 遍历所有th标签查找包含"最新樓價走勢"的标签
        price_th = None
        for th in soup.find_all('th'):
            if '最新樓價走勢' in th.get_text():
                price_th = th
                break
                
        if price_th:
            # 找到th所在的table
            price_table = price_th.find_parent('table')
            if price_table:
                price_trend = {}
                        
                # 查找tbody中的所有行
                tbody = price_table.find('tbody')
                if tbody:
                    for row in tbody.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                                    
                            # 映射字段名
                            field_mapping = {
                                '平均成交咀價': 'avg_sqft_price',
                                '成交量': 'transaction_volume',
                                '有盈利比例': 'profit_ratio',
                                '蝕讓比例': 'loss_ratio',
                                '一年轉手率(二手)': 'turnover_rate',
                                '一年前咀價': 'price_year_ago',
                                '放盤叫價': 'listing_price'
                            }
                                    
                            field_key = field_mapping.get(label, label)
                            price_trend[field_key] = value
                        
                if price_trend:
                    dynamic_info['price_trend'] = price_trend
        
        # 提取最新租赁市场
        # 遍历所有th标签查找包含"最新租賃市場"的标签
        rental_th = None
        for th in soup.find_all('th'):
            if '最新租賃市場' in th.get_text():
                rental_th = th
                break
                
        if rental_th:
            rental_table = rental_th.find_parent('table')
            if rental_table:
                rental_market = {}
                        
                tbody = rental_table.find('tbody')
                if tbody:
                    for row in tbody.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                                    
                            # 映射字段名
                            field_mapping = {
                                '平均成交咀租': 'avg_sqft_rent',
                                '成交量': 'transaction_volume',
                                '租務回報率': 'rental_yield',
                                '租務活躍率': 'rental_activity_rate',
                                '租盤叫價': 'rental_price'
                            }
                                    
                            field_key = field_mapping.get(label, label)
                            rental_market[field_key] = value
                        
                if rental_market:
                    dynamic_info['rental_market'] = rental_market
        
        return dynamic_info
    
    def scrape_all_estates(self, estates_mapping: Dict[str, str], use_threading: bool = True):
        """
        爬取所有屋苑的详细信息
        
        Args:
            estates_mapping: {屋苑名称: 屋苑ID} 字典
            use_threading: 是否使用多线程
        """
        total = len(estates_mapping)
        print("=" * 60)
        print(f"开始爬取 {total} 个屋苑的详细信息")
        print("=" * 60)
        
        if use_threading:
            self._scrape_with_threading(estates_mapping)
        else:
            self._scrape_sequential(estates_mapping)
        
        print("\n" + "=" * 60)
        print(f"爬取完成！")
        print(f"  静态信息: {len(self.static_data)} 个屋苑")
        print(f"  动态信息: {len(self.dynamic_data)} 个屋苑")
        print("=" * 60)
    
    def _scrape_sequential(self, estates_mapping: Dict[str, str]):
        """单线程顺序爬取"""
        total = len(estates_mapping)
        for i, (name, estate_id) in enumerate(estates_mapping.items(), 1):
            static_info, dynamic_info = self.fetch_estate_detail(name, estate_id)
            
            if static_info:
                self.static_data[estate_id] = static_info
            if dynamic_info:
                self.dynamic_data[estate_id] = dynamic_info
            
            if i % 10 == 0 or i == 1:
                print(f"进度: {i}/{total} ({i*100//total}%)")
            
            time.sleep(0.5)  # 礼貌延迟
    
    def _scrape_with_threading(self, estates_mapping: Dict[str, str]):
        """多线程并发爬取"""
        total = len(estates_mapping)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(self.fetch_estate_detail, name, estate_id): (name, estate_id)
                for name, estate_id in estates_mapping.items()
            }
            
            # 处理完成的任务
            for future in as_completed(futures):
                name, estate_id = futures[future]
                completed += 1
                
                try:
                    static_info, dynamic_info = future.result()
                    
                    if static_info:
                        self.static_data[estate_id] = static_info
                    if dynamic_info:
                        self.dynamic_data[estate_id] = dynamic_info
                    
                    if completed % 50 == 0 or completed == 1:
                        print(f"进度: {completed}/{total} ({completed*100//total}%)")
                    
                except Exception as e:
                    print(f"  ✗ 处理 {name} 时出错: {e}")
                
                time.sleep(0.1)
    
    def save_results(self, output_dir: str = '.'):
        """
        保存结果到文件
        
        Args:
            output_dir: 输出目录
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存静态信息到单个文件
        static_file = os.path.join(output_dir, 'estate_static_info.json')
        with open(static_file, 'w', encoding='utf-8') as f:
            json.dump(self.static_data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 静态信息已保存到: {static_file}")
        
        # 创建动态信息目录
        dynamic_dir = os.path.join(output_dir, 'estate_dynamic')
        os.makedirs(dynamic_dir, exist_ok=True)
        
        # 为每个屋苑保存单独的动态信息文件
        for estate_id, dynamic_info in self.dynamic_data.items():
            dynamic_file = os.path.join(dynamic_dir, f'{estate_id}.json')
            with open(dynamic_file, 'w', encoding='utf-8') as f:
                json.dump(dynamic_info, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 动态信息已保存到: {dynamic_dir}/ ({len(self.dynamic_data)} 个文件)")
    
    def print_sample_results(self, num_samples: int = 3):
        """打印部分结果样例"""
        print(f"\n{'='*60}")
        print(f"结果样例（前{num_samples}条）:")
        print(f"{'='*60}")
        
        for i, (estate_id, info) in enumerate(list(self.static_data.items())[:num_samples]):
            print(f"\n{i+1}. {info.get('name')} (ID: {estate_id})")
            print(f"   地址: {info.get('address', 'N/A')}")
            print(f"   坐标: {info.get('coordinates', 'N/A')}")
            print(f"   發展商: {info.get('developer', 'N/A')}")
            print(f"   入伙年份: {info.get('establish_year', 'N/A')}")
            
            if estate_id in self.dynamic_data:
                dynamic = self.dynamic_data[estate_id]
                if 'price_trend' in dynamic:
                    price = dynamic['price_trend'].get('avg_sqft_price', 'N/A')
                    print(f"   平均呎價: {price}")
                if 'rental_market' in dynamic:
                    rent = dynamic['rental_market'].get('avg_sqft_rent', 'N/A')
                    print(f"   平均呎租: {rent}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='屋苑详细信息爬虫')
    parser.add_argument('--input', type=str, default='estates_mapping.json', 
                       help='输入的屋苑映射文件路径')
    parser.add_argument('--workers', type=int, default=5, help='并发线程数（默认5）')
    parser.add_argument('--single-thread', action='store_true', help='使用单线程模式')
    parser.add_argument('--limit', type=int, default=None, help='限制爬取数量（用于测试）')
    
    args = parser.parse_args()
    
    # 创建爬虫实例
    scraper = EstateDetailScraper(max_workers=args.workers)
    
    # 加载屋苑映射
    print(f"正在加载屋苑映射文件: {args.input}")
    estates_mapping = scraper.load_estates_mapping(args.input)
    
    # 如果设置了限制，只爬取前N个
    if args.limit:
        estates_mapping = dict(list(estates_mapping.items())[:args.limit])
        print(f"测试模式：只爬取前 {args.limit} 个屋苑")
    
    # 爬取所有屋苑
    scraper.scrape_all_estates(estates_mapping, use_threading=not args.single_thread)
    
    # 打印样例结果
    scraper.print_sample_results(5)
    
    # 保存结果
    scraper.save_results()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n爬虫已被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
