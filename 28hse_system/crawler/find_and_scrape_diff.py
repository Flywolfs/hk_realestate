#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查找新旧映射文件的差异，并为差异屋苑补充爬取数据
"""

import json
import os
import sys
import subprocess
from typing import Dict, Set, Tuple


def load_mapping(filepath: str) -> Dict[str, str]:
    """加载映射文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  文件不存在: {filepath}")
        return {}
    except Exception as e:
        print(f"❌ 加载文件失败 {filepath}: {e}")
        return {}


def find_differences(new_mapping: Dict[str, str], 
                    old_mapping: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    找出新旧映射的差异
    
    Args:
        new_mapping: 新的映射 {ID: 名称}
        old_mapping: 旧的映射 {名称: ID} 或 {ID: 名称}
        
    Returns:
        (新增的屋苑, 删除的屋苑)
    """
    # 检测旧映射的格式
    if old_mapping:
        first_key = next(iter(old_mapping.keys()))
        first_value = old_mapping[first_key]
        
        # 如果key是数字，value不是数字，说明是新格式 {ID: 名称}
        if first_key.isdigit() and not first_value.isdigit():
            old_ids = set(old_mapping.keys())
        else:
            # 旧格式 {名称: ID}，需要反转
            old_ids = set(old_mapping.values())
    else:
        old_ids = set()
    
    new_ids = set(new_mapping.keys())
    
    # 找出新增和删除的ID
    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids
    
    # 构建结果字典
    added_estates = {eid: new_mapping[eid] for eid in added_ids}
    removed_estates = {}
    
    # 对于删除的ID，尝试找回名称
    if old_mapping:
        if first_key.isdigit():
            # 新格式
            removed_estates = {eid: old_mapping.get(eid, '未知') for eid in removed_ids}
        else:
            # 旧格式，需要反向查找
            reverse_old = {v: k for k, v in old_mapping.items()}
            removed_estates = {eid: reverse_old.get(eid, '未知') for eid in removed_ids}
    
    return added_estates, removed_estates


def save_diff_mapping(added_estates: Dict[str, str], output_file: str = 'estates_diff_mapping.json'):
    """保存差异的屋苑映射"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(added_estates, f, ensure_ascii=False, indent=2)
    print(f"✓ 差异屋苑映射已保存到: {output_file}")


def scrape_estate_details(diff_mapping_file: str):
    """调用 scrape_estate_details.py 爬取差异屋苑的详细信息"""
    print("\n" + "=" * 70)
    print("开始爬取差异屋苑的详细信息...")
    print("=" * 70)
    
    cmd = [
        'python3', 
        'scrape_estate_details.py',
        '--input', diff_mapping_file,
        '--workers', '5'
    ]
    
    print(f"\n执行命令: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✓ 屋苑详细信息爬取完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 屋苑详细信息爬取失败: {e}")
        return False
    except FileNotFoundError:
        print(f"\n❌ 找不到脚本: scrape_estate_details.py")
        return False


def scrape_transaction_records(diff_mapping_file: str):
    """调用 scrape_transaction_records.py 爬取差异屋苑的成交记录"""
    print("\n" + "=" * 70)
    print("开始爬取差异屋苑的成交记录...")
    print("=" * 70)
    
    cmd = [
        'python3',
        'scrape_transaction_records.py',
        '--mapping', diff_mapping_file,
        '--workers', '5'
    ]
    
    print(f"\n执行命令: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✓ 成交记录爬取完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 成交记录爬取失败: {e}")
        return False
    except FileNotFoundError:
        print(f"\n❌ 找不到脚本: scrape_transaction_records.py")
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='查找并爬取差异屋苑数据')
    parser.add_argument('--new-mapping', type=str, default='estates_mapping.json',
                       help='新的映射文件 (默认: estates_mapping.json)')
    parser.add_argument('--old-mapping', type=str, default='estates_mapping_old.json',
                       help='旧的映射文件 (默认: estates_mapping_old.json)')
    parser.add_argument('--output', type=str, default='estates_diff_mapping.json',
                       help='差异映射输出文件 (默认: estates_diff_mapping.json)')
    parser.add_argument('--skip-details', action='store_true',
                       help='跳过爬取详细信息')
    parser.add_argument('--skip-transactions', action='store_true',
                       help='跳过爬取成交记录')
    parser.add_argument('--only-diff', action='store_true',
                       help='只生成差异文件，不执行爬取')
    parser.add_argument('--auto-scrape', action='store_true',
                       help='自动开始爬取，不需要确认')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("查找新旧映射文件差异")
    print("=" * 70)
    
    # 加载映射文件
    print(f"\n正在加载新映射文件: {args.new_mapping}")
    new_mapping = load_mapping(args.new_mapping)
    
    print(f"正在加载旧映射文件: {args.old_mapping}")
    old_mapping = load_mapping(args.old_mapping)
    
    if not new_mapping:
        print("\n❌ 新映射文件为空或加载失败")
        return 1
    
    print(f"\n新映射: {len(new_mapping)} 个屋苑")
    print(f"旧映射: {len(old_mapping)} 个屋苑")
    
    # 查找差异
    print("\n正在分析差异...")
    added_estates, removed_estates = find_differences(new_mapping, old_mapping)
    
    print("\n" + "=" * 70)
    print("差异分析结果")
    print("=" * 70)
    
    print(f"\n新增屋苑: {len(added_estates)} 个")
    if added_estates:
        print("\n前20个新增屋苑:")
        for i, (eid, name) in enumerate(list(added_estates.items())[:20], 1):
            print(f"  {i:2d}. ID={eid:6s}, 名称={name}")
        if len(added_estates) > 20:
            print(f"  ... 还有 {len(added_estates) - 20} 个")
    
    print(f"\n删除屋苑: {len(removed_estates)} 个")
    if removed_estates:
        print("\n前20个删除屋苑:")
        for i, (eid, name) in enumerate(list(removed_estates.items())[:20], 1):
            print(f"  {i:2d}. ID={eid:6s}, 名称={name}")
        if len(removed_estates) > 20:
            print(f"  ... 还有 {len(removed_estates) - 20} 个")
    
    # 保存差异映射
    if added_estates:
        save_diff_mapping(added_estates, args.output)
    else:
        print("\n⚠️  没有新增屋苑，无需生成差异文件")
        return 0
    
    # 如果只生成差异文件，直接返回
    if args.only_diff:
        print("\n✓ 差异文件已生成，跳过爬取")
        return 0
    
    # 询问是否继续爬取（除非自动模式）
    if not args.auto_scrape:
        print("\n" + "=" * 70)
        print(f"发现 {len(added_estates)} 个新增屋苑需要爬取数据")
        print("=" * 70)
        
        response = input("\n是否开始爬取？(y/n): ").strip().lower()
        if response != 'y':
            print("\n已取消爬取")
            return 0
    else:
        print("\n✓ 自动模式，开始爬取...")
    
    # 爬取详细信息
    if not args.skip_details:
        scrape_estate_details(args.output)
    else:
        print("\n⏭️  跳过爬取详细信息")
    
    # 爬取成交记录
    if not args.skip_transactions:
        scrape_transaction_records(args.output)
    else:
        print("\n⏭️  跳过爬取成交记录")
    
    print("\n" + "=" * 70)
    print("全部完成！")
    print("=" * 70)
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n已被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
