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
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
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
            if avg_area in result_clusters:
                result_clusters[avg_area].extend(cluster_trans)
            else:
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
    return round(float(rent_sale_ratio * 100), 4)


def get_month_key(date_obj: datetime) -> str:
    """将日期转换为YYYY-MM格式的月份key"""
    return date_obj.strftime("%Y-%m")


def generate_monthly_ratios(buy_transactions: List[Dict], rent_transactions: List[Dict],
                            min_date: Optional[str] = None,
                            enable_outlier_removal: bool = True) -> Dict[str, float]:
    """
    按月计算租售比，从min_date开始每个月生成一个租售比
    如果某个月没有数据，使用上个月的最后一个价格数据填补
    
    Args:
        buy_transactions: 买卖交易记录列表
        rent_transactions: 出租交易记录列表
        min_date: 最早日期限制，格式为YYYY-MM-DD
        enable_outlier_removal: 是否启用异常值剔除
        
    Returns:
        字典 {月份(YYYY-MM): 租售比}
    """
    monthly_ratios = {}
    
    # 解析最小日期
    start_date = datetime.strptime(min_date, "%Y-%m-%d") if min_date else datetime(2025, 1, 1)
    end_date = datetime.now()
    
    # 按月份聚合买卖数据
    buy_monthly = {}  # {月份: [price_per_sqft列表]}
    for trans in buy_transactions:
        date_str = trans.get('date')
        if not date_str:
            continue
        try:
            trans_date = datetime.strptime(date_str, "%Y-%m-%d")
            if trans_date < start_date:
                continue
            month_key = get_month_key(trans_date)
            price = trans.get('price_per_sqft')
            if price and isinstance(price, (int, float)) and price > 0:
                if month_key not in buy_monthly:
                    buy_monthly[month_key] = []
                buy_monthly[month_key].append(float(price))
        except (ValueError, TypeError):
            continue
    
    # 按月份聚合出租数据
    rent_monthly = {}  # {月份: [rent_per_sqft列表]}
    for trans in rent_transactions:
        date_str = trans.get('date')
        if not date_str:
            continue
        try:
            trans_date = datetime.strptime(date_str, "%Y-%m-%d")
            if trans_date < start_date:
                continue
            month_key = get_month_key(trans_date)
            rent_price = trans.get('rent_per_sqft')
            if rent_price and isinstance(rent_price, (int, float)) and rent_price > 0:
                if month_key not in rent_monthly:
                    rent_monthly[month_key] = []
                rent_monthly[month_key].append(float(rent_price))
        except (ValueError, TypeError):
            continue
    
    # 获取所有需要计算的月份
    all_months = set(buy_monthly.keys()) | set(rent_monthly.keys())
    if not all_months:
        return monthly_ratios
    
    # 确定计算范围：从min_date到最新数据月份
    min_month = get_month_key(start_date)
    max_month = max(all_months) if all_months else min_month
    
    # 生成连续的月份列表
    current_date = start_date
    months_list = []
    while get_month_key(current_date) <= max_month:
        months_list.append(get_month_key(current_date))
        current_date += relativedelta(months=1)
    
    # 用于保存上个月的最后一个价格（用于填补缺失数据）
    last_sale_prices = []  # 上个月的销售价格列表
    last_rent_prices = []  # 上个月的出租价格列表
    
    # 按月计算租售比
    for month_key in months_list:
        # 获取当前月的买卖数据
        if month_key in buy_monthly and buy_monthly[month_key]:
            current_sale_prices = buy_monthly[month_key]
            last_sale_prices = current_sale_prices.copy()
        else:
            # 使用上个月的数据填补
            current_sale_prices = last_sale_prices.copy()
        
        # 获取当前月的出租数据
        if month_key in rent_monthly and rent_monthly[month_key]:
            current_rent_prices = rent_monthly[month_key]
            last_rent_prices = current_rent_prices.copy()
        else:
            # 使用上个月的数据填补
            current_rent_prices = last_rent_prices.copy()
        
        # 计算该月的租售比
        if current_sale_prices and current_rent_prices:
            ratio = calculate_ratio_for_cluster(
                current_sale_prices,
                current_rent_prices,
                enable_outlier_removal
            )
            if ratio is not None:
                monthly_ratios[month_key] = ratio
    
    return monthly_ratios


