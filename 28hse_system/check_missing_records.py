#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查哪些屋苑ID在成交记录中没有出现
输出缺失买卖记录和租房记录的屋苑ID列表
"""

import json
import os
from typing import Dict, List, Set


def load_estates_mapping(json_path: str) -> Dict[str, str]:
    """加载屋苑名称-ID映射"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 加载屋苑映射文件失败: {e}")
        return {}


def get_existing_ids(folder_path: str) -> Set[str]:
    """
    获取指定文件夹中已存在的屋苑ID集合
    
    Args:
        folder_path: 文件夹路径（如 'transaction_records/buy'）
        
    Returns:
        存在的屋苑ID集合（不含.json后缀）
    """
    existing_ids = set()
    
    if not os.path.exists(folder_path):
        print(f"⚠️  文件夹不存在: {folder_path}")
        return existing_ids
    
    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            # 提取ID（去掉.json后缀）
            estate_id = filename[:-5]
            existing_ids.add(estate_id)
    
    return existing_ids


def check_missing_records(
    estates_mapping: Dict[str, str],
    transaction_records_dir: str = 'transaction_records'
) -> Dict:
    """
    检查缺失的成交记录
    
    Args:
        estates_mapping: {屋苑名称: 屋苑ID}
        transaction_records_dir: 成交记录根目录
        
    Returns:
        检查结果字典
    """
    buy_folder = os.path.join(transaction_records_dir, 'buy')
    rent_folder = os.path.join(transaction_records_dir, 'rent')
    
    # 获取已存在的ID
    buy_existing_ids = get_existing_ids(buy_folder)
    rent_existing_ids = get_existing_ids(rent_folder)
    
    # 获取所有应该存在的ID
    all_ids = set(estates_mapping.values())
    
    # 计算缺失的ID
    missing_buy_ids = all_ids - buy_existing_ids
    missing_rent_ids = all_ids - rent_existing_ids
    missing_both_ids = missing_buy_ids & missing_rent_ids
    
    # 构建结果
    result = {
        'total_estates': len(all_ids),
        'buy': {
            'existing': len(buy_existing_ids),
            'missing': len(missing_buy_ids),
            'missing_ids': sorted(list(missing_buy_ids))
        },
        'rent': {
            'existing': len(rent_existing_ids),
            'missing': len(missing_rent_ids),
            'missing_ids': sorted(list(missing_rent_ids))
        },
        'both_missing': {
            'count': len(missing_both_ids),
            'ids': sorted(list(missing_both_ids))
        }
    }
    
    return result


def print_results(result: Dict, estates_mapping: Dict[str, str]):
    """打印检查结果"""
    
    print("=" * 70)
    print("屋苑成交记录缺失检查报告")
    print("=" * 70)
    
    print(f"\n📊 总体统计:")
    print(f"  屋苑总数: {result['total_estates']}")
    
    print(f"\n📈 买卖记录 (buy):")
    print(f"  已存在: {result['buy']['existing']} 个")
    print(f"  缺失: {result['buy']['missing']} 个")
    print(f"  完成率: {result['buy']['existing'] / result['total_estates'] * 100:.1f}%")
    
    print(f"\n📈 租房记录 (rent):")
    print(f"  已存在: {result['rent']['existing']} 个")
    print(f"  缺失: {result['rent']['missing']} 个")
    print(f"  完成率: {result['rent']['existing'] / result['total_estates'] * 100:.1f}%")
    
    print(f"\n📉 完全缺失 (buy和rent都缺失):")
    print(f"  数量: {result['both_missing']['count']} 个")
    
    # 创建ID到名称的反向映射
    id_to_name = {v: k for k, v in estates_mapping.items()}
    
    # 打印缺失buy的ID（前20个）
    if result['buy']['missing'] > 0:
        print(f"\n📝 缺失买卖记录的屋苑ID (共{result['buy']['missing']}个，显示前20个):")
        for i, estate_id in enumerate(result['buy']['missing_ids'][:20], 1):
            name = id_to_name.get(estate_id, '未知')
            print(f"  {i}. ID: {estate_id}, 名称: {name}")
        
        if result['buy']['missing'] > 20:
            print(f"  ... 还有 {result['buy']['missing'] - 20} 个")
    
    # 打印缺失rent的ID（前20个）
    if result['rent']['missing'] > 0:
        print(f"\n📝 缺失租房记录的屋苑ID (共{result['rent']['missing']}个，显示前20个):")
        for i, estate_id in enumerate(result['rent']['missing_ids'][:20], 1):
            name = id_to_name.get(estate_id, '未知')
            print(f"  {i}. ID: {estate_id}, 名称: {name}")
        
        if result['rent']['missing'] > 20:
            print(f"  ... 还有 {result['rent']['missing'] - 20} 个")
    
    # 打印完全缺失的ID
    if result['both_missing']['count'] > 0:
        print(f"\n📝 完全缺失的屋苑ID (buy和rent都缺失，共{result['both_missing']['count']}个，显示前20个):")
        for i, estate_id in enumerate(result['both_missing']['ids'][:20], 1):
            name = id_to_name.get(estate_id, '未知')
            print(f"  {i}. ID: {estate_id}, 名称: {name}")
        
        if result['both_missing']['count'] > 20:
            print(f"  ... 还有 {result['both_missing']['count'] - 20} 个")
    
    print("\n" + "=" * 70)


def save_missing_ids(result: Dict, output_file: str = 'missing_records.json'):
    """保存缺失的ID到JSON文件"""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 详细结果已保存到: {output_file}")
    except Exception as e:
        print(f"\n❌ 保存失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='检查缺失的屋苑成交记录')
    parser.add_argument('--mapping', type=str, default='estates_mapping.json',
                       help='屋苑映射文件路径 (默认: estates_mapping.json)')
    parser.add_argument('--records-dir', type=str, default='28hse/transaction_records',
                       help='成交记录根目录 (默认: transaction_records)')
    parser.add_argument('--output', type=str, default='missing_records.json',
                       help='输出JSON文件路径 (默认: missing_records.json)')
    parser.add_argument('--save', action='store_true',
                       help='是否保存结果到JSON文件')
    
    args = parser.parse_args()
    
    # 加载屋苑映射
    print("正在加载屋苑映射...")
    estates_mapping = load_estates_mapping(args.mapping)
    
    if not estates_mapping:
        print("❌ 未找到屋苑映射数据")
        return
    
    print(f"✓ 已加载 {len(estates_mapping)} 个屋苑\n")
    
    # 检查缺失记录
    result = check_missing_records(estates_mapping, args.records_dir)
    
    # 打印结果
    print_results(result, estates_mapping)
    
    # 保存结果（如果指定）
    if args.save:
        save_missing_ids(result, args.output)


if __name__ == '__main__':
    main()
