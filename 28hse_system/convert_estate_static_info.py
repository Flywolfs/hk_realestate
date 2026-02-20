#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
转换 estate_static_info.json 中的字段格式
- establish_year: 提取年份数字部分
- primary_school: 提取校网数字部分
- building_count: 提取数字部分
- units: 提取数字部分
"""

import json
import re


def extract_year(year_str):
    """从年份字符串中提取数字部分
    
    Args:
        year_str: 年份字符串，例如 "1976 年"
        
    Returns:
        int: 年份数字，如果无法提取则返回 None
    """
    if not year_str:
        return None
    
    # 提取数字部分
    match = re.search(r'\d+', str(year_str))
    if match:
        return int(match.group())
    return None


def extract_primary_school_number(school_str):
    """从校网字符串中提取数字部分
    
    Args:
        school_str: 校网字符串，例如 "相關樓盤14校網(東區)"
        
    Returns:
        int: 校网数字，如果无法提取则返回 None
    """
    if not school_str:
        return None
    
    # 提取"校網"前的数字
    match = re.search(r'(\d+)校網', str(school_str))
    if match:
        return int(match.group(1))
    return None


def extract_number(text):
    """从字符串中提取第一个数字部分
    
    Args:
        text: 包含数字的字符串
        
    Returns:
        int: 提取的数字，如果无法提取则返回 None
    """
    if not text:
        return None
    
    # 提取第一个数字
    match = re.search(r'\d+', str(text))
    if match:
        return int(match.group())
    return None


def convert_estate_data(estate_data):
    """转换单个屋苑的数据
    
    Args:
        estate_data: 屋苑数据字典
        
    Returns:
        dict: 转换后的数据
    """
    converted = estate_data.copy()
    
    # 转换 establish_year (在根层级和 basic_info 中都可能存在)
    if 'establish_year' in converted:
        converted['establish_year'] = extract_year(converted['establish_year'])
    
    if 'basic_info' in converted and 'establish_year' in converted['basic_info']:
        converted['basic_info']['establish_year'] = extract_year(converted['basic_info']['establish_year'])
    
    # 转换 primary_school (在根层级和 basic_info 中都可能存在)
    if 'primary_school' in converted:
        converted['primary_school'] = extract_primary_school_number(converted['primary_school'])
    
    if 'basic_info' in converted and 'primary_school' in converted['basic_info']:
        converted['basic_info']['primary_school'] = extract_primary_school_number(converted['basic_info']['primary_school'])
    
    # 转换 building_count (在根层级和 basic_info 中都可能存在)
    if 'building_count' in converted:
        converted['building_count'] = extract_number(converted['building_count'])
    
    if 'basic_info' in converted and 'building_count' in converted['basic_info']:
        converted['basic_info']['building_count'] = extract_number(converted['basic_info']['building_count'])
    
    # 转换 units (在根层级和 basic_info 中都可能存在)
    if 'units' in converted:
        converted['units'] = extract_number(converted['units'])
    
    if 'basic_info' in converted and 'units' in converted['basic_info']:
        converted['basic_info']['units'] = extract_number(converted['basic_info']['units'])
    
    return converted


def main():
    """主函数"""
    input_file = 'estate_static_info.json'
    output_file = 'estate_static_info_convert.json'
    
    print(f"正在读取文件: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到文件 {input_file}")
        return
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败 - {e}")
        return
    
    print(f"开始转换 {len(data)} 个屋苑的数据...")
    
    # 转换所有屋苑数据
    converted_data = {}
    success_count = 0
    
    for estate_id, estate_info in data.items():
        try:
            converted_data[estate_id] = convert_estate_data(estate_info)
            success_count += 1
        except Exception as e:
            print(f"警告: 转换屋苑 {estate_id} 时出错 - {e}")
            # 保留原始数据
            converted_data[estate_id] = estate_info
    
    print(f"成功转换 {success_count} 个屋苑的数据")
    
    # 保存转换后的数据
    print(f"正在保存到文件: {output_file}")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(converted_data, f, ensure_ascii=False, indent=2)
        print(f"✓ 转换完成! 结果已保存到 {output_file}")
    except Exception as e:
        print(f"错误: 保存文件失败 - {e}")


if __name__ == '__main__':
    main()
