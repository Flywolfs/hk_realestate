"""
成交量查询工具
查询屋苑或地区的月度成交笔数及量价趋势分析。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.loader import get_loader
from agent.tools.utils import to_traditional


@tool
def get_sales_volume(estate_name: str = None, area: str = None, months: int = 12) -> str:
    """
    查询指定屋苑或地区的月度成交量（买卖交易笔数）及趋势分析。
    适合用户询问成交量、市场热度、交投活跃度等问题。
    例如：「太古城最近成交量如何」「沙田最近成交活跃吗」「市场热不热」。

    参数:
        estate_name: 屋苑名称（中文或英文），如 "太古城"（可选）
        area: 地区名称，如 "沙田區"（可选，与 estate_name 二选一）
        months: 查询最近几个月，默认 12，最大 36
    """
    if estate_name:
        estate_name = to_traditional(estate_name)
    if area:
        area = to_traditional(area)
    loader = get_loader()
    months = min(36, max(1, months))

    if estate_name:
        # 查找屋苑
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

        vol_data = loader.get_sales_volume(estate_id=estate_id, months=months)
        if not vol_data or not vol_data.get('monthly_volume'):
            return f"「{estate_name_display}」暂无成交量数据。"

        return _format_estate_volume(estate_name_display, vol_data['monthly_volume'], months)

    if area:
        vol_data = loader.get_sales_volume(area=area, months=months)
        if not vol_data or not vol_data.get('monthly_volume'):
            return f"地区「{area}」暂无成交量数据。"

        return _format_area_volume(area, vol_data['monthly_volume'], months)

    return "请提供屋苑名称或地区名称来查询成交量。"


def _format_estate_volume(name: str, monthly: dict, months: int) -> str:
    sorted_months = sorted(monthly.keys())
    lines = [f"【{name}】成交量（近 {months} 个月）\n"]

    total_count = 0
    lines.append("月度成交：")
    for month in sorted_months:
        data = monthly[month]
        count = data.get('count', 0)
        total_count += count
        avg_price = data.get('avg_price')
        price_str = f"  均价 {avg_price:,.0f}" if avg_price else ""
        lines.append(f"  {month}: {count} 笔{price_str}")

    lines.append(f"\n期间总成交：{total_count} 笔")

    # 趋势分析
    trend = _analyze_trend(monthly)
    if trend:
        lines.append(f"趋势分析：{trend}")

    return "\n".join(lines)


def _format_area_volume(area: str, monthly: dict, months: int) -> str:
    sorted_months = sorted(monthly.keys())
    lines = [f"【{area}】地区成交量（近 {months} 个月）\n"]

    total_count = 0
    lines.append("月度成交：")
    for month in sorted_months:
        data = monthly[month]
        count = data.get('count', 0)
        total_count += count
        lines.append(f"  {month}: {count} 笔")

    lines.append(f"\n期间总成交：{total_count} 笔")

    trend = _analyze_trend(monthly)
    if trend:
        lines.append(f"趋势分析：{trend}")

    return "\n".join(lines)


def _analyze_trend(monthly: dict) -> str:
    """根据月度数据给出量价趋势判断。"""
    sorted_months = sorted(monthly.keys())
    if len(sorted_months) < 3:
        return ""

    # 近3月 vs 前3月
    recent_3 = sorted_months[-3:]
    prev_3 = sorted_months[-6:-3] if len(sorted_months) >= 6 else sorted_months[:3]

    recent_count = sum(monthly[m].get('count', 0) for m in recent_3)
    prev_count = sum(monthly[m].get('count', 0) for m in prev_3)

    if prev_count == 0 and recent_count == 0:
        return "近期无成交记录"
    if prev_count == 0:
        return "成交量从零开始回升"

    vol_change = (recent_count - prev_count) / prev_count * 100

    # 价格变化
    recent_prices = [monthly[m].get('avg_price') for m in recent_3 if monthly[m].get('avg_price')]
    prev_prices = [monthly[m].get('avg_price') for m in prev_3 if monthly[m].get('avg_price')]

    if recent_prices and prev_prices:
        avg_recent = sum(recent_prices) / len(recent_prices)
        avg_prev = sum(prev_prices) / len(prev_prices)
        price_change = (avg_recent - avg_prev) / avg_prev * 100

        if vol_change > 10 and price_change > 5:
            return f"量价齐升（成交量 +{vol_change:.0f}%，均价 +{price_change:.0f}%）"
        elif vol_change < -10 and price_change < -5:
            return f"量缩价跌（成交量 {vol_change:.0f}%，均价 {price_change:.0f}%）"
        elif vol_change > 10 and price_change < -5:
            return f"以价换量（成交量 +{vol_change:.0f}%，均价 {price_change:.0f}%）"
        elif vol_change < -10 and price_change > 5:
            return f"缩量上涨（成交量 {vol_change:.0f}%，均价 +{price_change:.0f}%）"

    if vol_change > 20:
        return f"成交活跃，近3月成交量增加 {vol_change:.0f}%"
    elif vol_change < -20:
        return f"成交萎缩，近3月成交量减少 {abs(vol_change):.0f}%"
    else:
        return "成交量基本持平"
