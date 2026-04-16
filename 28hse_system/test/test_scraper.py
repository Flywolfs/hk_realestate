#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试爬虫 - 只爬取前3页验证功能
"""

from  import EstateIDScraper
import json


def test_scraper():
    """测试爬虫功能"""
    print("="*60)
    print("测试爬虫 - 只爬取前3页")
    print("="*60)
    
    scraper = EstateIDScraper(max_workers=2)
    
    # 只爬取前3页
    total_count = 0
    for page in range(1, 4):
        print(f"\n正在爬取第 {page} 页...")
        page_num, count = scraper.fetch_estate_page(page)
        total_count += count
        print(f"  ✓ 第{page}页: 发现 {count} 个屋苑")
    
    print("\n" + "="*60)
    print(f"测试完成！共发现 {len(scraper.estate_mapping)} 个不重复的屋苑")
    print("="*60)
    
    # 打印部分结果
    print("\n结果样例:")
    for i, (name, estate_id) in enumerate(list(scraper.estate_mapping.items())[:10]):
        info = scraper.estate_full_info.get(estate_id, {})
        area = info.get('area', '未知')
        print(f"{i+1:2d}. {name:20s} → ID: {estate_id:6s} (区域: {area})")
    
    # 保存测试结果
    with open('test_result.json', 'w', encoding='utf-8') as f:
        json.dump(scraper.estate_mapping, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试结果已保存到: test_result.json")
    
    return scraper.estate_mapping


if __name__ == '__main__':
    test_scraper()
