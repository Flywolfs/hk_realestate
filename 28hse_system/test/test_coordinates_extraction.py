#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试坐标提取功能"""

import json
from  import EstateDetailScraper


def test_coordinates():
    """测试坐标提取"""
    print("=" * 70)
    print("测试坐标提取功能")
    print("=" * 70)
    
    # 创建爬虫实例
    scraper = EstateDetailScraper()
    
    # 测试几个不同的屋苑
    test_estates = [
        ("太古城", "1140"),
        ("黃埔花園", "3060"),
        ("嘉雲臺", "1000")
    ]
    
    print("\n正在提取坐标信息...\n")
    
    for estate_name, estate_id in test_estates:
        static_info, _ = scraper.fetch_estate_detail(estate_name, estate_id)
        
        if static_info:
            print(f"屋苑: {estate_name} (ID: {estate_id})")
            print(f"地址: {static_info.get('address', 'N/A')}")
            
            if 'coordinates' in static_info:
                coords = static_info['coordinates']
                print(f"✓ 坐标: 纬度 {coords['latitude']}, 经度 {coords['longitude']}")
            else:
                print("✗ 未找到坐标信息")
            
            print("-" * 70)
        else:
            print(f"✗ 无法获取 {estate_name} 的信息")
            print("-" * 70)
    
    # 验证坐标是否不同
    print("\n" + "=" * 70)
    print("验证不同屋苑的坐标是否不同")
    print("=" * 70)
    
    coordinates_list = []
    for estate_name, estate_id in test_estates:
        static_info, _ = scraper.fetch_estate_detail(estate_name, estate_id)
        if static_info and 'coordinates' in static_info:
            coords = static_info['coordinates']
            coord_tuple = (coords['latitude'], coords['longitude'])
            coordinates_list.append((estate_name, coord_tuple))
    
    if len(coordinates_list) >= 2:
        # 检查是否所有坐标都相同
        first_coord = coordinates_list[0][1]
        all_same = all(coord == first_coord for _, coord in coordinates_list)
        
        if all_same:
            print("⚠️  警告：所有屋苑的坐标都相同！")
            print(f"   坐标值: {first_coord}")
        else:
            print("✓ 不同屋苑有不同的坐标（正确！）")
            for name, coord in coordinates_list:
                print(f"   {name}: {coord}")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == '__main__':
    test_coordinates()
