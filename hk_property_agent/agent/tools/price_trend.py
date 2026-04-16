"""
价格趋势查询工具
提供屋苑近 N 个月成交尺价走势查询功能。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.loader import get_loader
from agent.tools.utils import to_traditional


@tool
def get_price_trend(estate_name: str, months: int = 12) -> str:
    """
    查询指定香港屋苑近几个月的每平方呎成交价（尺价）走势。
    适合用户询问"XX 屋苑的房价走势"、"近期价格有没有上涨"、"历史尺价"等问题。
    返回各月份的平均尺价数据及简单趋势分析。

    参数:
        estate_name: 屋苑名称（中文或英文）
        months: 查询最近几个月，默认 12 个月，最大 36 个月
    """
    estate_name = to_traditional(estate_name)
    loader = get_loader()
    months = min(36, max(1, months))

    # 找到屋苑
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

    trend_info = loader.get_price_trend_info(estate_id, months=months)
    if not trend_info:
        return f"「{estate_name_display}」暂无价格走势数据。"

    monthly = trend_info.get('monthly_trend', {})
    current_price = trend_info.get('current_price_per_sqft')

    lines = [f"【{estate_name_display}】尺价走势（近 {months} 个月）\n"]

    if current_price:
        lines.append(f"当前平均尺价（最近5笔成交）：{current_price:,.0f} 港元/呎\n")

    if not monthly:
        lines.append("暂无月度尺价趋势数据。")
        return "\n".join(lines)

    sorted_months = sorted(monthly.keys())

    lines.append("月度平均尺价：")
    for month in sorted_months:
        val = monthly[month]
        if isinstance(val, (int, float)):
            lines.append(f"  {month}: {val:,.0f} 港元/呎")
        elif isinstance(val, dict):
            # 可能包含 avg/min/max 等字段
            avg = val.get('avg') or val.get('average') or val.get('mean')
            if avg:
                lines.append(f"  {month}: {avg:,.0f} 港元/呎（均价）")

    # 涨跌分析
    if len(sorted_months) >= 2:
        first_val = _extract_price(monthly[sorted_months[0]])
        last_val = _extract_price(monthly[sorted_months[-1]])
        if first_val and last_val:
            change = last_val - first_val
            pct = change / first_val * 100
            direction = "上涨" if change > 0 else "下跌"
            lines.append(
                f"\n趋势分析：过去 {len(sorted_months)} 个月，尺价{direction} "
                f"{abs(change):,.0f} 港元/呎（{pct:+.1f}%）"
            )

    return "\n".join(lines)


def _extract_price(val) -> float | None:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        return val.get('avg') or val.get('average') or val.get('mean')
    return None
