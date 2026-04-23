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
    min_rent: float = None,
    max_rent: float = None,
    min_building_age: float = None,
    max_building_age: float = None,
    include_public_housing: bool = False,
    include_hos: bool = False,
    sort_by: str = "rent_ratio",
    sort_order: str = "desc",
    limit: int = 10,
) -> str:
    """
    按数值条件筛选香港屋苑。适合用户提出明确的价格区间、面积要求或租售比阈值时使用。
    例如：「800万以内的两房」「尺价低于1万的屋苑」「租售比高于4%的沙田屋苑」「月租2万以内」「楼龄20年以下」。

    默认排除公屋和居屋。如果用户特别要求查看公屋或居屋，设置 include_public_housing=True 或 include_hos=True。

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
        min_rent: 平均月租下限（港元），如 15000（可选）
        max_rent: 平均月租上限（港元），如 30000（可选）
        min_building_age: 楼龄下限（年），如 5（可选）
        max_building_age: 楼龄上限（年），如 20 表示20年以内（可选）
        include_public_housing: 是否包含公屋，默认 False（除非用户特别要求查看公屋）
        include_hos: 是否包含居屋，默认 False（除非用户特别要求查看居屋）
        sort_by: 排序字段，可选 "rent_ratio"（租售比）、"price"（尺价）、"area_size"（面积）、"rent"（月租）、"building_age"（楼龄），默认 "rent_ratio"
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
        min_rent=min_rent,
        max_rent=max_rent,
        min_building_age=min_building_age,
        max_building_age=max_building_age,
        include_public_housing=include_public_housing,
        include_hos=include_hos,
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
        if min_rent or max_rent:
            conditions.append(f"月租 {_range_str(min_rent, max_rent)} 港元")
        if min_building_age or max_building_age:
            conditions.append(f"楼龄 {_range_str(min_building_age, max_building_age)} 年")
        if not include_public_housing:
            conditions.append("已排除公屋")
        if not include_hos:
            conditions.append("已排除居屋")
        cond_str = "、".join(conditions) if conditions else "当前条件"
        all_areas = loader.list_all_areas()
        return (
            f"按{cond_str}筛选，未找到符合条件的屋苑。\n"
            f"可尝试放宽条件。可用地区包括：{'、'.join(all_areas[:15])} 等。"
        )

    sort_label = {"rent_ratio": "租售比", "price": "尺价", "area_size": "面积", "rent": "月租", "building_age": "楼龄"}.get(sort_by, sort_by)
    order_label = "从高到低" if sort_order == "desc" else "从低到高"

    # 提示是否排除了公屋/居屋
    exclude_note = ""
    if not include_public_housing and not include_hos:
        exclude_note = "（已排除公屋/居屋）"
    elif not include_public_housing:
        exclude_note = "（已排除公屋）"
    elif not include_hos:
        exclude_note = "（已排除居屋）"

    lines = [f"筛选结果（按{sort_label}{order_label}排列，共 {len(results)} 个）{exclude_note}：\n"]

    for i, r in enumerate(results, 1):
        area_range = _fmt_area_range(r.get('min_area'), r.get('max_area'))
        lines.append(
            f"{i}. 【{r['name']}】（{r.get('area', '—')}）"
            f" | 租售比: {_fmt_ratio(r.get('rent_ratio_latest'))}"
            f" | 尺价: {_fmt_price(r.get('current_price_per_sqft'))}"
            f" | 面积: {area_range}"
            f" | 月租: {_fmt_rent(r.get('avg_rent'))}"
            f" | 楼龄: {_fmt_age(r.get('building_age'), r.get('establish_year'))}"
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


def _fmt_rent(rent) -> str:
    if rent is None:
        return "暂无"
    return f"{rent:,.0f} 港元"


def _fmt_age(age, establish_year=None) -> str:
    if age is not None:
        year_info = f"（{int(establish_year)}年入伙）" if establish_year else ""
        return f"{int(age)}年{year_info}"
    if establish_year:
        return f"入伙年份 {int(establish_year)}"
    return "暂无"


if __name__ == "__main__":
    # ====== 手动调试入口 ======
    # 用法: cd hk_property_agent && python -m agent.tools.filter_estates
    # 当 agent 筛选结果异常时，在此处直接测试

    print("===== filter_estates 测试 =====")

    # >>> 在此修改筛选条件 <<<
    test_cases = [
        # 测试1: 按地区筛选
        {"area": "沙田區", "limit": 5},
        # 测试2: 尺价筛选
        {"max_price": 10000, "sort_by": "price", "sort_order": "asc", "limit": 5},
        # 测试3: 租售比筛选
        {"min_rent_ratio": 4.0, "sort_by": "rent_ratio", "sort_order": "desc", "limit": 5},
        # 测试4: 组合条件
        {"area": "沙田區", "min_rent_ratio": 3.5, "max_price": 15000, "limit": 5},
        # 测试5: 面积筛选
        {"min_area_size": 400, "max_area_size": 600, "sort_by": "area_size", "limit": 5},
        # 测试6: 月租筛选
        {"max_rent": 20000, "sort_by": "rent", "sort_order": "asc", "limit": 5},
        # 测试7: 楼龄筛选
        {"max_building_age": 20, "sort_by": "building_age", "limit": 5},
        # 测试8: 包含公屋
        {"area": "沙田區", "include_public_housing": True, "limit": 5},
    ]

    for i, case in enumerate(test_cases, 1):
        desc = ", ".join(f"{k}={v}" for k, v in case.items() if k != "limit")
        print(f"\n--- 测试{i}: {desc or '无条件'} ---")
        result = filter_estates.invoke(case)
        print(result)
        print("-" * 50)
