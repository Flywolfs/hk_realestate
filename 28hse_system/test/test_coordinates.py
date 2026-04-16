#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试坐标提取 - 检查几个样本小区的真实坐标
"""

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import quote

def test_coordinate_extraction(estate_name, estate_id):
    """测试单个小区的坐标提取"""
    base_url = "https://www.28hse.com"
    url = f"{base_url}/estate/detail/{quote(estate_name)}-{estate_id}"
    
    print(f"\n{'='*60}")
    print(f"测试小区: {estate_name} (ID: {estate_id})")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        
        response = session.get(url, timeout=30)
        response.raise_for_status()
        page_text = response.text
        
        # 方法1: 查找 defaultLat 和 defaultLng
        lat_match = re.search(r'defaultLat\s*=\s*([\d.]+)', page_text)
        lng_match = re.search(r'defaultLng\s*=\s*([\d.]+)', page_text)
        
        print(f"\n方法1 (defaultLat/defaultLng):")
        if lat_match and lng_match:
            print(f"  defaultLat = {lat_match.group(1)}")
            print(f"  defaultLng = {lng_match.group(1)}")
        else:
            print(f"  未找到 (lat_match={lat_match is not None}, lng_match={lng_match is not None})")
        
        # 方法2: 查找 latitude 和 longitude
        lat_match2 = re.search(r'latitude[\'"]?\s*[:=]\s*[\'"]?([\d.]+)', page_text, re.IGNORECASE)
        lng_match2 = re.search(r'longitude[\'"]?\s*[:=]\s*[\'"]?([\d.]+)', page_text, re.IGNORECASE)
        
        print(f"\n方法2 (latitude/longitude):")
        if lat_match2 and lng_match2:
            print(f"  latitude = {lat_match2.group(1)}")
            print(f"  longitude = {lng_match2.group(1)}")
        else:
            print(f"  未找到 (lat_match2={lat_match2 is not None}, lng_match2={lng_match2 is not None})")
        
        # 方法3: 查找所有包含坐标的代码
        coord_patterns = [
            r'lat[^a-zA-Z]*[:=]\s*[\'"]?([\d.]+)',
            r'lng[^a-zA-Z]*[:=]\s*[\'"]?([\d.]+)',
            r'\d{2}\.\d{5,},\s*\d{3}\.\d{5,}',
        ]
        
        print(f"\n方法3 (模糊匹配坐标):")
        for pattern in coord_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                print(f"  Pattern '{pattern}': {matches[:5]}")  # 只显示前5个
        
        # 查找地图相关的div
        soup = BeautifulSoup(response.content, 'html.parser')
        map_div = soup.find('div', id='estate_id_map')
        if map_div:
            print(f"\n找到地图div (id=estate_id_map):")
            print(f"  属性: {map_div.attrs}")
        
        # 查找所有包含lat/lng的script标签
        print(f"\n查找包含坐标的script标签:")
        for i, script in enumerate(soup.find_all('script')):
            script_text = script.string
            if script_text and ('lat' in script_text.lower() or 'lng' in script_text.lower() or 'coordinate' in script_text.lower()):
                # 提取包含坐标的行
                lines = [line.strip() for line in script_text.split('\n') if 'lat' in line.lower() or 'lng' in line.lower()]
                if lines:
                    print(f"\n  Script #{i+1}:")
                    for line in lines[:3]:  # 只显示前3行
                        print(f"    {line}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    # 测试几个不同的小区
    test_cases = [
        ("黃埔花園", "3060"),
        ("太古城", "5167"),
        ("美孚新邨", "5177"),
    ]
    
    print("开始测试坐标提取...")
    for estate_name, estate_id in test_cases:
        test_coordinate_extraction(estate_name, estate_id)
        print("\n")
