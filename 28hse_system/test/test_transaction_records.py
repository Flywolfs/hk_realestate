#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试成交记录爬虫 - 只爬取前3个屋苑"""

import json
from  import TransactionRecordScraper

def main():
    # 加载屋苑映射
    with open('estates_mapping.json', 'r', encoding='utf-8') as f:
        all_estates = json.load(f)
    
    # 只取前3个屋苑进行测试
    test_estates = dict(list(all_estates.items())[:3])
    
    print("="*60)
    print("测试成交记录爬虫 - 前3个屋苑")
    print("="*60)
    print("\n将测试以下屋苑:")
    for name, eid in test_estates.items():
        print(f"  - {name} (ID: {eid})")
    print("="*60)
    
    # 创建爬虫实例
    scraper = TransactionRecordScraper(max_workers=1)  # 测试时使用单线程
    
    # 爬取测试数据
    scraper.scrape_all(test_estates, output_dir='test_transaction_output')
    
    print("\n测试完成！")
    print("详细结果查看:")
    print("  买卖记录: test_transaction_output/buy/")
    print("  租房记录: test_transaction_output/rent/")

if __name__ == '__main__':
    main()
