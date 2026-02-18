#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算周平均尺价变化趋势脚本

功能：
1. 读取transaction_records_20260215_trans文件夹中的买卖和出租数据
2. 按周为单位统计每周的平均尺价
3. 计算2025年1月1日至当前日期的销售平均尺价和租赁平均尺价变化趋势
4. 如果某周没有数据，则延续上周的数据
5. 输出结果到JSON文件
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
# import numpy as np  # 使用纯Python实现，无需numpy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置参数
CONFIG = {
    "base_dir": "./28hse/transaction_records_20260215_trans",
    "start_date": "2025-01-01",
    "output_file": "weekly_price_trends.json"
}


def get_week_start(date_str: str) -> Optional[str]:
    """
    获取日期所在周的起始日期（周一）
    
    Args:
        date_str: 日期字符串，格式为 YYYY-MM-DD
        
    Returns:
        周起始日期字符串（周一），格式为 YYYY-MM-DD
    """
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        # 计算到周一的天数（weekday(): 周一=0, 周日=6）
        days_to_monday = date.weekday()
        monday = date - timedelta(days=days_to_monday)
        return monday.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def is_date_in_range(date_str: str, start_date_str: str) -> bool:
    """
    检查日期是否在指定范围内（包含起始日期）
    
    Args:
        date_str: 要检查的日期字符串
        start_date_str: 起始日期字符串
        
    Returns:
        如果日期 >= 起始日期则返回True
    """
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        return date >= start_date
    except (ValueError, TypeError):
        return False


def extract_valid_price_records(file_path: str, price_field: str, start_date: str) -> List[Tuple[str, float]]:
    """
    从JSON文件中提取有效的价格记录
    
    Args:
        file_path: JSON文件路径
        price_field: 价格字段名（price_per_sqft 或 rent_per_sqft）
        start_date: 起始日期
        
    Returns:
        列表，每个元素为 (week_start_date, price) 元组
    """
    records = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        transactions = data.get('transactions', [])
        
        for trans in transactions:
            date_str = trans.get('date')
            price = trans.get(price_field)
            
            # 检查日期是否有效且在范围内
            if not date_str or not is_date_in_range(date_str, start_date):
                continue
            
            # 检查价格是否有效（必须是正数）
            if price is None or not isinstance(price, (int, float)) or price <= 0:
                continue
            
            # 获取周起始日期
            week_start = get_week_start(date_str)
            if week_start:
                records.append((week_start, float(price)))
                
    except Exception as e:
        logger.error(f"读取文件失败 {file_path}: {e}")
    
    return records


def load_all_price_data(data_dir: Path, price_field: str, start_date: str) -> Dict[str, List[float]]:
    """
    加载指定目录下所有文件的周价格数据
    
    Args:
        data_dir: 数据目录路径（buy 或 rent）
        price_field: 价格字段名
        start_date: 起始日期
        
    Returns:
        字典 {week_start_date: [price1, price2, ...]}
    """
    weekly_prices = defaultdict(list)
    
    if not data_dir.exists():
        logger.error(f"数据目录不存在: {data_dir}")
        return weekly_prices
    
    json_files = list(data_dir.glob("*.json"))
    logger.info(f"在 {data_dir} 中找到 {len(json_files)} 个JSON文件")
    
    for json_file in json_files:
        records = extract_valid_price_records(str(json_file), price_field, start_date)
        for week_start, price in records:
            weekly_prices[week_start].append(price)
    
    return weekly_prices


def calculate_mean(values: List[float]) -> float:
    """计算平均值"""
    if not values:
        return 0.0
    return sum(values) / len(values)


def calculate_weekly_averages(weekly_prices: Dict[str, List[float]]) -> Dict[str, float]:
    """
    计算每周的平均价格
    
    Args:
        weekly_prices: 字典 {week_start_date: [price1, price2, ...]}
        
    Returns:
        字典 {week_start_date: average_price}
    """
    weekly_averages = {}
    
    for week_start, prices in weekly_prices.items():
        if prices:
            weekly_averages[week_start] = round(calculate_mean(prices), 2)
    
    return weekly_averages


def fill_missing_weeks(weekly_averages: Dict[str, float], start_date_str: str) -> List[Dict]:
    """
    填充缺失的周数据，使用上周数据进行延续
    
    Args:
        weekly_averages: 每周平均价格字典
        start_date_str: 起始日期字符串
        
    Returns:
        按时间排序的数据点列表，每个点为 {week_start, avg_price, has_data}
    """
    if not weekly_averages:
        return []
    
    # 获取所有周日期并排序
    all_weeks = sorted(weekly_averages.keys())
    
    # 确定日期范围
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(all_weeks[-1], "%Y-%m-%d")
    
    # 生成所有周（从start_date开始，每周一）
    result = []
    current_date = start_date
    last_valid_price = None
    
    # 调整到最近的周一
    if current_date.weekday() != 0:
        days_to_monday = current_date.weekday()
        current_date = current_date - timedelta(days=days_to_monday)
    
    while current_date <= end_date:
        week_str = current_date.strftime("%Y-%m-%d")
        
        if week_str in weekly_averages:
            # 该周有数据
            price = weekly_averages[week_str]
            last_valid_price = price
            result.append({
                "week_start": week_str,
                "avg_price": price,
                "has_data": True
            })
        else:
            # 该周无数据，延续上周数据
            if last_valid_price is not None:
                result.append({
                    "week_start": week_str,
                    "avg_price": last_valid_price,
                    "has_data": False
                })
            else:
                # 还没有任何有效数据，标记为无数据
                result.append({
                    "week_start": week_str,
                    "avg_price": None,
                    "has_data": False
                })
        
        # 移动到下一周
        current_date += timedelta(days=7)
    
    return result


