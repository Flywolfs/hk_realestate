"""
结构化筛选工具
按数值条件（尺价、租售比、面积）精确过滤屋苑，支持排序。
与 semantic_search 互补：数值条件用本工具，描述性需求用 semantic_search。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.loader import get_loader
from agent.tools.utils import to_traditional


@tool
def filter_estates(
    area: str = None,
    min_price: float = None,
    max_price: float = None,
    min_rent_ratio: float = None,
    max_rent_ratio: float = None,
    min_area_size: float = None,
    max_area_size: float = None,
    sort_by: str = "rent_ratio",
    sort_order: str = "desc",
    limit: int = 10,
) -> str:
    """
    按数值条件筛选香港屋苑。适合用户提出明确的价格区间、面积要求或租售比阈值时使用。
    例如：「800万以内的两房」「尺价低于1万的屋苑」「租售比高于4%的沙田屋苑」。

    与 semantic_search 的区别：本工具做精确的数值过滤和排序，
    semantic_search 做模糊的语义匹配。如果用户只说了描述性需求（如"性价比高"）
    而没有给出具体数字，应该用 semantic_search。

    参数:
        area: 地区名称，如 "沙田區"、"將軍澳"、"中西區"（可选）
        min_price: 尺价下限（港元/平方呎），如 8000（可选）
        max_price: 尺价上限（港元/平方呎），如 15000（可选）
        min_rent_ratio: 租售比下限（百分比），如 3.0 表示 3%（可选）
        max_rent_ratio: 租售比上限（百分比）（可选）
        min_area_size: 实用面积下限（平方呎），如 400（可选）
        max_area_size: 实用面积上限（平方呎）（可选）
        sort_by: 排序字段，可选 "rent_ratio"（租售比）、"price"（尺价）、"area_size"（面积），默认 "rent_ratio"
        sort_order: 排序方向，"desc"（从高到低）或 "asc"（从低到高），默认 "desc"
        limit: 返回数量，默认 10，最大 30
    """
    if area:
        area = to_traditional(area)
    loader = get_loader()
    limit = min(30, max(1, limit))

    results = loader.filter_estates(
        area=area,
        min_price=min_price,
        max_price=max_price,
        min_rent_ratio=min_rent_ratio,
        max_rent_ratio=max_rent_ratio,
        min_area_size=min_area_size,
        max_area_size=max_area_size,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
    )

    if not results:
        conditions = []
        if area:
            conditions.append(f"地区={area}")
        if min_price or max_price:
            conditions.append(f"尺价 {_range_str(min_price, max_price)} 港元/呎")
        if min_rent_ratio or max_rent_ratio:
            conditions.append(f"租售比 {_range_str(min_rent_ratio, max_rent_ratio)}%")
        if min_area_size or max_area_size:
            conditions.append(f"面积 {_range_str(min_area_size, max_area_size)} 呎")
        cond_str = "、".join(conditions) if conditions else "当前条件"
        all_areas = loader.list_all_areas()
        return (
            f"按{cond_str}筛选，未找到符合条件的屋苑。\n"
            f"可尝试放宽条件。可用地区包括：{'、'.join(all_areas[:15])} 等。"
        )

    sort_label = {"rent_ratio": "租售比", "price": "尺价", "area_size": "面积"}.get(sort_by, sort_by)
    order_label = "从高到低" if sort_order == "desc" else "从低到高"

    lines = [f"筛选结果（按{sort_label}{order_label}排列，共 {len(results)} 个）：\n"]

    for i, r in enumerate(results, 1):
        area_range = _fmt_area_range(r.get('min_area'), r.get('max_area'))
        lines.append(
            f"{i}. 【{r['name']}】（{r.get('area', '—')}）"
            f" | 租售比: {_fmt_ratio(r.get('rent_ratio_latest'))}"
            f" | 尺价: {_fmt_price(r.get('current_price_per_sqft'))}"
            f" | 面积: {area_range}"
        )

    return "\n".join(lines)


def _range_str(low, high) -> str:
    if low and high:
        return f"{low}–{high}"
    if low:
        return f"≥{low}"
    if high:
        return f"≤{high}"
    return ""


def _fmt_ratio(ratio) -> str:
    if ratio is None:
        return "暂无"
    return f"{ratio:.2f}%"


def _fmt_price(price) -> str:
    if price is None:
        return "暂无"
    return f"{price:,.0f} 港元/呎"


def _fmt_area_range(min_a, max_a) -> str:
    if min_a and max_a:
        return f"{min_a:.0f}–{max_a:.0f} 呎"
    return "暂无"
