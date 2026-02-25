"""
数据加载和整合工具
整合 estate_static_info.json 和 average_rent_sale_ratio.json
"""
import json
import os
from functools import lru_cache
from typing import Dict, List, Optional


class DataLoader:
    def __init__(self, base_path: str):
        """
        初始化数据加载器
        :param base_path: 项目根目录路径
        """
        self.base_path = base_path
        self.estate_static_path = '/home/zhangchi/Documents/28hse/centanet_system/crawler/estate_info_20260221_convert.json'
        self.rent_ratio_path = '/home/zhangchi/Documents/28hse/centanet_system/crawler/average_rent_sale_ratio.json'
        self.housing_types_path = os.path.join(base_path, 'housing_types.json')
    
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
            
            # 整合租售比数据（新数据结构）
            rent_ratio_data = rent_ratios.get(estate_id, {})
            if isinstance(rent_ratio_data, dict):
                overall_ratio = rent_ratio_data.get('overall_ratio')
                room_type_ratio = rent_ratio_data.get('room_type_ratio', {})
            else:
                # 兼容旧数据结构
                overall_ratio = rent_ratio_data
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
            
            integrated_list.append({
                'id': estate_id,
                'name': estate_data.get('name', ''),
                'address': estate_data.get('address', ''),
                'coordinates': coordinates,
                'rent_ratio': overall_ratio,
                'room_type_ratio': room_type_ratio,
                'housing_type': housing_type,
                'establish_year': establish_year,
                'primary_school': primary_school
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
        
        # 处理新的租售比数据结构
        rent_ratio_data = rent_ratios.get(estate_id, {})
        if isinstance(rent_ratio_data, dict):
            overall_ratio = rent_ratio_data.get('overall_ratio')
            room_type_ratio = rent_ratio_data.get('room_type_ratio', {})
        else:
            overall_ratio = rent_ratio_data
            room_type_ratio = {}
        
        detail = {
            'id': estate_id,
            'name': estate_data.get('name', ''),
            'address': estate_data.get('address', ''),
            'coordinates': estate_data.get('coordinates', {}),
            'rent_ratio': overall_ratio,
            'room_type_ratio': room_type_ratio,
            'establish_year': basic_info.get('establish_year', estate_data.get('establish_year', '')),
            'developer': basic_info.get('developer', estate_data.get('developer', '')),
            'building_count': basic_info.get('building_count', estate_data.get('building_count', '')),
            'units': basic_info.get('units', ''),
            'management_company': basic_info.get('management_company', ''),
            'facilities': basic_info.get('facilities', ''),
            'parking_spaces': basic_info.get('parking_spaces', ''),
            'primary_school': basic_info.get('primary_school', ''),
            'middle_school': basic_info.get('middle_school', '')
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
        
        # 提取overall_ratio用于统计
        overall_ratios = {}
        for estate_id, ratio_data in rent_ratios.items():
            if isinstance(ratio_data, dict):
                overall_ratio = ratio_data.get('overall_ratio')
            else:
                overall_ratio = ratio_data
            
            if overall_ratio is not None:
                overall_ratios[estate_id] = overall_ratio
        
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
