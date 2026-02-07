#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算平均租售比脚本

功能：
1. 读取transaction_records_trans文件夹中的买卖和出租数据
2. 找出同时存在于buy和rent文件夹中的小区ID
3. 对每个小区提取rent_per_sqft和price_per_sqft
4. 剔除异常值（使用IQR方法）
5. 计算租售比 = (平均月租金 * 12) / 平均售价
6. 输出结果到average_rent_sale_ratio.json
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def remove_outliers_iqr(data: List[float]) -> List[float]:
    """
    使用IQR(四分位距)方法剔除异常值
    
    Args:
        data: 原始数据列表
        
    Returns:
        剔除异常值后的数据列表
    """
    if len(data) < 4:  # 数据量太少,不剔除异常值
        return data
    
    arr = np.array(data)
    q1 = np.percentile(arr, 25)
    q3 = np.percentile(arr, 75)
    iqr = q3 - q1
    
    # 定义异常值边界
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    # 过滤异常值
    filtered_data = [x for x in data if lower_bound <= x <= upper_bound]
    
    removed_count = len(data) - len(filtered_data)
    if removed_count > 0:
        logger.debug(f"剔除了 {removed_count} 个异常值 (原始数据: {len(data)}, 范围: [{lower_bound:.2f}, {upper_bound:.2f}])")
    
    return filtered_data


def extract_valid_values(transactions: List[Dict], field_name: str) -> List[float]:
    """
    从交易记录中提取有效的数值字段
    
    Args:
        transactions: 交易记录列表
        field_name: 要提取的字段名
        
    Returns:
        有效数值列表
    """
    values = []
    for trans in transactions:
        value = trans.get(field_name)
        # 过滤掉无效值：None、空字符串、0和负数
        if value and isinstance(value, (int, float)) and value > 0:
            values.append(float(value))
    
    return values


