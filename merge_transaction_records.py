#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并交易记录目录
将前一个完整目录中缺失的屋苑记录复制到当前增量目录
"""

import os
import json
import shutil
import argparse
from typing import Set, Dict, List, Tuple
from pathlib import Path


class TransactionRecordsMerger:
    """交易记录合并器"""
    
    def __init__(self, current_dir: str, previous_dir: str):
        """
        初始化合并器
        
        Args:
            current_dir: 当前目录（增量数据目录）
            previous_dir: 前一个完整记录目录
        """
        self.current_dir = current_dir
        self.previous_dir = previous_dir
        self.stats = {
            'buy': {'copied': 0, 'skipped': 0, 'missing_in_previous': 0},
            'rent': {'copied': 0, 'skipped': 0, 'missing_in_previous': 0}
        }
        
    def get_existing_ids(self, directory: str, subdir: str) -> Set[str]:
        """
        获取指定目录中已存在的屋苑ID集合
        
        Args:
            directory: 主目录路径
            subdir: 子目录名称（buy 或 rent）
            
        Returns:
            存在的屋苑ID集合（不含.json后缀）
        """
        ids = set()
        target_dir = os.path.join(directory, subdir)
        
        if not os.path.exists(target_dir):
            return ids
        
        for filename in os.listdir(target_dir):
            if filename.endswith('.json'):
                estate_id = filename[:-5]  # 去掉 .json
                ids.add(estate_id)
        
        return ids
    
    def copy_file(self, src_path: str, dst_path: str) -> bool:
        """
        复制文件
        
        Args:
            src_path: 源文件路径
            dst_path: 目标文件路径
            
        Returns:
            是否成功
        """
        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            
            # 复制文件
            shutil.copy2(src_path, dst_path)
            return True
        except Exception as e:
            print(f"    ❌ 复制失败: {e}")
            return False
    
    def merge_subdirectory(self, subdir: str) -> Dict:
        """
        合并指定子目录（buy 或 rent）
        
        Args:
            subdir: 子目录名称
            
        Returns:
            统计信息
        """
        print(f"\n{'='*60}")
        print(f"处理 {subdir.upper()} 记录")
        print(f"{'='*60}")
        
        # 获取当前目录和前一个目录的ID集合
        current_ids = self.get_existing_ids(self.current_dir, subdir)
        previous_ids = self.get_existing_ids(self.previous_dir, subdir)
        
        print(f"\n当前目录 ({self.current_dir}/{subdir}):")
        print(f"  已有记录: {len(current_ids)} 个")
        
        print(f"\n前一个目录 ({self.previous_dir}/{subdir}):")
        print(f"  已有记录: {len(previous_ids)} 个")
        
        # 找出需要补充的ID（在前一个目录中存在但在当前目录中不存在）
        missing_ids = previous_ids - current_ids
        
        print(f"\n需要补充的记录: {len(missing_ids)} 个")
        
        if not missing_ids:
            print(f"  ✓ 无需补充，当前目录已完整")
            return {'copied': 0, 'skipped': len(current_ids), 'missing_in_previous': 0}
        
        # 显示前10个需要补充的ID
        if len(missing_ids) > 0:
            print(f"\n前10个需要补充的屋苑ID:")
            for i, estate_id in enumerate(sorted(list(missing_ids))[:10], 1):
                src_file = os.path.join(self.previous_dir, subdir, f"{estate_id}.json")
                # 尝试读取屋苑名称
                estate_name = "未知"
                try:
                    with open(src_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        estate_name = data.get('transactions', [{}])[0].get('unit_location', '未知')[:20]
                except:
                    pass
                print(f"  {i:2d}. ID={estate_id:6s} ({estate_name})")
            
            if len(missing_ids) > 10:
                print(f"  ... 还有 {len(missing_ids) - 10} 个")
        
        # 复制缺失的文件
        print(f"\n开始复制...")
        copied = 0
        failed = 0
        
        for i, estate_id in enumerate(sorted(list(missing_ids)), 1):
            src_file = os.path.join(self.previous_dir, subdir, f"{estate_id}.json")
            dst_file = os.path.join(self.current_dir, subdir, f"{estate_id}.json")
            
            if self.copy_file(src_file, dst_file):
                copied += 1
                if i % 100 == 0 or i == len(missing_ids):
                    print(f"  进度: {i}/{len(missing_ids)} ({i*100//len(missing_ids)}%)")
            else:
                failed += 1
        
        print(f"\n✓ {subdir.upper()} 处理完成:")
        print(f"  成功复制: {copied} 个")
        if failed > 0:
            print(f"  复制失败: {failed} 个")
        
        return {
            'copied': copied,
            'skipped': len(current_ids),
            'missing_in_previous': len(current_ids - previous_ids)
        }
    
    def merge(self) -> Dict:
        """
        执行合并操作
        
        Returns:
            合并统计信息
        """
        print("=" * 70)
        print("交易记录目录合并工具")
        print("=" * 70)
        
        print(f"\n当前目录（增量数据）: {self.current_dir}")
        print(f"前一个目录（完整数据）: {self.previous_dir}")
        
        # 检查目录是否存在
        if not os.path.exists(self.current_dir):
            print(f"\n❌ 当前目录不存在: {self.current_dir}")
            return {}
        
        if not os.path.exists(self.previous_dir):
            print(f"\n❌ 前一个目录不存在: {self.previous_dir}")
            return {}
        
        # 合并 buy 和 rent
        buy_stats = self.merge_subdirectory('buy')
        rent_stats = self.merge_subdirectory('rent')
        
        # 汇总统计
        total_copied = buy_stats['copied'] + rent_stats['copied']
        total_skipped = buy_stats['skipped'] + rent_stats['skipped']
        
        print("\n" + "=" * 70)
        print("合并完成！")
        print("=" * 70)
        
        print(f"\n📊 汇总统计:")
        print(f"  BUY 记录:")
        print(f"    - 复制: {buy_stats['copied']} 个")
        print(f"    - 跳过（已存在）: {buy_stats['skipped']} 个")
        if buy_stats['missing_in_previous'] > 0:
            print(f"    - 当前目录特有（不在前一个目录）: {buy_stats['missing_in_previous']} 个")
        
        print(f"\n  RENT 记录:")
        print(f"    - 复制: {rent_stats['copied']} 个")
        print(f"    - 跳过（已存在）: {rent_stats['skipped']} 个")
        if rent_stats['missing_in_previous'] > 0:
            print(f"    - 当前目录特有（不在前一个目录）: {rent_stats['missing_in_previous']} 个")
        
        print(f"\n  总计:")
        print(f"    - 复制: {total_copied} 个文件")
        print(f"    - 跳过: {total_skipped} 个文件")
        print(f"    - 当前目录最终: {total_skipped + total_copied} 个文件")
        
        print("\n" + "=" * 70)
        
        return {
            'buy': buy_stats,
            'rent': rent_stats,
            'total_copied': total_copied,
            'total_skipped': total_skipped
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='合并交易记录目录 - 将前一个完整目录中缺失的记录复制到当前增量目录',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本用法
  python3 merge_transaction_records.py \\
    --current 28hse/transaction_records_20260215 \\
    --previous 28hse/transaction_records

  # 使用短参数
  python3 merge_transaction_records.py \\
    -c 28hse/transaction_records_new \\
    -p 28hse/transaction_records_old
        """
    )
    
    parser.add_argument(
        '--current', '-c',
        type=str,
        required=True,
        help='当前目录路径（增量数据目录）'
    )
    
    parser.add_argument(
        '--previous', '-p',
        type=str,
        required=True,
        help='前一个完整记录目录路径'
    )
    
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='试运行模式，只显示将要复制的文件，不实际执行复制'
    )
    
    args = parser.parse_args()
    
    # 创建合并器并执行
    merger = TransactionRecordsMerger(args.current, args.previous)
    
    if args.dry_run:
        print("\n⚠️  试运行模式 - 不会实际复制文件\n")
    
    stats = merger.merge()
    
    if not stats:
        return 1
    
    return 0


if __name__ == '__main__':
    import sys
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
