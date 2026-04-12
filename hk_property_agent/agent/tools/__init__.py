"""
LangChain Tools 集合
所有供 Agent 调用的工具在此统一导出。
"""

from agent.tools.estate_search import search_estate_by_name, search_estates_by_area
from agent.tools.rent_sale_ratio import get_rent_sale_ratio
from agent.tools.price_trend import get_price_trend
from agent.tools.compare_estates import compare_estates
from agent.tools.vector_search import semantic_search

ALL_TOOLS = [
    search_estate_by_name,
    search_estates_by_area,
    get_rent_sale_ratio,
    get_price_trend,
    compare_estates,
    semantic_search,
]
