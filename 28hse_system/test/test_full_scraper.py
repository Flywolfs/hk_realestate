#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完整爬虫 - 爬取前20页验证功能
"""

from  import EstateIDScraper
import json


def test_full_scraper():
    """测试完整爬虫功能"""
    print("="*60)
    print("测试完整爬虫 - 爬取前20页")
    print("="*60)
    
    scraper = EstateIDScraper(max_workers=3)
    
    # 测试爬取前20页
    print("\n开始爬取...")
    for page in range(1, 21):
        page_num, count = scraper.fetch_estate_page(page)
        if page % 5 == 0 or page == 1:
            print(f"进度: {page}/20 - 本页新增: {count} 个 - 总计: {len(scraper.estate_mapping)} 个")
    
    print("\n" + "="*60)
    print(f"测试完成！共发现 {len(scraper.estate_mapping)} 个不重复的屋苑")
    print("="*60)
    
    # 打印部分结果
    print("\n结果样例（前20条）:")
    for i, (name, estate_id) in enumerate(list(scraper.estate_mapping.items())[:20]):
        info = scraper.estate_full_info.get(estate_id, {})
        district = info.get('district', '未知')
        print(f"{i+1:2d}. {name:25s} → ID: {estate_id:6s} (地区: {district})")
    
    # 保存测试结果
    with open('test_full_result.json', 'w', encoding='utf-8') as f:
        json.dump(scraper.estate_mapping, f, ensure_ascii=False, indent=2)
    
    with open('test_full_result_detailed.json', 'w', encoding='utf-8') as f:
        json.dump(scraper.estate_full_info, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试结果已保存到: test_full_result.json 和 test_full_result_detailed.json")
    
    # 统计信息
    districts = {}
    for info in scraper.estate_full_info.values():
        district = info.get('district', '未知')
        districts[district] = districts.get(district, 0) + 1
    
    print(f"\n地区分布（前10个）:")
    for district, count in sorted(districts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {district:15s}: {count:3d} 个屋苑")
    
    return scraper.estate_mapping


if __name__ == '__main__':
    test_full_scraper()
