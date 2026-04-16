"""
租售比查询工具
提供屋苑租售比（当前值 + 历史时序 + 户型分类）的查询功能。

租售比 = 月租金 / 房价，反映该屋苑的投资回报率，
数值越高表示租金回报越好（通常 3-5% 为正常水平）。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.loader import get_loader
from agent.tools.utils import to_traditional


@tool
def get_rent_sale_ratio(estate_name: str) -> str:
    """
    查询指定香港屋苑的租售比信息，包括当前最新租售比、历史月度趋势及各户型租售比。
    租售比是评估房产投资价值的关键指标，反映租金回报率。
    适合用户询问"XX 屋苑值不值得投资"、"租售比多少"、"租金回报如何"等问题。

    参数:
        estate_name: 屋苑名称（中文或英文）
    """
    estate_name = to_traditional(estate_name)
    loader = get_loader()

    # 先找到屋苑 ID
    estate = loader.find_estate_by_name(estate_name)
    if not estate:
        results = loader.fuzzy_search_by_name(estate_name, limit=3)
        if not results:
            return f"找不到屋苑「{estate_name}」，请检查名称是否正确。"
        estate_id = results[0]['id']
        estate_name_display = results[0]['name']
    else:
        estate_id = estate['id']
        estate_name_display = estate['name']

    ratio_info = loader.get_rent_ratio_info(estate_id)
    if not ratio_info:
        return f"「{estate_name_display}」暂无租售比数据。"

    latest = ratio_info.get('latest_ratio')
    timeseries = ratio_info.get('timeseries', {})
    room_type = ratio_info.get('room_type_ratio', {})

    lines = [f"【{estate_name_display}】租售比信息\n"]

    # 当前租售比
    if latest is not None:
        lines.append(f"当前租售比（最新月份）：{latest:.2f}%")
        lines.append(_interpret_ratio(latest))
    else:
        lines.append("当前租售比：暂无数据")

    # 历史趋势（最近 6 个月）
    if timeseries:
        sorted_months = sorted(timeseries.keys())
        recent_6 = sorted_months[-6:]
        lines.append("\n历史月度租售比（近 6 个月）：")
        for month in recent_6:
            lines.append(f"  {month}: {timeseries[month]:.2f}%")

        # 趋势判断
        if len(recent_6) >= 2:
            first_val = timeseries[recent_6[0]]
            last_val = timeseries[recent_6[-1]]
            diff = last_val - first_val
            trend_str = f"上升 {diff:.2f}%" if diff > 0 else f"下降 {abs(diff):.2f}%"
            lines.append(f"\n近半年趋势：{trend_str}")

    # 户型租售比
    if room_type:
        lines.append("\n各户型租售比：")
        for room, ratio in sorted(room_type.items(), key=lambda x: float(x[0]) if _is_num(x[0]) else 0):
            area_str = f"{float(room):.0f} 呎" if _is_num(room) else room
            lines.append(f"  {area_str}: {ratio:.2f}%")

    return "\n".join(lines)


def _is_num(s) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _interpret_ratio(ratio: float) -> str:
    """给出租售比的简单解读。"""
    if ratio < 2.0:
        return "（解读：租售比偏低，租金回报较差，投资吸引力有限）"
    elif ratio < 3.5:
        return "（解读：租售比处于正常偏低水平）"
    elif ratio < 5.0:
        return "（解读：租售比处于正常水平，租金回报尚可）"
    elif ratio < 7.0:
        return "（解读：租售比较高，租金回报较好）"
    else:
        return "（解读：租售比很高，请核实数据是否准确）"
