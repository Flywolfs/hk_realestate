#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算平均租售比脚本

功能：
1. 读取transaction_records_trans文件夹中的买卖和出租数据
2. 找出同时存在于buy和rent文件夹中的小区ID
3. 对每个小区提取rent_per_sqft和price_per_sqft
4. 按户型(room_count)进行数据聚类，room_count=-1时根据面积差值聚类
5. 剔除异常值（使用IQR方法）
6. 计算整体租售比和各户型租售比
7. 输出结果到average_rent_sale_ratio.json
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def remove_outliers_iqr(data: List[float], enable_outlier_removal: bool = True) -> List[float]:
    """
    使用IQR(四分位距)方法剔除异常值
    
    Args:
        data: 原始数据列表
        enable_outlier_removal: 是否启用异常值剔除（开关）
        
    Returns:
        剔除异常值后的数据列表
    """
    if not enable_outlier_removal or len(data) < 4:  # 数据量太少或开关关闭,不剔除异常值
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


def cluster_by_room_type(transactions: List[Dict], min_date: Optional[str] = None) -> Dict[int, List[Dict]]:
    """
    根据room_count字段对交易记录进行户型聚类
    对于room_count=-1的记录，根据面积差值进行聚类
    
    Args:
        transactions: 交易记录列表
        min_date: 最早日期限制，格式为YYYY-MM-DD，只分析该日期之后的数据
        
    Returns:
        字典 {平均面积(整数): [交易记录列表]}
    """
    clusters = {}  # {room_count或平均面积: [transactions]}
    area_threshold = 0.08  # 8%的面积差值阈值
    
    # 解析最小日期
    min_date_obj = None
    if min_date:
        try:
            min_date_obj = datetime.strptime(min_date, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"无效的日期格式: {min_date}，将忽略日期限制")
    
    for trans in transactions:
        # 检查日期限制
        if min_date_obj:
            trans_date_str = trans.get('date')
            if trans_date_str:
                try:
                    trans_date = datetime.strptime(trans_date_str, "%Y-%m-%d")
                    if trans_date < min_date_obj:
                        continue  # 跳过早于最小日期的记录
                except ValueError:
                    pass  # 日期格式无效，保留该记录
        room_count = trans.get('room_count', -1)
        area = trans.get('area', 0)
        
        # 确保area是数值类型
        if isinstance(area, str):
            try:
                area = float(area)
            except (ValueError, TypeError):
                continue
        
        if not area or area <= 0:
            continue
            
        if room_count is not None and room_count > 0:
            # 有明确户型的记录，直接按room_count分类
            if room_count not in clusters:
                clusters[room_count] = []
            clusters[room_count].append(trans)
        else:
            # room_count为-1或空，需要根据面积匹配
            matched = False
            for key, cluster_trans in clusters.items():
                if not cluster_trans:
                    continue
                # 计算该聚类的平均面积
                cluster_areas = []
                for t in cluster_trans:
                    t_area = t.get('area', 0)
                    if isinstance(t_area, str):
                        try:
                            t_area = float(t_area)
                        except (ValueError, TypeError):
                            continue
                    if t_area > 0:
                        cluster_areas.append(t_area)
                
                if not cluster_areas:
                    continue
                avg_area = np.mean(cluster_areas)
                # 计算面积差值比例
                area_diff_ratio = abs(area - avg_area) / avg_area
                if area_diff_ratio < area_threshold:
                    clusters[key].append(trans)
                    matched = True
                    break
            
            # 如果没有匹配到任何聚类，创建新聚类（使用当前面积作为key）
            if not matched:
                # 使用负数表示这是基于面积创建的聚类
                new_key = -area
                clusters[new_key] = [trans]
    
    # 将聚类的key转换为平均面积（四舍五入为整数）
    result_clusters = {}
    for key, cluster_trans in clusters.items():
        if not cluster_trans:
            continue
        # 计算该聚类的平均面积
        cluster_areas = []
        for t in cluster_trans:
            t_area = t.get('area', 0)
            if isinstance(t_area, str):
                try:
                    t_area = float(t_area)
                except (ValueError, TypeError):
                    continue
            if t_area > 0:
                cluster_areas.append(t_area)
        
        if cluster_areas:
            avg_area = int(round(np.mean(cluster_areas)))
            result_clusters[avg_area] = cluster_trans
    
    return result_clusters


