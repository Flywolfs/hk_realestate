#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试屋苑详细信息爬虫 - 只爬取前3个屋苑
"""

from  import EstateDetailScraper
import json


def test_scraper():
    """测试爬虫功能"""
    print("="*60)
    print("测试屋苑详细信息爬虫 - 前3个屋苑")
    print("="*60)
    
    scraper = EstateDetailScraper(max_workers=2)
    
    # 加载映射文件
    estates_mapping = scraper.load_estates_mapping('estates_mapping.json')
    
    # 只测试前3个
    test_mapping = dict(list(estates_mapping.items())[:3])
    
    print(f"\n将测试以下屋苑:")
    for name, estate_id in test_mapping.items():
        print(f"  - {name} (ID: {estate_id})")
    
    # 爬取
    scraper.scrape_all_estates(test_mapping, use_threading=False)
    
    # 打印结果
    scraper.print_sample_results(3)
    
    # 保存到测试目录
    scraper.save_results('test_output')
    
    print("\n\n详细结果查看:")
    print("  静态信息: test_output/estate_static_info.json")
    print("  动态信息: test_output/estate_dynamic/")


if __name__ == '__main__':
    test_scraper()
