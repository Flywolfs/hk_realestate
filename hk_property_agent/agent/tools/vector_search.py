"""
向量语义检索工具
处理用户自然语言描述的模糊需求，如"租售比低的大型屋苑"、"将军澳新盘"等，
通过向量相似度检索最相关的屋苑列表。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.vector_store import get_vector_store
from data.loader import get_loader
from agent.tools.utils import to_traditional


@tool
def semantic_search(query: str, top_k: int = 8) -> str:
    """
    用自然语言描述需求，语义化检索最符合条件的香港屋苑。
    适合处理模糊、描述性的问题，例如：
    - "有没有租售比比较高的新界屋苑"
    - "九龙适合自住、校网好的屋苑"
    - "价格相对便宜、面积比较大的屋苑"
    - "靠近港铁站的沿线屋苑"
    该工具会从向量数据库中检索语义最相关的结果，优先于其他工具使用于描述性查询。

    参数:
        query: 用户自然语言查询描述
        top_k: 返回结果数量，默认 8，最大 15
    """
    query = to_traditional(query)
    vs = get_vector_store()
    loader = get_loader()

    top_k = min(15, max(1, top_k))

    if not vs.is_ready():
        # 向量索引尚未构建，降级为关键词匹配
        return _fallback_keyword_search(query, loader, top_k)

    results = vs.similarity_search(query, top_k=top_k)

    if not results:
        return f"未找到与「{query}」相关的屋苑。请尝试更换关键词，或使用地区名称直接搜索。"

    lines = [f"根据您的描述「{query}」，找到以下相关屋苑：\n"]
    for i, r in enumerate(results, 1):
        estate_id = r.get('estate_id', '')
        # 补充最新租售比和尺价
        summary = loader._build_summary(estate_id, loader.estate_static.get(estate_id, {}))
        lines.append(
            f"{i}. 【{r['name']}】（{r['area']}）"
            f" | 租售比: {_fmt_ratio(summary.get('rent_ratio_latest'))}"
            f" | 尺价: {_fmt_price(summary.get('current_price_per_sqft'))}"
        )

    lines.append("\n如需了解某个屋苑的详细信息，请告知屋苑名称。")
    return "\n".join(lines)


def _fallback_keyword_search(query: str, loader, top_k: int) -> str:
    """向量索引未就绪时，降级为关键词包含搜索。"""
    results = loader.fuzzy_search_by_name(query, limit=top_k)
    if not results:
        return (
            f"向量检索索引尚未构建，且关键词搜索也未找到与「{query}」相关的屋苑。\n"
            "建议先运行 scripts/weekly_update.py 构建向量索引，以获得更好的语义检索效果。"
        )
    lines = [f"（注：向量索引未就绪，以下为关键词匹配结果）\n"]
    for r in results:
        lines.append(
            f"- 【{r['name']}】（{r['area']}）"
            f" | 租售比: {_fmt_ratio(r.get('rent_ratio_latest'))}"
            f" | 尺价: {_fmt_price(r.get('current_price_per_sqft'))}"
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
    # 用法: cd hk_property_agent && python -m agent.tools.vector_search
    # 当 agent 语义搜索异常时，在此处直接测试

    print("===== semantic_search 测试 =====")

    # >>> 在此修改要测试的自然语言查询 <<<
    test_queries = [
        {"query": "租售比高的大型屋苑", "top_k": 5},
        {"query": "沙田区校网好的屋苑", "top_k": 3},
        {"query": "价格便宜的屋苑", "top_k": 5},
        {"query": "完全不相关的查询xyz", "top_k": 3},
    ]

    for case in test_queries:
        query = case["query"]
        top_k = case.get("top_k", 8)
        print(f"\n--- 语义搜索: '{query}' (top_k={top_k}) ---")
        result = semantic_search.invoke(case)
        print(result)
        print("-" * 50)