def extract_valid_values(transactions: List[Dict], field_name: str, min_date: Optional[str] = None) -> List[float]:
    """
    从交易记录中提取有效的数值字段
    
    Args:
        transactions: 交易记录列表
        field_name: 要提取的字段名
        min_date: 最早日期限制，格式为YYYY-MM-DD，只分析该日期之后的数据
        
    Returns:
        有效数值列表
    """
    values = []
    
    # 解析最小日期
    min_date_obj = None
    if min_date:
        try:
            min_date_obj = datetime.strptime(min_date, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"无效的日期格式: {min_date}，将忽略日期限制")
    
    for trans in transactions:
        # 检查日期限制
        if min_date_obj:
            trans_date_str = trans.get('date')
            if trans_date_str:
                try:
                    trans_date = datetime.strptime(trans_date_str, "%Y-%m-%d")
                    if trans_date < min_date_obj:
                        continue  # 跳过早于最小日期的记录
                except ValueError:
                    pass  # 日期格式无效，保留该记录
        
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


def calculate_ratio_for_cluster(sale_prices: List[float], rent_prices: List[float], 
                                enable_outlier_removal: bool = True) -> float:
    """
    计算一组数据的租售比
    
    Args:
        sale_prices: 售价列表
        rent_prices: 租金列表
        enable_outlier_removal: 是否启用异常值剔除
        
    Returns:
        租售比百分比，如果数据不足则返回None
    """
    if len(sale_prices) == 0 or len(rent_prices) == 0:
        return None
    
    # 剔除异常值
    sale_prices_filtered = remove_outliers_iqr(sale_prices, enable_outlier_removal)
    rent_prices_filtered = remove_outliers_iqr(rent_prices, enable_outlier_removal)
    
    # 再次检查数据是否充足
    if len(sale_prices_filtered) == 0 or len(rent_prices_filtered) == 0:
        return None
    
    # 计算平均值
    avg_sale_price = np.mean(sale_prices_filtered)
    avg_rent_price = np.mean(rent_prices_filtered)
    
    # 计算租售比 = (月租金 * 12) / 售价
    rent_sale_ratio = (avg_rent_price * 12) / avg_sale_price
    
    # 将租售比转换为百分比形式
    return round(rent_sale_ratio * 100, 4)


