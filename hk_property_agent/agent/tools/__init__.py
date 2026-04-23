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
from agent.tools.utils import setup_tool_logging, wrap_tool_with_logging

# 初始化工具调用日志
setup_tool_logging()

ALL_TOOLS = [
    wrap_tool_with_logging(search_estate_by_name),
    wrap_tool_with_logging(search_estates_by_area),
    wrap_tool_with_logging(get_rent_sale_ratio),
    wrap_tool_with_logging(get_price_trend),
    wrap_tool_with_logging(compare_estates),
    # wrap_tool_with_logging(semantic_search),
    wrap_tool_with_logging(filter_estates),
    wrap_tool_with_logging(get_area_stats),
    wrap_tool_with_logging(get_sales_volume),
    wrap_tool_with_logging(get_rental_price),
]
