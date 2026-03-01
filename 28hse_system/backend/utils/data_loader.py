"""
数据加载和整合工具
整合 estate_static_info.json 和 average_rent_sale_ratio.json
"""
import json
import os
from functools import lru_cache
from typing import Dict, List, Optional


class DataLoader:
    def __init__(self, base_path: str, transaction_buy_path: str = None):
        """
        初始化数据加载器
        :param base_path: 项目根目录路径
        :param transaction_buy_path: 交易数据路径（buy目录）
        """
        self.base_path = base_path
        # self.estate_static_path = '/home/zhangchi/Documents/28hse/centanet_system/crawler/estate_info_20260221_convert.json'
        # self.rent_ratio_path = '/home/zhangchi/Documents/28hse/centanet_system/crawler/average_rent_sale_ratio.json'
        self.estate_static_path = '/home/zhangchi/Documents/28hse/28hse_system/estate_static_info_convert.json'
        self.rent_ratio_path = '/home/zhangchi/Documents/28hse/28hse_system/average_rent_sale_ratio.json'
        self.housing_types_path = os.path.join(base_path, 'housing_types.json')
        
        # 设置交易数据路径（默认值）
        if transaction_buy_path:
            self.transaction_buy_path = transaction_buy_path
        else:
            self.transaction_buy_path = os.path.join(base_path, '28hse', 'transaction_records_20260227_trans', 'buy')
    
    @lru_cache(maxsize=1)
    def load_estate_static_info(self) -> Dict:
        """
        加载静态小区信息
        使用LRU缓存提高性能
        """
        try:
            with open(self.estate_static_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"错误: 未找到文件 {self.estate_static_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"错误: JSON解析失败 {e}")
            return {}
    
    @lru_cache(maxsize=1)
    def load_rent_ratio_data(self) -> Dict:
        """
        加载租售比数据
        使用LRU缓存提高性能
        """
        try:
            with open(self.rent_ratio_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('data', {})
        except FileNotFoundError:
            print(f"错误: 未找到文件 {self.rent_ratio_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"错误: JSON解析失败 {e}")
            return {}
    
    @lru_cache(maxsize=1)
    def load_housing_types(self) -> Dict:
        """
        加载公屋和居屋数据
        使用LRU缓存提高性能
        """
        try:
            with open(self.housing_types_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"错误: 未找到文件 {self.housing_types_path}")
            return {'gongwu': {'names': []}, 'juwu': {'names': []}}
        except json.JSONDecodeError as e:
            print(f"错误: JSON解析失败 {e}")
            return {'gongwu': {'names': []}, 'juwu': {'names': []}}
    
    def load_estate_transactions(self, estate_id: str) -> List[Dict]:
        """
        加载某个小区的交易记录
        :param estate_id: 小区ID
        :return: 交易记录列表
        """
        # 将estate_id转换为文件名（去除前缀）
        # 例如：'2-AABBCCDD' -> 'AABBCCDD.json'
        if '-' in estate_id:
            file_id = estate_id.split('-', 1)[1]
        else:
            file_id = estate_id
        
        transaction_file = os.path.join(self.transaction_buy_path, f"{file_id}.json")
        
        try:
            with open(transaction_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('transactions', [])
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as e:
            print(f"警告: 交易数据解析失败 {transaction_file}: {e}")
            return []
    
    def get_estate_area_range(self, estate_id: str) -> Dict:
        """
        获取小区的面积范围
        :param estate_id: 小区ID
        :return: {'min_area': float, 'max_area': float} 或 {}
        """
        transactions = self.load_estate_transactions(estate_id)
        
        if not transactions:
            return {}
        
        # 提取所有有效面积
        areas = []
        for trans in transactions:
            # 尝试saleable_area或area字段
            area = trans.get('saleable_area') or trans.get('area')
            if area and isinstance(area, (int, float)) and area > 0:
                areas.append(area)
        
        if not areas:
            return {}
        
        return {
            'min_area': min(areas),
            'max_area': max(areas)
        }
    
    def get_estate_current_price_per_sqft(self, estate_id: str) -> Optional[float]:
        """
        获取小区的当前尺价（最近5条记录的平均值）
        :param estate_id: 小区ID
        :return: 平均尺价或None
        """
        transactions = self.load_estate_transactions(estate_id)
        
        if not transactions:
            return None
        
        # 按交易日期排序（使用date字段）
        # 如果没有日期字段，则取最后5条
        sorted_trans = transactions
        if transactions and 'date' in transactions[0]:
            sorted_trans = sorted(transactions, key=lambda x: x.get('date', ''), reverse=True)
        
        # 取最新5条
        recent_trans = sorted_trans[:5]
        
        # 提取price_per_sqft
        prices = []
        for trans in recent_trans:
            price = trans.get('price_per_sqft')
            if price and isinstance(price, (int, float)) and price > 0:
                prices.append(price)
        
        if not prices:
            return None
        
        return sum(prices) / len(prices)
    
    def get_integrated_estates(self) -> List[Dict]:
        """
        获取整合后的小区数据列表
        只返回有坐标的小区(用于地图显示)
        """
        static_info = self.load_estate_static_info()
        rent_ratios = self.load_rent_ratio_data()
        housing_types = self.load_housing_types()
        
        # 建立名称到类型的映射
        gongwu_names = set(housing_types.get('gongwu', {}).get('names', []))
        juwu_names = set(housing_types.get('juwu', {}).get('names', []))
        
        integrated_list = []
        
        for estate_id, estate_data in static_info.items():
            # 检查是否有坐标信息
            coordinates = estate_data.get('coordinates')
            if not coordinates or not coordinates.get('latitude') or not coordinates.get('longitude'):
                continue
            
            # 整合租售比数据（支持时序数据）
            rent_ratio_data = rent_ratios.get(estate_id, {})
            if isinstance(rent_ratio_data, dict):
                overall_ratio_timeseries = rent_ratio_data.get('overall_ratio', {})
                room_type_ratio = rent_ratio_data.get('room_type_ratio', {})
                
                # 提取最新月份的租售比（用于地图颜色显示）
                if isinstance(overall_ratio_timeseries, dict) and overall_ratio_timeseries:
                    # 获取字典中最后一个值（最新月份）
                    latest_ratio = list(overall_ratio_timeseries.values())[-1]
                elif isinstance(overall_ratio_timeseries, (int, float)):
                    # 兼容旧格式（单一数值）
                    latest_ratio = overall_ratio_timeseries
                    overall_ratio_timeseries = {}
                else:
                    latest_ratio = None
                    overall_ratio_timeseries = {}
            else:
                # 兼容旧数据结构
                latest_ratio = rent_ratio_data if isinstance(rent_ratio_data, (int, float)) else None
                overall_ratio_timeseries = {}
                room_type_ratio = {}
            
            # 判断房屋类型
            estate_name = estate_data.get('name', '')
            housing_type = None
            if estate_name in gongwu_names:
                housing_type = 'gongwu'
            elif estate_name in juwu_names:
                housing_type = 'juwu'
            
            # 提取establish_year和primary_school
            basic_info = estate_data.get('basic_info', {})
            establish_year = estate_data.get('establish_year') or basic_info.get('establish_year')
            primary_school = estate_data.get('primary_school') or basic_info.get('primary_school')
            
            # 获取当前尺价
            current_price_per_sqft = self.get_estate_current_price_per_sqft(estate_id)
            
            integrated_list.append({
                'id': estate_id,
                'name': estate_data.get('name', ''),
                'address': estate_data.get('address', ''),
                'coordinates': coordinates,
                'rent_ratio': latest_ratio,  # 最新月份租售比（用于颜色映射）
                'overall_ratio_timeseries': overall_ratio_timeseries,  # 完整时序数据
                'room_type_ratio': room_type_ratio,
                'housing_type': housing_type,
                'establish_year': establish_year,
                'primary_school': primary_school,
                'current_price_per_sqft': current_price_per_sqft  # 当前尺价
            })
        
        return integrated_list
    
    def get_estate_detail(self, estate_id: str) -> Optional[Dict]:
        """
        获取特定小区的详细信息
        :param estate_id: 小区ID
        :return: 小区详细信息字典,如果不存在返回None
        """
        static_info = self.load_estate_static_info()
        rent_ratios = self.load_rent_ratio_data()
        
        estate_data = static_info.get(estate_id)
        if not estate_data:
            return None
        
        # 整合详细信息
        basic_info = estate_data.get('basic_info', {})
        
        # 处理时序租售比数据结构
        rent_ratio_data = rent_ratios.get(estate_id, {})
        if isinstance(rent_ratio_data, dict):
            overall_ratio_timeseries = rent_ratio_data.get('overall_ratio', {})
            room_type_ratio = rent_ratio_data.get('room_type_ratio', {})
            
            # 提取最新月份租售比
            if isinstance(overall_ratio_timeseries, dict) and overall_ratio_timeseries:
                latest_ratio = list(overall_ratio_timeseries.values())[-1]
            elif isinstance(overall_ratio_timeseries, (int, float)):
                latest_ratio = overall_ratio_timeseries
                overall_ratio_timeseries = {}
            else:
                latest_ratio = None
                overall_ratio_timeseries = {}
        else:
            latest_ratio = rent_ratio_data if isinstance(rent_ratio_data, (int, float)) else None
            overall_ratio_timeseries = {}
            room_type_ratio = {}
        
        # 获取面积范围
        area_range = self.get_estate_area_range(estate_id)
        
        # 获取平均尺价
        avg_price_per_sqft = self.get_estate_current_price_per_sqft(estate_id)
        
        detail = {
            'id': estate_id,
            'name': estate_data.get('name', ''),
            'address': estate_data.get('address', ''),
            'coordinates': estate_data.get('coordinates', {}),
            'rent_ratio': latest_ratio,  # 最新月份租售比
            'overall_ratio_timeseries': overall_ratio_timeseries,  # 完整时序数据
            'room_type_ratio': room_type_ratio,
            'establish_year': basic_info.get('establish_year', estate_data.get('establish_year', '')),
            'developer': basic_info.get('developer', estate_data.get('developer', '')),
            'building_count': basic_info.get('building_count', estate_data.get('building_count', '')),
            'units': basic_info.get('units', ''),
            'management_company': basic_info.get('management_company', ''),
            'facilities': basic_info.get('facilities', ''),
            'parking_spaces': basic_info.get('parking_spaces', ''),
            'primary_school': basic_info.get('primary_school', ''),
            'middle_school': basic_info.get('middle_school', ''),
            'min_area': area_range.get('min_area'),  # 最小面积
            'max_area': area_range.get('max_area'),   # 最大面积
            'avg_price_per_sqft': avg_price_per_sqft  # 平均尺价
        }
        
        return detail
    
    def get_rent_ratio_statistics(self) -> Dict:
        """
        获取租售比统计信息(最小值、最大值、平均值)
        用于前端色彩映射
        """
        rent_ratios = self.load_rent_ratio_data()
        
        if not rent_ratios:
            return {
                'min': 0,
                'max': 0,
                'average': 0,
                'count': 0,
                'data': {}
            }
        
        # 提取overall_ratio用于统计（提取最新月份值）
        overall_ratios = {}
        for estate_id, ratio_data in rent_ratios.items():
            if isinstance(ratio_data, dict):
                overall_ratio_timeseries = ratio_data.get('overall_ratio', {})
                # 提取最新月份的租售比
                if isinstance(overall_ratio_timeseries, dict) and overall_ratio_timeseries:
                    latest_ratio = list(overall_ratio_timeseries.values())[-1]
                elif isinstance(overall_ratio_timeseries, (int, float)):
                    # 兼容旧格式
                    latest_ratio = overall_ratio_timeseries
                else:
                    latest_ratio = None
            else:
                # 兼容旧数据结构
                latest_ratio = ratio_data if isinstance(ratio_data, (int, float)) else None
            
            if latest_ratio is not None:
                overall_ratios[estate_id] = latest_ratio
        
        values = list(overall_ratios.values())
        
        if not values:
            return {
                'min': 0,
                'max': 0,
                'average': 0,
                'count': 0,
                'data': {}
            }
        
        return {
            'min': min(values),
            'max': max(values),
            'average': sum(values) / len(values),
            'count': len(values),
            'data': overall_ratios
        }
    
    def search_estates_by_name(self, keyword: str) -> List[Dict]:
        """
        按小区名称模糊搜索
        :param keyword: 搜索关键词
        :return: 匹配的小区列表
        """
        if not keyword:
            return []
        
        all_estates = self.get_integrated_estates()
        
        # 模糊匹配小区名称(中文不区分大小写)
        matched = [
            estate for estate in all_estates
            if keyword in estate['name']
        ]
        
        # 限制返回最多50条结果
        return matched[:50]