def calculate_rent_sale_ratio(base_dir: str = "./28hse/transaction_records_trans",
                               enable_outlier_removal: bool = True,
                               min_date: Optional[str] = None) -> Dict:
    """
    计算平均租售比
    
    Args:
        base_dir: 数据目录路径
        enable_outlier_removal: 是否启用异常值剔除
        min_date: 最早日期限制，格式为YYYY-MM-DD，只分析该日期之后的数据
        
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
    if min_date:
        logger.info(f"日期限制: 只分析 {min_date} 之后的数据")
    
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
        
        # 检查数据是否充足
        if not buy_transactions or not rent_transactions:
            logger.warning(f"  跳过小区 {estate_id}: 买卖或出租数据为空")
            skipped_estates.append({
                'estate_id': estate_id,
                'reason': '数据为空',
                'buy_count': len(buy_transactions),
                'rent_count': len(rent_transactions)
            })
            continue
        
        # 对买卖和出租数据分别进行户型聚类（应用日期限制）
        buy_clusters = cluster_by_room_type(buy_transactions, min_date)
        rent_clusters = cluster_by_room_type(rent_transactions, min_date)
        
        logger.info(f"  买卖数据户型聚类: {len(buy_clusters)} 个户型")
        logger.info(f"  出租数据户型聚类: {len(rent_clusters)} 个户型")
        
        # 计算整体租售比（应用日期限制）
        overall_sale_prices = extract_valid_values(buy_transactions, 'price_per_sqft', min_date)
        overall_rent_prices = extract_valid_values(rent_transactions, 'rent_per_sqft', min_date)
        
        overall_ratio = calculate_ratio_for_cluster(
            overall_sale_prices, 
            overall_rent_prices, 
            enable_outlier_removal
        )
        
        if overall_ratio is None:
            logger.warning(f"  跳过小区 {estate_id}: 整体数据不足以计算租售比")
            skipped_estates.append({
                'estate_id': estate_id,
                'reason': '整体数据不足',
                'sale_count': len(overall_sale_prices),
                'rent_count': len(overall_rent_prices)
            })
            continue
        
        logger.info(f"  整体租售比: {overall_ratio:.4f}%")
        
        # 计算各户型的租售比
        room_type_ratios = {}
        area_threshold = 0.08  # 8%的面积差值阈值
        
        # 用于记录已匹配的rent_cluster，避免重复匹配
        matched_rent_areas = set()
        
        # 遍历买卖数据的每个户型聚类
        for buy_area in sorted(buy_clusters.keys()):
            buy_cluster_trans = buy_clusters[buy_area]
            
            # 在出租数据中寻找匹配的户型（直接相等或面积差值<8%）
            matched_rent_area = None
            
            # 首先检查是否有完全相同的面积
            if buy_area in rent_clusters and buy_area not in matched_rent_areas:
                matched_rent_area = buy_area
            else:
                # 没有完全相同的，寻找面积差值<8%的
                for rent_area in rent_clusters.keys():
                    if rent_area in matched_rent_areas:
                        continue
                    # 计算面积差值比例
                    area_diff_ratio = abs(buy_area - rent_area) / max(buy_area, rent_area)
                    if area_diff_ratio < area_threshold:
                        matched_rent_area = rent_area
                        break
            
            if matched_rent_area is None:
                # 没有找到匹配的出租户型，跳过
                logger.debug(f"    买卖户型面积 {buy_area}平方英尺: 未找到匹配的出租户型")
                continue
            
            # 标记该出租户型已被匹配
            matched_rent_areas.add(matched_rent_area)
            rent_cluster_trans = rent_clusters[matched_rent_area]
            
            # 提取价格数据（应用日期限制）
            cluster_sale_prices = extract_valid_values(buy_cluster_trans, 'price_per_sqft', min_date)
            cluster_rent_prices = extract_valid_values(rent_cluster_trans, 'rent_per_sqft', min_date)
            
            # 计算该户型的租售比
            cluster_ratio = calculate_ratio_for_cluster(
                cluster_sale_prices,
                cluster_rent_prices,
                enable_outlier_removal
            )
            
            if cluster_ratio is not None:
                # 使用买卖和出租的平均面积作为key
                avg_area = int(round((buy_area + matched_rent_area) / 2))
                room_type_ratios[str(avg_area)] = cluster_ratio
                
                if buy_area == matched_rent_area:
                    logger.info(f"    户型面积 {avg_area}平方英尺: 租售比 {cluster_ratio:.4f}% "
                              f"(买{len(cluster_sale_prices)}条, 租{len(cluster_rent_prices)}条)")
                else:
                    logger.info(f"    户型面积 {avg_area}平方英尺: 租售比 {cluster_ratio:.4f}% "
                              f"(买{len(cluster_sale_prices)}条@{buy_area}ft², "
                              f"租{len(cluster_rent_prices)}条@{matched_rent_area}ft²)")
            else:
                logger.debug(f"    户型面积 {buy_area}/{matched_rent_area}平方英尺: 数据不足，跳过")
        
        # 保存结果
        results[estate_id] = {
            "overall_ratio": overall_ratio,
            "room_type_ratio": room_type_ratios
        }
        
        logger.info(f"  成功计算 {len(room_type_ratios)} 个户型的租售比")
    
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


def save_results(results: Dict, output_file: str = "average_rent_sale_ratio.json"):
    """
    保存结果到JSON文件
    
    Args:
        results: 租售比结果字典 {estate_id: {overall_ratio, room_type_ratio}}
        output_file: 输出文件名
    """
    try:
        # 添加元数据
        output_data = {
            "metadata": {
                "description": "平均租售比计算结果（整体及分户型）",
                "unit": "百分比 (%)",
                "formula": "(月租金单价 * 12) / 售价单价 * 100",
                "total_estates": len(results),
                "clustering_method": "基于room_count字段，room_count=-1时根据面积差值<8%进行聚类"
            },
            "data": results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n结果已保存到: {output_file}")
        
        # 输出一些统计信息
        if results:
            overall_ratios = [v["overall_ratio"] for v in results.values() if v.get("overall_ratio")]
            
            if overall_ratios:
                logger.info(f"\n整体租售比统计:")
                logger.info(f"  最小值: {min(overall_ratios):.4f}%")
                logger.info(f"  最大值: {max(overall_ratios):.4f}%")
                logger.info(f"  平均值: {np.mean(overall_ratios):.4f}%")
                logger.info(f"  中位数: {np.median(overall_ratios):.4f}%")
            
            # 统计户型数据
            total_room_types = sum(len(v.get("room_type_ratio", {})) for v in results.values())
            estates_with_room_types = sum(1 for v in results.values() if v.get("room_type_ratio"))
            
            logger.info(f"\n户型租售比统计:")
            logger.info(f"  有户型数据的小区数: {estates_with_room_types}")
            logger.info(f"  总户型数量: {total_room_types}")
            if estates_with_room_types > 0:
                logger.info(f"  平均每小区户型数: {total_room_types / estates_with_room_types:.2f}")
            
    except Exception as e:
        logger.error(f"保存结果失败: {e}")


def main():
    """主函数"""
    logger.info("="*60)
    logger.info("开始计算平均租售比")
    logger.info("="*60)
    
    # 计算租售比
    # 示例：设置最早日期为2025-01-01，只分析该日期之后的数据
    # results = calculate_rent_sale_ratio(base_dir="./transaction_record_20260223_trans", min_date="2025-01-01")
    min_date = "2025-01-01"
    results = calculate_rent_sale_ratio(base_dir="./transaction_record_20260223_trans", min_date=min_date)
    
    # 保存结果
    if results:
        save_results(results)
    else:
        logger.warning("没有计算出任何租售比数据")
    
    logger.info("\n处理完成!")


if __name__ == "__main__":
    main()
