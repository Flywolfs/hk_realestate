"""
屋苑对比工具
对比多个屋苑的租售比、尺价及基本信息，辅助用户做出购房/投资决策。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import List
from langchain_core.tools import tool
from data.loader import get_loader


@tool
def compare_estates(estate_names: List[str]) -> str:
    """
    对比多个香港屋苑的关键指标，包括租售比、当前尺价、实用面积范围、地区、建成年份等。
    适合用户想要比较几个屋苑孰优孰劣时使用，
    例如"帮我比较太古城和康怡花园"、"哪个屋苑的租售比更高"。

    参数:
        estate_names: 要对比的屋苑名称列表，例如 ["太古城", "康怡花园", "嘉湖山庄"]
    """
    loader = get_loader()

    if not estate_names:
        return "请提供至少两个屋苑名称进行对比。"

    if len(estate_names) > 5:
        return "单次最多对比 5 个屋苑，请减少数量后重试。"

    results = []
    not_found = []

    for name in estate_names:
        estate = loader.find_estate_by_name(name)
        if not estate:
            fuzzy = loader.fuzzy_search_by_name(name, limit=1)
            if fuzzy:
                estate = loader.get_estate_full_info(fuzzy[0]['id'])
            else:
                not_found.append(name)
                continue
        if estate:
            results.append(estate)

    if not results:
        return f"所有屋苑均未找到：{', '.join(not_found)}"

    lines = ["【屋苑对比】\n"]

    # 表格式对比
    headers = ["屋苑名称", "地区", "建成年份", "租售比", "当前尺价", "面积范围（呎）"]
    col_width = 18

    header_line = "  ".join(h.ljust(col_width) for h in headers)
    lines.append(header_line)
    lines.append("-" * len(header_line))

    for estate in results:
        basic = estate.get('basic_info', {})
        row = [
            estate.get('name', '—')[:col_width],
            (estate.get('area', '—') or '—')[:col_width],
            str(estate.get('establish_year') or basic.get('establish_year') or '—')[:col_width],
            _fmt_ratio(estate.get('rent_ratio_latest'))[:col_width],
            _fmt_price(estate.get('current_price_per_sqft'))[:col_width],
            _fmt_area(estate.get('min_area'), estate.get('max_area'))[:col_width],
        ]
        lines.append("  ".join(cell.ljust(col_width) for cell in row))

    # 投资推荐（基于租售比排名）
    valid_ratios = [(e.get('name', ''), e.get('rent_ratio_latest')) for e in results if e.get('rent_ratio_latest')]
    if valid_ratios:
        ranked = sorted(valid_ratios, key=lambda x: x[1], reverse=True)
        lines.append(f"\n按租售比从高到低排名：")
        for i, (name, ratio) in enumerate(ranked, 1):
            lines.append(f"  {i}. {name}: {ratio:.2f}%")

    if not_found:
        lines.append(f"\n以下屋苑未找到：{', '.join(not_found)}")

    return "\n".join(lines)


def _fmt_ratio(ratio) -> str:
    if ratio is None:
        return "暂无"
    return f"{ratio:.2f}%"


def _fmt_price(price) -> str:
    if price is None:
        return "暂无"
    return f"{price:,.0f}"


def _fmt_area(min_a, max_a) -> str:
    if min_a and max_a:
        return f"{min_a:.0f}–{max_a:.0f}"
    return "暂无"
