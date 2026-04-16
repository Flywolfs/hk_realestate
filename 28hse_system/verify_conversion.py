#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证转换后的数据"""

import json
import os
import random


def verify_conversion():
    """验证数据转换"""
    
    print("=" * 70)
    print("数据转换验证工具")
    print("=" * 70)
    
    # 买卖记录验证
    print("\n📊 买卖记录验证")
    print("-" * 70)
    
    buy_dir = '28hse/transaction_records_trans/buy'
    buy_files = [f for f in os.listdir(buy_dir) if f.endswith('.json')]
    
    if buy_files:
        # 随机选择3个文件验证
        sample_files = random.sample(buy_files, min(3, len(buy_files)))
        
        for filename in sample_files:
            filepath = os.path.join(buy_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"\n文件: {filename}")
            print(f"屋苑ID: {data['estate_id']}")
            print(f"记录数: {data['total_records']}")
            
            if data['transactions']:
                t = data['transactions'][0]
                print(f"示例记录:")
                print(f"  单位: {t.get('unit_location', 'N/A')}")
                print(f"  日期: {t.get('date', 'N/A')}")
                
                if 'area' in t and isinstance(t['area'], (int, float)):
                    print(f"  ✓ 面积: {t['area']} 呎 (原始: {t.get('area_text', 'N/A')})")
                
                if 'total_price' in t and isinstance(t['total_price'], (int, float)):
                    print(f"  ✓ 总价: {t['total_price']:,} 元 (原始: {t.get('total_price_text', 'N/A')})")
                
                if 'price_per_sqft' in t and isinstance(t['price_per_sqft'], (int, float)):
                    print(f"  ✓ 尺价: {t['price_per_sqft']:,} 元 (原始: {t.get('price_per_sqft_text', 'N/A')})")
                
                if 'profit_loss_rate' in t:
                    if isinstance(t['profit_loss_rate'], (int, float)):
                        print(f"  ✓ 盈利率: {t['profit_loss_rate']:.2%} (原始: {t.get('profit_loss_rate_text', 'N/A')})")
                    else:
                        print(f"  - 盈利率: 无数据")
    
    # 租赁记录验证
    print("\n" + "=" * 70)
    print("📊 租赁记录验证")
    print("-" * 70)
    
    rent_dir = '28hse/transaction_records_trans/rent'
    rent_files = [f for f in os.listdir(rent_dir) if f.endswith('.json')]
    
    if rent_files:
        # 随机选择3个文件验证
        sample_files = random.sample(rent_files, min(3, len(rent_files)))
        
        for filename in sample_files:
            filepath = os.path.join(rent_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"\n文件: {filename}")
            print(f"屋苑ID: {data['estate_id']}")
            print(f"记录数: {data['total_records']}")
            
            if data['transactions']:
                t = data['transactions'][0]
                print(f"示例记录:")
                print(f"  单位: {t.get('unit_location', 'N/A')}")
                print(f"  日期: {t.get('date', 'N/A')}")
                
                if 'area' in t and isinstance(t['area'], (int, float)):
                    print(f"  ✓ 面积: {t['area']} 呎 (原始: {t.get('area_text', 'N/A')})")
                
                if 'total_rent' in t and isinstance(t['total_rent'], (int, float)):
                    print(f"  ✓ 租金: {t['total_rent']:,} 元 (原始: {t.get('total_rent_text', 'N/A')})")
                
                if 'rent_per_sqft' in t and isinstance(t['rent_per_sqft'], (int, float)):
                    print(f"  ✓ 尺租: {t['rent_per_sqft']:,} 元 (原始: {t.get('rent_per_sqft_text', 'N/A')})")
    
    print("\n" + "=" * 70)
    print("验证完成！")
    print("=" * 70)


if __name__ == '__main__':
    verify_conversion()
