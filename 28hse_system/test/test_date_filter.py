#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试日期过滤功能"""

import json
from  import TransactionRecordScraper

def main():
    # 加载屋苑映射
    with open('estates_mapping.json', 'r', encoding='utf-8') as f:
        all_estates = json.load(f)
    
    # 只取第1个屋苑进行测试
    test_estates = dict(list(all_estates.items())[:1])
    
    print("="*60)
    print("测试日期过滤功能 - 只爬取2025年及之后的记录")
    print("="*60)
    print("\n将测试以下屋苑:")
    for name, eid in test_estates.items():
        print(f"  - {name} (ID: {eid})")
    print("="*60)
    
    # 创建爬虫实例
    scraper = TransactionRecordScraper(max_workers=1)
    
    # 测试日期过滤函数
    print("\n测试日期判断函数:")
    test_dates = [
        "2026-02-03",  # 应该返回True
        "2025-12-31",  # 应该返回True
        "2025-01-01",  # 应该返回True
        "2024-12-31",  # 应该返回False
        "2024-01-01",  # 应该返回False
        "2023-06-15",  # 应该返回False
    ]
    
    for date_str in test_dates:
        result = scraper.is_date_after_2025(date_str)
        status = "✓ 保留" if result else "✗ 过滤"
        print(f"  {date_str} -> {status}")
    
    print("\n" + "="*60)
    print("开始爬取测试")
    print("="*60 + "\n")
    
    # 爬取测试数据
    scraper.scrape_all(test_estates, output_dir='test_date_filter_output')
    
    # 查看结果
    print("\n" + "="*60)
    print("查看爬取结果")
    print("="*60 + "\n")
    
    for name, eid in test_estates.items():
        # 检查买卖记录
        buy_file = f'test_date_filter_output/buy/{eid}.json'
        try:
            with open(buy_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"买卖记录 ({name}):")
                print(f"  总记录数: {data['total_records']}")
                if data['transactions']:
                    # 显示前3条记录的日期
                    print(f"  前3条记录的日期:")
                    for i, trans in enumerate(data['transactions'][:3], 1):
                        print(f"    {i}. {trans.get('date', 'N/A')}")
        except FileNotFoundError:
            print(f"买卖记录文件不存在: {buy_file}")
        
        print()
        
        # 检查租房记录
        rent_file = f'test_date_filter_output/rent/{eid}.json'
        try:
            with open(rent_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"租房记录 ({name}):")
                print(f"  总记录数: {data['total_records']}")
                if data['transactions']:
                    # 显示前3条记录的日期
                    print(f"  前3条记录的日期:")
                    for i, trans in enumerate(data['transactions'][:3], 1):
                        print(f"    {i}. {trans.get('date', 'N/A')}")
        except FileNotFoundError:
            print(f"租房记录文件不存在: {rent_file}")
    
    print("\n测试完成！")

if __name__ == '__main__':
    main()
