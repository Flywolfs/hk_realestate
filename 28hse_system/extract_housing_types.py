#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从Excel文件提取公屋和居屋名称，生成JSON文件供前端使用
"""
import pandas as pd
import json

def extract_housing_names():
    """提取公屋和居屋名称"""
    
    # 读取公屋数据
    gongwu_df = pd.read_excel('gongwu.xlsx')
    gongwu_names = gongwu_df['zh_name'].dropna().unique().tolist()
    
    # 读取居屋数据
    juwu_df = pd.read_excel('juwu.xlsx')
    juwu_names = juwu_df['zh_name'].dropna().unique().tolist()
    
    # 生成JSON数据
    housing_data = {
        'gongwu': {
            'count': len(gongwu_names),
            'names': gongwu_names
        },
        'juwu': {
            'count': len(juwu_names),
            'names': juwu_names
        }
    }
    
    # 保存到JSON文件
    output_file = 'housing_types.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(housing_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 成功生成 {output_file}")
    print(f"  - 公屋: {len(gongwu_names)} 个")
    print(f"  - 居屋: {len(juwu_names)} 个")
    
    return housing_data

if __name__ == '__main__':
    extract_housing_names()