def calculate_price_trends(config: Dict) -> Dict:
    """
    计算周平均尺价变化趋势
    
    Args:
        config: 配置字典
        
    Returns:
        包含买卖和租赁趋势的结果字典
    """
    base_path = Path(config["base_dir"])
    buy_dir = base_path / "buy"
    rent_dir = base_path / "rent"
    start_date = config["start_date"]
    
    logger.info("=" * 60)
    logger.info("开始计算周平均尺价变化趋势")
    logger.info("=" * 60)
    logger.info(f"数据目录: {base_path}")
    logger.info(f"起始日期: {start_date}")
    
    # 加载买卖数据
    logger.info("\n【1】加载买卖数据...")
    buy_weekly_prices = load_all_price_data(buy_dir, "price_per_sqft", start_date)
    buy_weekly_averages = calculate_weekly_averages(buy_weekly_prices)
    logger.info(f"买卖数据：共 {len(buy_weekly_averages)} 个周有数据")
    
    # 加载租赁数据
    logger.info("\n【2】加载租赁数据...")
    rent_weekly_prices = load_all_price_data(rent_dir, "rent_per_sqft", start_date)
    rent_weekly_averages = calculate_weekly_averages(rent_weekly_prices)
    logger.info(f"租赁数据：共 {len(rent_weekly_averages)} 个周有数据")
    
    # 填充缺失周
    logger.info("\n【3】填充缺失周数据...")
    buy_trend = fill_missing_weeks(buy_weekly_averages, start_date)
    rent_trend = fill_missing_weeks(rent_weekly_averages, start_date)
    
    # 统计信息
    buy_data_weeks = sum(1 for item in buy_trend if item["has_data"])
    rent_data_weeks = sum(1 for item in rent_trend if item["has_data"])
    
    logger.info(f"买卖趋势：共 {len(buy_trend)} 周，其中有数据 {buy_data_weeks} 周")
    logger.info(f"租赁趋势：共 {len(rent_trend)} 周，其中有数据 {rent_data_weeks} 周")
    
    # 构建结果
    result = {
        "metadata": {
            "description": "周平均尺价变化趋势（2025年1月1日起）",
            "unit": "港币/平方英尺",
            "start_date": start_date,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_weeks": len(buy_trend),
            "buy_data_weeks": buy_data_weeks,
            "rent_data_weeks": rent_data_weeks
        },
        "buy_trend": buy_trend,
        "rent_trend": rent_trend
    }
    
    return result


def save_results(result: Dict, output_file: str):
    """
    保存结果到JSON文件
    
    Args:
        result: 结果字典
        output_file: 输出文件路径
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n结果已保存到: {output_file}")
        
        # 输出统计摘要
        logger.info("\n" + "=" * 60)
        logger.info("统计摘要")
        logger.info("=" * 60)
        
        buy_trend = result.get("buy_trend", [])
        rent_trend = result.get("rent_trend", [])
        
        # 买卖数据摘要
        buy_prices = [item["avg_price"] for item in buy_trend if item["avg_price"] is not None]
        if buy_prices:
            logger.info(f"\n【买卖平均尺价】")
            logger.info(f"  数据点数: {len(buy_prices)}")
            logger.info(f"  最小值: ${min(buy_prices):,.2f}/ft²")
            logger.info(f"  最大值: ${max(buy_prices):,.2f}/ft²")
            logger.info(f"  平均值: ${calculate_mean(buy_prices):,.2f}/ft²")
            logger.info(f"  最新值: ${buy_prices[-1]:,.2f}/ft²")
        
        # 租赁数据摘要
        rent_prices = [item["avg_price"] for item in rent_trend if item["avg_price"] is not None]
        if rent_prices:
            logger.info(f"\n【租赁平均尺价】")
            logger.info(f"  数据点数: {len(rent_prices)}")
            logger.info(f"  最小值: ${min(rent_prices):,.2f}/ft²")
            logger.info(f"  最大值: ${max(rent_prices):,.2f}/ft²")
            logger.info(f"  平均值: ${calculate_mean(rent_prices):,.2f}/ft²")
            logger.info(f"  最新值: ${rent_prices[-1]:,.2f}/ft²")
        
    except Exception as e:
        logger.error(f"保存结果失败: {e}")


def main():
    """主函数"""
    # 计算趋势
    result = calculate_price_trends(CONFIG)
    
    # 保存结果
    save_results(result, CONFIG["output_file"])
    
    logger.info("\n处理完成!")


if __name__ == "__main__":
    main()