def generate_room_type_ratios_for_latest_month(
        buy_transactions: List[Dict],
        rent_transactions: List[Dict],
        min_date: Optional[str] = None,
        enable_outlier_removal: bool = True) -> Dict[str, float]:
    """
    按月计算各户型的租售比，逻辑与 generate_monthly_ratios 一致：
    - 先将买卖和出租数据分别按 (户型聚类key, 月份) 聚合
    - 对每个户型按月遍历，缺数据时用上月价格填补
    - 只返回最新月份的各户型租售比

    Args:
        buy_transactions: 买卖交易记录列表
        rent_transactions: 出租交易记录列表
        min_date: 最早日期限制，格式为YYYY-MM-DD
        enable_outlier_removal: 是否启用异常值剔除

    Returns:
        字典 {平均面积(str): 最新月份租售比}
    """
    area_threshold = 0.08  # 8%的面积差值阈值

    # 解析 min_date
    start_date = datetime.strptime(min_date, "%Y-%m-%d") if min_date else datetime(2025, 1, 1)

    def get_area(trans):
        """安全地获取交易记录中的面积值"""
        a = trans.get('area', 0)
        if isinstance(a, str):
            try:
                a = float(a)
            except (ValueError, TypeError):
                return None
        return a if a and a > 0 else None

    def assign_to_cluster(clusters_meta: Dict, area: float) -> Optional[int]:
        """
        尝试将面积 area 分配到已有聚类中（8%容差）。
        clusters_meta: {cluster_key: avg_area}
        返回匹配的 cluster_key，若无则返回 None。
        """
        for key, avg in clusters_meta.items():
            if abs(area - avg) / max(area, avg) < area_threshold:
                return key
        return None

    # ------------------------------------------------------------------ #
    # Step 1: 将买卖和出租数据分别聚类并按月聚合                            #
    # 结构: buy_cluster_monthly[cluster_key][month_key] = [price_per_sqft] #
    # ------------------------------------------------------------------ #
    def build_cluster_monthly(transactions, price_field):
        """
        返回:
          cluster_monthly: {cluster_key: {month_key: [price]}}
          clusters_meta:   {cluster_key: current_avg_area}  — 随数据更新
        """
        cluster_monthly = {}
        clusters_meta = {}   # {cluster_key: avg_area}
        cluster_areas = {}   # {cluster_key: [all_areas_so_far]}
        next_key = 0         # 简单自增 key，与 room_count/area 无关

        for trans in transactions:
            # 日期过滤
            date_str = trans.get('date')
            if not date_str:
                continue
            try:
                trans_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if trans_date < start_date:
                continue

            area = get_area(trans)
            if area is None:
                continue

            price = trans.get(price_field)
            if not price or not isinstance(price, (int, float)) or price <= 0:
                continue

            month_key = get_month_key(trans_date)

            # 先尝试用 room_count 归类
            room_count = trans.get('room_count', -1)
            if room_count is not None and room_count > 0:
                # 使用 room_count 作为聚类 key
                ck = f"rc_{room_count}"
            else:
                # 根据面积容差匹配已有聚类
                ck_found = assign_to_cluster(clusters_meta, area)
                if ck_found is not None:
                    ck = ck_found
                else:
                    ck = f"area_{next_key}"
                    next_key += 1

            # 维护聚类元数据
            if ck not in clusters_meta:
                clusters_meta[ck] = area
                cluster_areas[ck] = [area]
                cluster_monthly[ck] = {}
            else:
                cluster_areas[ck].append(area)
                clusters_meta[ck] = float(np.mean(cluster_areas[ck]))

            if month_key not in cluster_monthly[ck]:
                cluster_monthly[ck][month_key] = []
            cluster_monthly[ck][month_key].append(float(price))

        return cluster_monthly, clusters_meta, cluster_areas

    buy_cluster_monthly, buy_meta, buy_areas_map = build_cluster_monthly(
        buy_transactions, 'price_per_sqft')
    rent_cluster_monthly, rent_meta, rent_areas_map = build_cluster_monthly(
        rent_transactions, 'rent_per_sqft')

    # ------------------------------------------------------------------ #
    # Step 2: 确定全局月份范围                                              #
    # ------------------------------------------------------------------ #
    all_months = set()
    for monthly in buy_cluster_monthly.values():
        all_months.update(monthly.keys())
    for monthly in rent_cluster_monthly.values():
        all_months.update(monthly.keys())

    if not all_months:
        return {}

    max_month = max(all_months)
    months_list = []
    cur = start_date
    while get_month_key(cur) <= max_month:
        months_list.append(get_month_key(cur))
        cur += relativedelta(months=1)

    # ------------------------------------------------------------------ #
    # Step 3: 对每个买卖聚类，按月遍历（缺数据时用上月填补），                #
    #         匹配对应出租聚类，计算最新月份的租售比                          #
    # ------------------------------------------------------------------ #
    # 先建立 buy_cluster -> best_rent_cluster 的面积匹配映射
    matched_rent_for_buy = {}     # {buy_ck: rent_ck}
    matched_rent_used = set()

    for buy_ck, buy_avg in buy_meta.items():
        best_rent_ck = None
        best_diff = float('inf')
        for rent_ck, rent_avg in rent_meta.items():
            if rent_ck in matched_rent_used:
                continue
            diff = abs(buy_avg - rent_avg) / max(buy_avg, rent_avg)
            if diff < area_threshold and diff < best_diff:
                best_diff = diff
                best_rent_ck = rent_ck
        if best_rent_ck is not None:
            matched_rent_for_buy[buy_ck] = best_rent_ck
            matched_rent_used.add(best_rent_ck)

    room_type_ratios = {}

    for buy_ck, rent_ck in matched_rent_for_buy.items():
        buy_monthly = buy_cluster_monthly.get(buy_ck, {})
        rent_monthly_data = rent_cluster_monthly.get(rent_ck, {})

        last_sale_prices = []
        last_rent_prices = []
        latest_ratio = None

        for month_key in months_list:
            if month_key in buy_monthly and buy_monthly[month_key]:
                cur_sale = buy_monthly[month_key]
                last_sale_prices = cur_sale
            else:
                cur_sale = last_sale_prices

            if month_key in rent_monthly_data and rent_monthly_data[month_key]:
                cur_rent = rent_monthly_data[month_key]
                last_rent_prices = cur_rent
            else:
                cur_rent = last_rent_prices

            if cur_sale and cur_rent:
                ratio = calculate_ratio_for_cluster(
                    cur_sale, cur_rent, enable_outlier_removal)
                if ratio is not None:
                    latest_ratio = ratio

        if latest_ratio is None:
            continue

        # 用买卖和出租聚类的平均面积均值作为 key
        buy_avg_area = buy_meta[buy_ck]
        rent_avg_area = rent_meta[rent_ck]
        avg_area = int(round((buy_avg_area + rent_avg_area) / 2))
        room_type_ratios[str(avg_area)] = round(float(latest_ratio), 4)

    return room_type_ratios


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
        
        # 计算按月整体租售比（从min_date开始，每个月一个租售比）
        monthly_ratios = generate_monthly_ratios(
            buy_transactions,
            rent_transactions,
            min_date,
            enable_outlier_removal
        )
        
        if not monthly_ratios:
            logger.warning(f"  跳过小区 {estate_id}: 没有足够的数据计算租售比")
            skipped_estates.append({
                'estate_id': estate_id,
                'reason': '没有足够的数据计算租售比',
                'buy_count': len(buy_transactions),
                'rent_count': len(rent_transactions)
            })
            continue
        
        # 获取最新的租售比用于日志显示
        latest_month = max(monthly_ratios.keys())
        latest_ratio = monthly_ratios[latest_month]
        logger.info(f"  按月租售比: 共 {len(monthly_ratios)} 个月份，最新({latest_month}): {latest_ratio:.4f}%")
        
        # 计算各户型的租售比（与月度计算逻辑一致，只返回最新月份的户型租售比）
        room_type_ratios = generate_room_type_ratios_for_latest_month(
            buy_transactions,
            rent_transactions,
            min_date,
            enable_outlier_removal
        )
        
        # 保存结果
        results[estate_id] = {
            "overall_ratio": monthly_ratios,
            "room_type_ratio": room_type_ratios
        }
        
        logger.info(f"  成功计算 {len(room_type_ratios)} 个户型的租售比（最新月份: {latest_month}）")
    
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
                 其中 overall_ratio 是字典 {月份: 租售比}
        output_file: 输出文件名
    """
    try:
        # 对 results 进行排序，确保 estate_id 按数字顺序排列
        # 同时对每个小区内的 room_type_ratio 也按数字顺序排序
        # 对 overall_ratio 按月份排序
        sorted_results = {}
        for estate_id in sorted(results.keys(), key=lambda x: int(x) if x.isdigit() else x):
            estate_data = results[estate_id]
            # 对 room_type_ratio 按面积（数字）排序
            sorted_room_types = {}
            if "room_type_ratio" in estate_data:
                sorted_room_types = {
                    k: estate_data["room_type_ratio"][k]
                    for k in sorted(estate_data["room_type_ratio"].keys(), key=lambda x: int(x) if x.isdigit() else x)
                }
            # 对 overall_ratio 按月份排序
            sorted_monthly_ratios = {}
            if "overall_ratio" in estate_data and estate_data["overall_ratio"]:
                sorted_monthly_ratios = {
                    k: estate_data["overall_ratio"][k]
                    for k in sorted(estate_data["overall_ratio"].keys())
                }
            sorted_results[estate_id] = {
                "overall_ratio": sorted_monthly_ratios,
                "room_type_ratio": sorted_room_types
            }
        
        # 添加元数据
        output_data = {
            "metadata": {
                "description": "平均租售比计算结果（按月及分户型）",
                "unit": "百分比 (%)",
                "formula": "(月租金单价 * 12) / 售价单价 * 100",
                "total_estates": len(results),
                "clustering_method": "基于room_count字段，room_count=-1时根据面积差值<8%进行聚类",
                "overall_ratio_format": "按月计算，key为YYYY-MM格式，value为当月租售比",
                "room_type_ratio_format": "与月度整体计算逻辑一致，缺数据时向前填补，只保存最新月份的各户型租售比"
            },
            "data": sorted_results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n结果已保存到: {output_file}")
        
        # 输出一些统计信息
        if results:
            # 统计所有月份的租售比
            all_monthly_ratios = []
            for estate_data in results.values():
                monthly_ratios = estate_data.get("overall_ratio", {})
                all_monthly_ratios.extend(monthly_ratios.values())
            
            if all_monthly_ratios:
                logger.info(f"\n按月租售比统计:")
                logger.info(f"  总记录数: {len(all_monthly_ratios)} 个月份数据")
                logger.info(f"  最小值: {min(all_monthly_ratios):.4f}%")
                logger.info(f"  最大值: {max(all_monthly_ratios):.4f}%")
                logger.info(f"  平均值: {np.mean(all_monthly_ratios):.4f}%")
                logger.info(f"  中位数: {np.median(all_monthly_ratios):.4f}%")
            
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
    results = calculate_rent_sale_ratio(base_dir="./transaction_record_20260411_trans", min_date=min_date)
    
    # 保存结果
    if results:
        save_results(results)
    else:
        logger.warning("没有计算出任何租售比数据")
    
    logger.info("\n处理完成!")


if __name__ == "__main__":
    main()
