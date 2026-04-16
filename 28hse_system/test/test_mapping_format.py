#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 estates_mapping.json 的数据格式"""

import json
import os


def test_mapping_format():
    """测试映射文件格式"""
    
    mapping_file = 'estates_mapping.json'
    
    if not os.path.exists(mapping_file):
        print(f"❌ 文件不存在: {mapping_file}")
        print("   请先运行 scrape_estates.py 生成映射文件")
        return
    
    print("=" * 70)
    print("测试 estates_mapping.json 格式")
    print("=" * 70)
    
    # 加载映射文件
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    print(f"\n总记录数: {len(mapping)}")
    
    # 检查格式：应该是 {ID: 名称}
    print("\n检查前10条记录:")
    print("-" * 70)
    
    for i, (key, value) in enumerate(list(mapping.items())[:10], 1):
        print(f"{i:2d}. Key={key:6s} (类型: {type(key).__name__:3s}), "
              f"Value={value:20s} (类型: {type(value).__name__})")
    
    # 分析key和value的特征
    print("\n" + "=" * 70)
    print("数据特征分析:")
    print("-" * 70)
    
    keys_are_numeric = all(k.isdigit() for k in list(mapping.keys())[:100])
    values_are_numeric = all(v.isdigit() if isinstance(v, str) else False 
                             for v in list(mapping.values())[:100])
    
    print(f"前100个key是否全是数字: {'✓ 是' if keys_are_numeric else '✗ 否'}")
    print(f"前100个value是否全是数字: {'✓ 是' if values_are_numeric else '✗ 否'}")
    
    # 检查重名情况
    print("\n" + "=" * 70)
    print("检查重名情况:")
    print("-" * 70)
    
    from collections import Counter
    
    name_counts = Counter(mapping.values())
    duplicates = {name: count for name, count in name_counts.items() if count > 1}
    
    if duplicates:
        print(f"发现 {len(duplicates)} 个重名的屋苑:")
        for i, (name, count) in enumerate(sorted(duplicates.items(), 
                                                  key=lambda x: x[1], 
                                                  reverse=True)[:10], 1):
            # 找出所有这个名字的ID
            ids = [k for k, v in mapping.items() if v == name]
            print(f"  {i:2d}. {name} (出现{count}次): ID={', '.join(ids)}")
    else:
        print("✓ 没有重名的屋苑")
    
    # 结论
    print("\n" + "=" * 70)
    print("结论:")
    print("-" * 70)
    
    if keys_are_numeric and not values_are_numeric:
        print("✓ 数据格式正确: {屋苑ID: 屋苑名称}")
        print("  - Key 是数字ID（唯一标识）")
        print("  - Value 是屋苑名称（可能重复）")
        print("  - 这样可以正确处理重名的屋苑")
    elif not keys_are_numeric and values_are_numeric:
        print("✗ 数据格式错误: {屋苑名称: 屋苑ID}")
        print("  - 这种格式会导致重名屋苑只保留最后一个")
        print("  - 需要运行新版本的 scrape_estates.py 重新生成")
    else:
        print("⚠️  数据格式无法确定")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_mapping_format()
