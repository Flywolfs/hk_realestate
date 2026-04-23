"""
地区统计工具
提供地区级别的整体数据：屋苑总数、中位尺价、中位租售比、近期价格变化、Top 5 屋苑。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.loader import get_loader
from agent.tools.utils import to_traditional


@tool
def get_area_stats(area: str = None) -> str:
    """
    查询香港某地区的整体房产统计数据，或查看全港各地区概览。
    适合用户询问某地区整体情况、跨地区比较、或想了解全港各区房价水平时使用。
    例如：「将军澳整体怎么样」「沙田和大埔哪个更值得投资」「全港哪个区最贵」。

    参数:
        area: 地区名称，如 "沙田區"、"將軍澳"、"中西區"。
              不传此参数则返回全港各地区的概览表。
    """
    if area:
        area = to_traditional(area)
    loader = get_loader()

    if area:
        stats = loader.get_area_statistics(area=area)
        if not stats:
            all_areas = loader.list_all_areas()
            return (
                f"未找到地区「{area}」的统计数据。\n"
                f"可用地区包括：{'、'.join(all_areas[:20])} 等（共 {len(all_areas)} 个）。"
            )
        return _format_area_detail(stats)

    # 全港概览
    stats = loader.get_area_statistics(area=None)
    if not stats or not stats.get('overview'):
        return "暂无地区统计数据。"
    return _format_overview(stats['overview'])


def _format_area_detail(stats: dict) -> str:
    lines = [f"【{stats['area']}】地区统计\n"]
    lines.append(f"屋苑总数：{stats['total_estates']}")
    lines.append(f"中位尺价：{_fmt_price(stats.get('median_price'))}")
    lines.append(f"中位租售比：{_fmt_ratio(stats.get('median_rent_ratio'))}")

    change = stats.get('price_change_3m')
    if change:
        direction = "上涨" if change['change_pct'] > 0 else "下跌"
        lines.append(
            f"近期尺价变化（{change['from_month']} → {change['to_month']}）："
            f"{direction} {abs(change['change_pct']):.1f}%"
        )

    top5 = stats.get('top5_by_rent_ratio', [])
    if top5:
        lines.append("\n租售比 Top 5 屋苑：")
        for i, e in enumerate(top5, 1):
            lines.append(
                f"  {i}. {e['name']}"
                f" | 租售比: {_fmt_ratio(e.get('ratio'))}"
                f" | 尺价: {_fmt_price(e.get('price'))}"
            )

    return "\n".join(lines)


def _format_overview(overview: list) -> str:
    # Sort by median_price descending
    sorted_areas = sorted(overview, key=lambda x: x.get('median_price') or 0, reverse=True)
    lines = [f"全港各地区概览（按中位尺价从高到低，共 {len(sorted_areas)} 个地区）：\n"]

    for a in sorted_areas:
        if a.get('median_price'):
            lines.append(
                f"- {a['area']}（{a['estate_count']} 个屋苑）"
                f"| 中位尺价: {_fmt_price(a['median_price'])}"
            )

    return "\n".join(lines)


def _fmt_ratio(ratio) -> str:
    if ratio is None:
        return "暂无"
    return f"{ratio:.2f}%"


def _fmt_price(price) -> str:
    if price is None:
        return "暂无"
    return f"{price:,.0f} 港元/呎"


if __name__ == "__main__":
    # ====== 手动调试入口 ======
    # 用法: cd hk_property_agent && python -m agent.tools.area_stats
    # 当 agent 地区统计异常时，在此处直接测试

    print("===== get_area_stats 测试 =====")

    # >>> 在此修改要测试的地区 <<<
    test_cases = [
        {"area": "沙田區"},          # 查询指定地区
        {"area": "將軍澳"},          # 查询另一个地区
        {"area": "火星區"},          # 不存在的地区
        {},                            # 全港概览
    ]

    for case in test_cases:
        area = case.get("area", "全港概览")
        print(f"\n--- 查询 '{area}' ---")
        result = get_area_stats.invoke(case)
        print(result)
        print("-" * 50)
