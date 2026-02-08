#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
私人屋苑楼宇ID爬取脚本
通过爬取屋苑成交页面获取全香港所有私人屋苑的名称和ID映射
"""

import requests
import re
import json
from bs4 import BeautifulSoup
from typing import Dict, Set, Tuple
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys


class EstateIDScraper:
    """屋苑ID爬虫"""
    
    def __init__(self, max_workers: int = 5):
        """
        初始化爬虫
        
        Args:
            max_workers: 并发线程数，默认5（建议不要设置太高以避免被封IP）
        """
        self.base_url = "https://www.28hse.com"
        self.estate_list_url = f"{self.base_url}/estate/"
        self.estate_search_api = f"{self.base_url}/estate/dosearch"  # 正确的分页API
        self.buy_url = f"{self.base_url}/buy"
        self.session = requests.Session()
        self.max_workers = max_workers
        
        # 设置请求头，模拟浏览器
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.base_url,
            'Connection': 'keep-alive'
        })
        
        # 存储结果
        self.estate_mapping = {}  # {楼宇ID: 楼宇名称} - 修改为以ID为key避免重名问题
        self.estate_full_info = {}  # {楼宇ID: {name, district, url, type}}
        
    def get_total_pages(self) -> int:
        """
        获取屋苑列表的总页数
        
        Returns:
            总页数
        """
        try:
            response = self.session.get(self.estate_list_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 查找分页信息
            # 方法1: 查找最后一页的链接
            pagination = soup.find('ul', class_='pagination') or soup.find('div', class_='pagination')
            if pagination:
                page_links = pagination.find_all('a', href=re.compile(r'\?page=\d+'))
                if page_links:
                    max_page = 1
                    for link in page_links:
                        match = re.search(r'page=(\d+)', link.get('href', ''))
                        if match:
                            page_num = int(match.group(1))
                            max_page = max(max_page, page_num)
                    return max_page
            
            # 方法2: 查找页面上显示的总数信息
            # 假设每页15个屋苑，总共11150个
            total_text = soup.find(text=re.compile(r'共\s*[\d,]+\s*個'))
            if total_text:
                match = re.search(r'([\d,]+)', total_text)
                if match:
                    total = int(match.group(1).replace(',', ''))
                    return (total + 14) // 15  # 向上取整
            
            # 默认值：基于已知的11150个屋苑
            print("  ⚠ 无法从页面获取总页数，使用默认值")
            return 744  # 11150 / 15 ≈ 744
            
        except Exception as e:
            print(f"  ✗ 获取总页数失败: {e}")
            return 744  # 返回默认值
    
    def fetch_estate_page(self, page_num: int) -> Tuple[int, int]:
        """
        获取指定页的屋苑列表
        使用POST API请求，因为GET请求不支持分页
        
        Args:
            page_num: 页码
            
        Returns:
            (页码, 提取到的屋苑数量)
        """
        count = 0
        
        try:
            # 使用POST请求到 /estate/dosearch
            # 关键发现：API期望参数被包装在 form_data 字段中
            form_params = {
                'page': str(page_num),
                'searchText': '',
                'myfav': '',
                'myvisited': '',
                'item_ids': '',
                'sortBy': '',  # 空值或DESC
                'is_grid_mode': '',
                'channel': 'residential',  # 住宅
                'channel_by_text': '0',
                'district': '',
                'district_by_text': '0',
                'type': '',
                'type_by_text': '0',
                'landreg_sqprice': '',
                'landreg_sqprice_by_text': '0',
                'estate_age': '',
                'estate_age_by_text': '0'
            }
            
            # 将参数序列化为URL编码字符串
            from urllib.parse import urlencode
            form_data_str = urlencode(form_params)
            
            # API期望的格式：{form_data: "page=2&searchText=&..."}
            data = {
                'form_data': form_data_str
            }
            
            # 设置POST请求头
            headers = self.session.headers.copy()
            headers.update({
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Origin': self.base_url,
                'Referer': f'{self.estate_list_url}?page={page_num}'
            })
            
            response = self.session.post(self.estate_search_api, data=data, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 解析JSON响应
            json_data = response.json()
            
            if json_data.get('status') == 1 and json_data.get('result') == 1:
                # 响应中包含HTML内容
                results = json_data.get('data', {}).get('results', {})
                html_content = results.get('showHtml', '')  # 正确的key是showHtml，不是resultContentHtml
                
                if html_content:
                    count = self._parse_estate_html(html_content)
            else:
                print(f"  ⚠ 第{page_num}页API返回状态异常: {json_data}")
            
            return (page_num, count)
            
        except Exception as e:
            print(f"  ✗ 第{page_num}页请求失败: {e}")
            return (page_num, 0)
    
    def _parse_estate_html(self, html_content: str) -> int:
        """
        解析HTML内容提取屋苑信息
        
        Args:
            html_content: HTML内容
            
        Returns:
            提取到的屋苑数量
        """
        if not html_content:
            return 0
        
        soup = BeautifulSoup(html_content, 'html.parser')
        count = 0
        
        # 查找 div.item 元素，从 attr1 属性获取ID
        estate_items = soup.find_all('div', class_='item', attrs={'attr1': True})
        
        for item in estate_items:
            estate_id = item.get('attr1', '')
            
            # 从item中查找屋苑名称
            name_link = item.find('a', class_='header')
            if name_link:
                estate_name = name_link.get_text(strip=True)
                href = name_link.get('href', '')
                
                if estate_name and estate_id and estate_id not in self.estate_full_info:
                    # 从meta中获取地区信息
                    meta = item.find('div', class_='meta')
                    district = meta.get_text(strip=True) if meta else ''
                    
                    self.estate_mapping[estate_id] = estate_name  # 修改：以ID为key，名称为value
                    self.estate_full_info[estate_id] = {
                        'name': estate_name,
                        'id': estate_id,
                        'area': '',
                        'district': district,
                        'url': f"{self.base_url}{href}" if href else '',
                        'type': '屋苑'
                    }
                    count += 1
        
        return count
    
    def fetch_buy_page_estates(self, page_num: int = 1, max_pages: int = 100) -> int:
        """
        从买房页面获取屋苑信息（作为补充数据源）
        
        Args:
            page_num: 起始页码
            max_pages: 最大爬取页数
            
        Returns:
            提取到的屋苑总数
        """
        total_count = 0
        
        for page in range(page_num, page_num + max_pages):
            url = f"{self.buy_url}?page={page}"
            
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 查找屋苑链接
                estate_links = soup.find_all('a', href=re.compile(r'/buy/apartment/[^/]+/[^/]+/[^/]+/c\d+'))
                
                page_count = 0
                for link in estate_links:
                    href = link.get('href', '')
                    estate_name = link.get_text(strip=True)
                    
                    # 提取楼宇ID
                    match = re.search(r'/c(\d+)', href)
                    if match:
                        estate_id = match.group(1)
                        
                        if estate_name and estate_id and estate_id not in self.estate_full_info:
                            # 检查是否为私人屋苑
                            parent = link.find_parent(['div', 'article', 'li'])
                            if parent and '私人屋苑' in parent.get_text():
                                area_match = re.search(r'/a(\d+)/', href)
                                area = '未知'
                                if area_match:
                                    area_code = area_match.group(1)
                                    area_map = {'1': '香港島', '2': '九龍', '3': '新界', '170': '離島'}
                                    area = area_map.get(area_code, '其他')
                                
                                self.estate_mapping[estate_id] = estate_name  # 修改：以ID为key，名称为value
                                self.estate_full_info[estate_id] = {
                                    'name': estate_name,
                                    'id': estate_id,
                                    'area': area,
                                    'url': f"{self.base_url}{href}",
                                    'type': '私人屋苑'
                                }
                                page_count += 1
                
                total_count += page_count
                
                if page_count == 0:
                    break  # 如果本页没有新数据，停止爬取
                
                time.sleep(0.5)  # 短暂延迟
                
            except Exception as e:
                print(f"  ✗ 买房页面第{page}页请求失败: {e}")
                break
        
        return total_count
    
    def scrape_all_estates(self, use_threading: bool = True):
        """
        爬取所有屋苑信息
            
        Args:
            use_threading: 是否使用多线程（默认True，速度更快）
        """
        print("="*60)
        print("开始爬取私人屋苑数据")
        print("="*60)
            
        # 获取总页数
        print("\n正在获取总页数...")
        total_pages = self.get_total_pages()
        print(f"✓ 检测到约 {total_pages} 页屋苑数据\n")
            
        if use_threading:
            # 多线程爬取
            print(f"使用 {self.max_workers} 个线程并发爬取...\n")
            self._scrape_with_threading(total_pages)
        else:
            # 单线程爬取
            print("使用单线程顺序爬取...\n")
            self._scrape_sequential(total_pages)
            
        print("\n" + "="*60)
        print(f"爬取完成！共发现 {len(self.estate_mapping)} 个不重复的私人屋苑")
        print("="*60)
        
    def _scrape_sequential(self, total_pages: int):
        """单线程顺序爬取"""
        for page in range(1, total_pages + 1):
            page_num, count = self.fetch_estate_page(page)
                
            if page % 10 == 0 or page == 1:
                print(f"进度: {page}/{total_pages} ({page*100//total_pages}%) - "
                      f"本页新增: {count} 个 - 总计: {len(self.estate_mapping)} 个")
                
            time.sleep(0.5)  # 礼貌延迟
        
    def _scrape_with_threading(self, total_pages: int):
        """多线程并发爬取"""
        completed = 0
        last_print = 0
            
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = {executor.submit(self.fetch_estate_page, page): page 
                      for page in range(1, total_pages + 1)}
                
            # 处理完成的任务
            for future in as_completed(futures):
                page_num, count = future.result()
                completed += 1
                    
                # 每完成10页或每10%进度打印一次
                if completed % 10 == 0 or (completed * 100 // total_pages) > last_print:
                    last_print = completed * 100 // total_pages
                    print(f"进度: {completed}/{total_pages} ({last_print}%) - "
                          f"总计: {len(self.estate_mapping)} 个屋苑")
                    
                time.sleep(0.1)  # 短暂延迟
    
    def save_results(self, output_file: str = 'estates_mapping.json'):
        """
        保存结果到JSON文件
        
        Args:
            output_file: 输出文件路径
        """
        # 保存简单的ID-名称映射
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.estate_mapping, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 楼宇ID-名称映射已保存到: {output_file}")
        
        # 保存详细信息
        detailed_file = output_file.replace('.json', '_detailed.json')
        with open(detailed_file, 'w', encoding='utf-8') as f:
            json.dump(self.estate_full_info, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 详细信息已保存到: {detailed_file}")
    
    def print_sample_results(self, num_samples: int = 10):
        """打印部分结果样例"""
        print(f"\n{'='*60}")
        print(f"结果样例（前{num_samples}条）:")
        print(f"{'='*60}")
        
        for i, (estate_id, name) in enumerate(list(self.estate_mapping.items())[:num_samples]):
            info = self.estate_full_info.get(estate_id, {})
            district = info.get('district', '未知')
            print(f"{i+1:2d}. {name:20s} → ID: {estate_id:6s} (区域: {district})")
    
    def get_mapping(self) -> Dict[str, str]:
        """
        获取楼宇ID-名称映射
        
        Returns:
            {楼宇ID: 楼宇名称} 字典
        """
        return self.estate_mapping


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='私人屋苑爬虫')
    parser.add_argument('--workers', type=int, default=5, help='并发线程数（默认5）')
    parser.add_argument('--single-thread', action='store_true', help='使用单线程模式')
    parser.add_argument('--output', type=str, default='estates_mapping.json', help='输出文件名')
    
    args = parser.parse_args()
    
    # 创建爬虫实例
    scraper = EstateIDScraper(max_workers=args.workers)
    
    # 爬取所有屋苑
    scraper.scrape_all_estates(use_threading=not args.single_thread)
    
    # 打印样例结果
    scraper.print_sample_results(20)
    
    # 保存结果
    scraper.save_results(args.output)
    
    # 返回映射
    return scraper.get_mapping()


if __name__ == '__main__':
    try:
        estate_mapping = main()
        
        print(f"\n总计: {len(estate_mapping)} 个不重复的私人屋苑")
        print("\n使用方法:")
        print("  python scrape_estates.py                    # 默认5线程并发")
        print("  python scrape_estates.py --workers 10       # 10线程并发")
        print("  python scrape_estates.py --single-thread    # 单线程模式")
        print("  python scrape_estates.py --output my.json   # 自定义输出文件")
    except KeyboardInterrupt:
        print("\n\n爬虫已被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