def load_estate_data(file_path: str) -> Tuple[str, List[Dict]]:
    """
    加载小区数据文件
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        元组 (estate_id, transactions列表)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            estate_id = data.get('estate_id')
            transactions = data.get('transactions', [])
            return estate_id, transactions
    except Exception as e:
        logger.error(f"读取文件失败 {file_path}: {e}")
        return None, []


def calculate_rent_sale_ratio(base_dir: str = "./28hse/transaction_records_trans") -> Dict[str, float]:
    """
    计算平均租售比
    
    Args:
        base_dir: 数据目录路径
        
    Returns:
        字典 {estate_id: 租售比}
    """
    base_path = Path(base_dir)
    buy_dir = base_path / "buy"
    rent_dir = base_path / "rent"
    
    # 检查目录是否存在
    if not buy_dir.exists():
        logger.error(f"买卖数据目录不存在: {buy_dir}")
        return {}
    
    if not rent_dir.exists():
        logger.error(f"出租数据目录不存在: {rent_dir}")
        return {}
    
    # 获取所有JSON文件的ID（不含扩展名）
    buy_ids = {f.stem for f in buy_dir.glob("*.json")}
    rent_ids = {f.stem for f in rent_dir.glob("*.json")}
    
    # 找出同时存在于两个文件夹的ID
    common_ids = buy_ids & rent_ids
    
    logger.info(f"买卖数据文件数: {len(buy_ids)}")
    logger.info(f"出租数据文件数: {len(rent_ids)}")
    logger.info(f"同时存在的小区数: {len(common_ids)}")
    
    results = {}
    skipped_estates = []
    
    # 遍历所有共同ID
    for estate_id in sorted(common_ids, key=lambda x: int(x) if x.isdigit() else 0):
        logger.info(f"\n处理小区 ID: {estate_id}")
        
        # 加载买卖数据
        buy_file = buy_dir / f"{estate_id}.json"
        _, buy_transactions = load_estate_data(str(buy_file))
        
        # 加载出租数据
        rent_file = rent_dir / f"{estate_id}.json"
        _, rent_transactions = load_estate_data(str(rent_file))
        
        # 提取价格数据
        sale_prices = extract_valid_values(buy_transactions, 'price_per_sqft')
        rent_prices = extract_valid_values(rent_transactions, 'rent_per_sqft')
        
        logger.info(f"  原始售价数据量: {len(sale_prices)}")
        logger.info(f"  原始租金数据量: {len(rent_prices)}")
        
        # 检查数据是否充足
        if len(sale_prices) == 0 or len(rent_prices) == 0:
            logger.warning(f"  跳过小区 {estate_id}: 售价或租金数据为空")
            skipped_estates.append({
                'estate_id': estate_id,
                'reason': '数据为空',
                'sale_count': len(sale_prices),
                'rent_count': len(rent_prices)
            })
            continue
        
        # 剔除异常值
        sale_prices_filtered = remove_outliers_iqr(sale_prices)
        rent_prices_filtered = remove_outliers_iqr(rent_prices)
        
        logger.info(f"  剔除异常值后售价数据量: {len(sale_prices_filtered)}")
        logger.info(f"  剔除异常值后租金数据量: {len(rent_prices_filtered)}")
        
        # 再次检查数据是否充足
        if len(sale_prices_filtered) == 0 or len(rent_prices_filtered) == 0:
            logger.warning(f"  跳过小区 {estate_id}: 剔除异常值后数据不足")
            skipped_estates.append({
                'estate_id': estate_id,
                'reason': '剔除异常值后数据不足',
                'sale_count': len(sale_prices_filtered),
                'rent_count': len(rent_prices_filtered)
            })
            continue
        
        # 计算平均值
        avg_sale_price = np.mean(sale_prices_filtered)
        avg_rent_price = np.mean(rent_prices_filtered)
        
        # 计算租售比 = (月租金 * 12) / 售价
        # 这里的单位都是每平方英尺的价格
        rent_sale_ratio = (avg_rent_price * 12) / avg_sale_price
        
        # 将租售比转换为百分比形式更直观
        rent_sale_ratio_percent = rent_sale_ratio * 100
        
        results[estate_id] = round(rent_sale_ratio_percent, 4)
        
        logger.info(f"  平均售价: ${avg_sale_price:.2f}/平方英尺")
        logger.info(f"  平均月租金: ${avg_rent_price:.2f}/平方英尺")
        logger.info(f"  租售比: {rent_sale_ratio_percent:.4f}%")
    
    # 输出跳过的小区统计
    if skipped_estates:
        logger.info(f"\n跳过的小区数量: {len(skipped_estates)}")
        logger.info("跳过原因统计:")
        reason_counts = {}
        for estate in skipped_estates:
            reason = estate['reason']
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for reason, count in reason_counts.items():
            logger.info(f"  {reason}: {count} 个")
    
    logger.info(f"\n成功计算租售比的小区数量: {len(results)}")
    
    return results


def save_results(results: Dict[str, float], output_file: str = "average_rent_sale_ratio.json"):
    """
    保存结果到JSON文件
    
    Args:
        results: 租售比结果字典
        output_file: 输出文件名
    """
    try:
        # 添加元数据
        output_data = {
            "metadata": {
                "description": "平均租售比计算结果",
                "unit": "百分比 (%)",
                "formula": "(月租金单价 * 12) / 售价单价 * 100",
                "total_estates": len(results)
            },
            "data": results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n结果已保存到: {output_file}")
        
        # 输出一些统计信息
        if results:
            ratios = list(results.values())
            logger.info(f"\n租售比统计:")
            logger.info(f"  最小值: {min(ratios):.4f}%")
            logger.info(f"  最大值: {max(ratios):.4f}%")
            logger.info(f"  平均值: {np.mean(ratios):.4f}%")
            logger.info(f"  中位数: {np.median(ratios):.4f}%")
            
    except Exception as e:
        logger.error(f"保存结果失败: {e}")


def main():
    """主函数"""
    logger.info("="*60)
    logger.info("开始计算平均租售比")
    logger.info("="*60)
    
    # 计算租售比
    results = calculate_rent_sale_ratio()
    
    # 保存结果
    if results:
        save_results(results)
    else:
        logger.warning("没有计算出任何租售比数据")
    
    logger.info("\n处理完成!")


if __name__ == "__main__":
    main()
