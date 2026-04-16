#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试增量爬取模式"""

import json
import os


def test_incremental_mode():
    """测试增量模式功能"""
    
    print("=" * 70)
    print("测试增量爬取模式")
    print("=" * 70)
    
    # 检查现有数据
    data_dir = '28hse/transaction_records'
    
    print(f"\n📁 检查现有数据目录: {data_dir}")
    
    if not os.path.exists(data_dir):
        print(f"❌ 目录不存在: {data_dir}")
        print("   请确保已有爬取的数据")
        return
    
    # 检查buy和rent文件夹
    buy_dir = os.path.join(data_dir, 'buy')
    rent_dir = os.path.join(data_dir, 'rent')
    
    buy_files = []
    rent_files = []
    
    if os.path.exists(buy_dir):
        buy_files = [f for f in os.listdir(buy_dir) if f.endswith('.json')]
    
    if os.path.exists(rent_dir):
        rent_files = [f for f in os.listdir(rent_dir) if f.endswith('.json')]
    
    print(f"\n📊 现有数据统计:")
    print(f"   买卖记录: {len(buy_files)} 个文件")
    print(f"   租赁记录: {len(rent_files)} 个文件")
    
    # 检查几个示例文件的最新日期
    print(f"\n🔍 检查示例文件的最新记录日期:")
    
    sample_files = buy_files[:3] if len(buy_files) >= 3 else buy_files
    
    for filename in sample_files:
        filepath = os.path.join(buy_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            transactions = data.get('transactions', [])
            if transactions:
                latest_date = transactions[0].get('date', 'N/A')
                estate_id = data.get('estate_id', 'N/A')
                total = len(transactions)
                
                print(f"   ID={estate_id}: 最新日期={latest_date}, 共{total}条记录")
        except Exception as e:
            print(f"   ❌ 读取失败 {filename}: {e}")
    
    print("\n" + "=" * 70)
    print("增量模式使用说明")
    print("=" * 70)
    
    print("\n1. 测试增量模式（处理前3个屋苑）:")
    print("   python3 scrape_transaction_records.py \\")
    print("     --incremental \\")
    print("     --data-dir 28hse/transaction_records \\")
    print("     --limit 3")
    
    print("\n2. 全量增量更新（所有屋苑）:")
    print("   python3 scrape_transaction_records.py \\")
    print("     --incremental \\")
    print("     --data-dir 28hse/transaction_records")
    
    print("\n3. 增量更新差异屋苑:")
    print("   python3 scrape_transaction_records.py \\")
    print("     --incremental \\")
    print("     --data-dir 28hse/transaction_records \\")
    print("     --mapping estates_diff_mapping.json \\")
    print("     --output transaction_records_new")
    
    print("\n💡 增量模式优势:")
    print("   - 只爬取比现有数据更新的记录")
    print("   - 自动合并新旧数据并去重")
    print("   - 减少网络请求，提高效率")
    print("   - 保持数据按时间从新到旧排序")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_incremental_mode()
