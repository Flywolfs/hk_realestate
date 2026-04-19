"""
LangChain Tools 集合
所有供 Agent 调用的工具在此统一导出。
"""

from agent.tools.estate_search import search_estate_by_name, search_estates_by_area
from agent.tools.rent_sale_ratio import get_rent_sale_ratio
from agent.tools.price_trend import get_price_trend
from agent.tools.compare_estates import compare_estates
from agent.tools.vector_search import semantic_search
from agent.tools.filter_estates import filter_estates
from agent.tools.area_stats import get_area_stats
from agent.tools.sales_volume import get_sales_volume
from agent.tools.rental_price import get_rental_price

ALL_TOOLS = [
    search_estate_by_name,
    search_estates_by_area,
    get_rent_sale_ratio,
    get_price_trend,
    compare_estates,
    # semantic_search,
    filter_estates,
    get_area_stats,
    get_sales_volume,
    get_rental_price,
]
