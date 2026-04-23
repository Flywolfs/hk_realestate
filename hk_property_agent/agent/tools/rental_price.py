"""
租金查询工具
查询屋苑的最近租赁记录、平均月租和租金尺价。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.loader import get_loader
from agent.tools.utils import to_traditional


@tool
def get_rental_price(estate_name: str) -> str:
    """
    查询指定香港屋苑的租金信息，包括最近租赁成交记录、平均月租和租金尺价。
    适合用户询问租金水平、出租行情等问题。
    例如：「太古城两房租多少」「将军澳日出康城的租金」「XX屋苑租金尺价」。

    参数:
        estate_name: 屋苑名称（中文或英文）
    """
    estate_name = to_traditional(estate_name)
    loader = get_loader()

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

    rental_info = loader.get_rental_info(estate_id)
    if not rental_info:
        return f"「{estate_name_display}」暂无租赁成交数据。"

    return _format_rental(estate_name_display, rental_info)


def _format_rental(name: str, info: dict) -> str:
    lines = [f"【{name}】租金信息\n"]

    avg_rent = info.get('avg_rent')
    rpsf = info.get('rent_per_sqft')
    total = info.get('total_records', 0)

    if avg_rent:
        lines.append(f"平均月租：{avg_rent:,.0f} 港元")
    if rpsf:
        lines.append(f"租金尺价：{rpsf:.1f} 港元/呎")
    lines.append(f"样本数量：{total} 笔租赁记录")

    recent = info.get('recent_rentals', [])
    if recent:
        lines.append(f"\n最近租赁成交（近 {min(len(recent), 10)} 笔）：")
        for r in recent[:10]:
            unit = r.get('unit_location', '—')
            date_str = r.get('date', '—')
            price = r.get('price', 0)
            lines.append(f"  {date_str} | {unit} | 月租 {price:,.0f} 港元")

    return "\n".join(lines)


if __name__ == "__main__":
    # ====== 手动调试入口 ======
    # 用法: cd hk_property_agent && python -m agent.tools.rental_price
    # 当 agent 租金查询异常时，在此处直接测试

    print("===== get_rental_price 测试 =====")

    # >>> 在此修改要测试的屋苑名称 <<<
    test_estates = ["太古城", "康怡花園", "不存在的屋苑"]

    for name in test_estates:
        print(f"\n--- 查询 '{name}' 的租金 ---")
        result = get_rental_price.invoke({"estate_name": name})
        print(result)
        print("-" * 50)
