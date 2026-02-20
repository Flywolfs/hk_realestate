#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中原地产屋苑基本信息爬取脚本
通过API获取香港所有屋苑的基本信息
"""

import requests
import json
import time
import sys
import urllib3
import ssl
from datetime import datetime
from typing import Dict, List, Any, Optional
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


class CentanetEstateScraper:
    """中原地产屋苑信息爬虫"""
    
    def __init__(self, request_interval: float = 1.0, max_retries: int = 3, max_estate_count: int = None):
        """
        初始化爬虫
        
        Args:
            request_interval: 请求间隔时间（秒），默认1.0秒
            max_retries: 最大重试次数，默认3次
            max_estate_count: 最大爬取屋苑数量（必须提供）
        """
        
        if max_estate_count is None:
            raise ValueError("max_estate_count 参数必须提供")
        self.api_url = "https://hk.centanet.com/findproperty/api/estate/Search"
        self.session = requests.Session()
        self.request_interval = request_interval
        self.max_retries = max_retries
        
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
        
        # 存储结果
        self.all_data: List[Dict[str, Any]] = []
        self.total_count: int = 0
        self.max_estate_count = max_estate_count
        
    def fetch_page(self, offset: int, size: int = 100) -> Optional[Dict[str, Any]]:
        """
        获取指定偏移量的数据
        
        Args:
            offset: 分页偏移量
            size: 每次请求的数据量（最大100）
            
        Returns:
            API响应数据，失败返回None
        """
        payload = {
            "size": size,
            "sort": "Ranking",
            "order": "Ascending",
            "offset": offset,
            "pageSource": "search",
            "adsource": "DMK-G0181"
        }
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.api_url,
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
                    print(f"  ⚠ 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    print(f"  等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"  ✗ 偏移量 {offset} 请求失败，已达最大重试次数: {e}")
                    return None
                    
            except json.JSONDecodeError as e:
                print(f"  ✗ JSON解析失败: {e}")
                return None
                
        return None
    
    def get_total_count(self) -> int:
        """
        获取屋苑总数
        
        Returns:
            屋苑总数
        """
        data = self.fetch_page(offset=0, size=1)
        if data and 'count' in data:
            return data['count']
        return 0
    
    def scrape_all_estates(self):
        """爬取所有屋苑信息"""
        print("=" * 60)
        print("开始爬取中原地产屋苑数据")
        print("=" * 60)
        
        # 首先获取总数
        print("\n正在获取屋苑总数...")
        self.total_count = self.get_total_count()
        
        if self.total_count == 0:
            print("✗ 无法获取屋苑总数，请检查网络连接或API是否可用")
            return
        
        # 确定实际要爬取的数量
        actual_count = self.max_estate_count
        print(f"✓ 检测到 {self.total_count} 个屋苑（API返回值）")
        print(f"  用户设置最大爬取: {self.max_estate_count} 条")
        print(f"  实际将爬取: {actual_count} 条\n")
        
        # 计算需要的请求次数
        page_size = 100
        total_requests = (actual_count + page_size - 1) // page_size
        
        print(f"计划发起 {total_requests} 次请求，每次获取 {page_size} 条数据\n")
        print(f"请求间隔: {self.request_interval} 秒\n")
        
        # 分页获取所有数据
        successful_requests = 0
        failed_requests = 0
        
        for request_num in range(total_requests):
            offset = request_num * page_size
            
            # 进度显示
            progress = (request_num + 1) * 100 // total_requests
            print(f"\r进度: {request_num + 1}/{total_requests} ({progress}%) - "
                  f"已获取: {len(self.all_data)} 条", end='', flush=True)
            
            data = self.fetch_page(offset=offset, size=page_size)
            
            if data:
                # 合并data数组
                if 'data' in data and isinstance(data['data'], list):
                    self.all_data.extend(data['data'])
                    successful_requests += 1
                else:
                    print(f"\n  ⚠ 偏移量 {offset} 响应中没有有效的data字段")
                    failed_requests += 1
            else:
                failed_requests += 1
            
            # 请求间隔（最后一次不需要等待）
            if request_num < total_requests - 1:
                time.sleep(self.request_interval)
        
        print(f"\n\n{'='*60}")
        print(f"爬取完成！")
        print(f"成功请求: {successful_requests}/{total_requests}")
        print(f"失败请求: {failed_requests}/{total_requests}")
        print(f"获取数据: {len(self.all_data)} 条")
        print(f"{'='*60}")
    
    def save_results(self, output_file: Optional[str] = None) -> str:
        """
        保存结果到JSON文件
        
        Args:
            output_file: 输出文件路径，默认自动生成
            
        Returns:
            实际保存的文件路径
        """
        if output_file is None:
            # 自动生成文件名: estate_info_[YYYYMMDD].json
            today = datetime.now().strftime('%Y%m%d')
            output_file = f"estate_info_{today}.json"
        
        # 构建输出数据结构
        output_data = {
            "count": self.total_count,
            "data": self.all_data
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 数据已保存到: {output_file}")
        print(f"  - 总数: {output_data['count']}")
        print(f"  - 实际数据条数: {len(output_data['data'])}")
        
        return output_file
    
    def print_sample_results(self, num_samples: int = 5):
        """打印部分结果样例"""
        if not self.all_data:
            print("没有数据可显示")
            return
            
        print(f"\n{'='*60}")
        print(f"数据样例（前{num_samples}条）:")
        print(f"{'='*60}")
        
        for i, item in enumerate(self.all_data[:num_samples]):
            print(f"\n{i+1}. {json.dumps(item, ensure_ascii=False, indent=2)}")
    
    def get_data(self) -> List[Dict[str, Any]]:
        """
        获取所有屋苑数据
        
        Returns:
            屋苑数据列表
        """
        return self.all_data


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='中原地产屋苑信息爬虫')
    parser.add_argument('--interval', type=float, default=1.0, 
                        help='请求间隔时间（秒），默认1.0')
    parser.add_argument('--retries', type=int, default=3, 
                        help='最大重试次数，默认3')
    parser.add_argument('--output', type=str, default=None, 
                        help='输出文件名（默认自动生成: estate_info_YYYYMMDD.json）')
    parser.add_argument('--sample', type=int, default=5, 
                        help='显示样例数据条数，默认5')
    parser.add_argument('--max-count', type=int, required=True,
                        help='最大爬取屋苑数量（必须提供）')
    
    args = parser.parse_args()
    
    # 创建爬虫实例
    scraper = CentanetEstateScraper(
        request_interval=args.interval,
        max_retries=args.retries,
        max_estate_count=args.max_count
    )
    
    # 爬取所有屋苑
    scraper.scrape_all_estates()
    
    if len(scraper.get_data()) == 0:
        print("\n未获取到任何数据，请检查网络连接或API状态")
        sys.exit(1)
    
    # 打印样例结果
    scraper.print_sample_results(args.sample)
    
    # 保存结果
    scraper.save_results(args.output)
    
    return scraper.get_data()


if __name__ == '__main__':
    try:
        estate_data = main()
        print(f"\n总计获取: {len(estate_data)} 条屋苑数据")
        print("\n使用方法:")
        print("  python scrape_centanet_estates.py --max-count 10000       # 必须指定爬取数量")
        print("  python scrape_centanet_estates.py --max-count 5000 --interval 2.0")
        print("  python scrape_centanet_estates.py --max-count 10000 --output my.json")
        
    except KeyboardInterrupt:
        print("\n\n爬虫已被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
