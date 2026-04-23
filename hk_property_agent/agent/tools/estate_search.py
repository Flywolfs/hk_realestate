"""
屋苑查询工具
提供按名称精确/模糊查询和按地区列表查询功能。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.loader import get_loader
from agent.tools.utils import to_traditional


@tool
def search_estate_by_name(name: str) -> str:
    """
    按屋苑名称查询香港屋苑的基本信息。
    支持中文名称和英文名称，优先精确匹配，无精确结果时进行模糊匹配。
    返回屋苑的名称、地址、地区、建成年份、当前租售比和当前尺价等信息。
    适合用户直接说出屋苑名称时使用，例如"查一下太古城"、"帝景峰怎么样"。

    参数:
        name: 屋苑名称（中文或英文），例如 "太古城"、"Taikoo Shing"
    """
    name = to_traditional(name)
    loader = get_loader()

    # 尝试精确匹配
    result = loader.find_estate_by_name(name)
    if result:
        return _format_estate_full(result)

    # 降级模糊匹配
    results = loader.fuzzy_search_by_name(name, limit=5)
    if not results:
        return f"找不到名称包含「{name}」的屋苑。请检查屋苑名称是否正确，或尝试使用地区名称搜索。"

    if len(results) == 1:
        # 唯一模糊结果，返回完整信息
        full = loader.get_estate_full_info(results[0]['id'])
        return _format_estate_full(full) if full else _format_estate_summary(results[0])

    lines = [f"找到 {len(results)} 个相关屋苑，请确认您要查询的是哪一个：\n"]
    for r in results:
        lines.append(
            f"- {r['name']}（{r['area']}）| 租售比: {_fmt_ratio(r['rent_ratio_latest'])} "
            f"| 尺价: {_fmt_price(r['current_price_per_sqft'])}"
        )
    lines.append("\n如需详细信息，请告知屋苑名称。")
    return "\n".join(lines)


@tool
def search_estates_by_area(area: str, limit: int = 15) -> str:
    """
    按香港地区（区域）列出该地区的屋苑列表及基本租售比和尺价信息。
    适合用户询问某地区有哪些屋苑，或想了解某地区的房价水平时使用。
    例如：「荃湾有什么屋苑」、「沙田的屋苑租售比怎么样」。

    参数:
        area: 香港地区名称，例如 "荃湾"、"沙田"、"旺角"、"将军澳"
        limit: 返回屋苑数量上限，默认 15，最大 30
    """
    area = to_traditional(area)
    loader = get_loader()
    limit = min(30, max(1, limit))

    results = loader.list_estates_by_area(area, limit=limit)
    if not results:
        # 列出可用地区供参考
        all_areas = loader.list_all_areas()
        areas_sample = "、".join(all_areas[:20])
        return (
            f"未找到地区「{area}」的屋苑数据。\n"
            f"可用地区包括：{areas_sample} 等（共 {len(all_areas)} 个地区）。\n"
            f"请检查地区名称是否正确。"
        )

    lines = [f"「{area}」共收录 {len(results)} 个屋苑（显示前 {limit} 个）：\n"]
    for r in results:
        lines.append(
            f"- {r['name']} | 地址: {r['address'] or '—'} "
            f"| 租售比: {_fmt_ratio(r['rent_ratio_latest'])} "
            f"| 尺价: {_fmt_price(r['current_price_per_sqft'])}"
        )
    return "\n".join(lines)


# ------------------------------------------------------------------
# 格式化辅助函数
# ------------------------------------------------------------------

def _fmt_ratio(ratio) -> str:
    if ratio is None:
        return "暂无"
    return f"{ratio:.2f}%"


def _fmt_price(price) -> str:
    if price is None:
        return "暂无"
    return f"{price:,.0f} 港元/呎"


def _format_estate_summary(info: dict) -> str:
    return (
        f"屋苑名称：{info.get('name', '—')}\n"
        f"英文名称：{info.get('name_en', '—') or '—'}\n"
        f"所在地区：{info.get('area', '—')}\n"
        f"地址：{info.get('address', '—')}\n"
        f"当前租售比：{_fmt_ratio(info.get('rent_ratio_latest'))}\n"
        f"当前尺价：{_fmt_price(info.get('current_price_per_sqft'))}\n"
        f"实用面积范围：{_fmt_area(info.get('min_area'), info.get('max_area'))}"
    )


def _format_estate_full(info: dict) -> str:
    if not info:
        return "找不到该屋苑的详细信息。"

    basic = info.get('basic_info', {})
    lines = [
        f"【{info.get('name', '—')}】",
        f"英文名称：{info.get('name_en', '—') or '—'}",
        f"所在地区：{info.get('area', '—')}",
        f"地址：{info.get('address', '—')}",
        f"建成年份：{info.get('establish_year') or basic.get('establish_year') or '—'}",
        f"校網（小学）：{info.get('primary_school') or basic.get('primary_school') or '—'}",
        f"当前租售比：{_fmt_ratio(info.get('rent_ratio_latest'))}",
        f"当前尺价：{_fmt_price(info.get('current_price_per_sqft'))}",
        f"实用面积范围：{_fmt_area(info.get('min_area'), info.get('max_area'))}",
    ]

    # 附加基本信息字段
    for k, v in basic.items():
        if k not in ('establish_year', 'primary_school') and v:
            lines.append(f"{k}：{v}")

    return "\n".join(lines)


def _fmt_area(min_area, max_area) -> str:
    if min_area and max_area:
        return f"{min_area:.0f} – {max_area:.0f} 平方呎"
    return "暂无"


if __name__ == "__main__":
    # ====== 手动调试入口 ======
    # 用法: cd hk_property_agent && python -m agent.tools.estate_search

    print("===== search_estate_by_name 测试 =====")

    # 测试1: 精确匹配
    print("\n--- 测试1: 精确匹配 '太古城' ---")
    result = search_estate_by_name.invoke({"name": "太古城"})
    print(result)

    # 测试2: 模糊匹配
    print("\n--- 测试2: 模糊匹配 '太古' ---")
    result = search_estate_by_name.invoke({"name": "太古"})
    print(result)

    # 测试3: 找不到
    print("\n--- 测试3: 找不到 '不存在的屋苑' ---")
    result = search_estate_by_name.invoke({"name": "不存在的屋苑"})
    print(result)

    # 测试4: 简体输入
    print("\n--- 测试4: 简体输入 '沙田区' ---")
    result = search_estate_by_name.invoke({"name": "沙田区"})
    print(result)

    print("\n===== search_estates_by_area 测试 =====")

    # 测试5: 按地区查询
    print("\n--- 测试5: 按地区查询 '沙田區' ---")
    result = search_estates_by_area.invoke({"area": "沙田區", "limit": 5})
    print(result)

    # 测试6: 找不到地区
    print("\n--- 测试6: 找不到地区 '火星區' ---")
    result = search_estates_by_area.invoke({"area": "火星區"})
    print(result)
