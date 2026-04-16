#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试提取功能
"""

import requests
from bs4 import BeautifulSoup
import re

url = "https://www.28hse.com/estate/detail/黃埔花園-3060"

response = requests.get(url, timeout=30)
soup = BeautifulSoup(response.content, 'html.parser')

print("="*60)
print("测试提取【最新樓價走勢】")
print("="*60)

# 查找th标签
price_th = soup.find('th', string=re.compile(r'最新樓價走勢'))
print(f"price_th 找到: {price_th is not None}")

if price_th:
    print(f"th文本: {price_th.get_text(strip=True)}")
    
    price_table = price_th.find_parent('table')
    print(f"price_table 找到: {price_table is not None}")
    
    if price_table:
        tbody = price_table.find('tbody')
        print(f"tbody 找到: {tbody is not None}")
        
        if tbody:
            rows = tbody.find_all('tr')
            print(f"找到 {len(rows)} 行")
            
            for i, row in enumerate(rows[:3]):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    print(f"  {i+1}. {label}: {value[:50]}")
else:
    # 尝试其他方法
    print("\n尝试使用string参数")
    all_ths = soup.find_all('th')
    print(f"总共有 {len(all_ths)} 个th标签")
    for i, th in enumerate(all_ths):
        text = th.get_text(strip=True)
        if '樓價' in text:
            print(f"  {i}. {text}")
