"""
数据加载和整合工具
整合 estate_static_info.json 和 average_rent_sale_ratio.json

数据源模式由 data_config.py 统一管理：
  - local 模式：直接读取 data_config.LOCAL_PATHS 中配置的本地路径（默认）
  - cos 模式  ：启动时从微信云托管对象存储下载文件到本地缓存目录后读取
"""
import json
import os
from functools import lru_cache
from typing import Dict, List, Optional

from utils import data_config


def _resolve_paths(base_path: str) -> dict:
    """
    根据 DATA_MODE 解析各数据文件的实际本地路径。
    cos 模式下，先将文件从 COS 下载到本地缓存目录，再返回缓存路径。
    """
    if data_config.DATA_MODE == 'cos':
        return _download_from_cos()
    else:
        # local 模式：直接使用配置的本地路径
        # housing_types.json 特殊处理：支持 base_path 动态计算
        paths = dict(data_config.LOCAL_PATHS)
        if not os.path.isabs(paths.get('housing_types', '')):
            paths['housing_types'] = os.path.join(base_path, 'housing_types.json')
        return paths


def _download_from_cos() -> dict:
    """
    从微信云托管对象存储（COS）批量下载数据文件到本地缓存目录。
    返回各文件的本地缓存路径字典。
    """
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        raise ImportError(
            "COS 模式需要安装 cos-python-sdk-v5，请执行：pip install cos-python-sdk-v5"
        )

    cache_dir = data_config.COS_LOCAL_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)

    config = CosConfig(
        Region=data_config.COS_REGION,
        SecretId=data_config.COS_SECRET_ID,
        SecretKey=data_config.COS_SECRET_KEY,
    )
    client = CosS3Client(config)
    bucket = data_config.COS_BUCKET

    local_paths = {}
    for key_name, cos_key in data_config.COS_KEYS.items():
        local_file = os.path.join(cache_dir, os.path.basename(cos_key))
        try:
            client.download_file(
                Bucket=bucket,
                Key=cos_key,
                DestFilePath=local_file,
            )
            print(f"[COS] 下载成功: {cos_key} -> {local_file}")
        except Exception as e:
            print(f"[COS] 下载失败: {cos_key}: {e}")
            # 若本地缓存已有旧文件则继续使用，否则保留空路径（加载时会报 FileNotFoundError）
        local_paths[key_name] = local_file

    # transaction_buy_dir 在 COS 模式下不使用（已由 dynamic_estate_data 替代）
    local_paths['transaction_buy_dir'] = os.path.join(cache_dir, 'buy')
    return local_paths


class DataLoader:
    def __init__(self, base_path: str, transaction_buy_path: str = None):
        """
        初始化数据加载器
        :param base_path: 项目根目录路径（用于 local 模式下 housing_types.json 的相对路径计算）
        :param transaction_buy_path: 交易数据路径（buy目录，本地回退用）
        """
        self.base_path = base_path

        # 解析数据文件路径（local 直接使用配置路径，cos 先下载再返回缓存路径）
        paths = _resolve_paths(base_path)

        self.estate_static_path       = paths['estate_static']
        self.rent_ratio_path          = paths['rent_ratio']
        self.housing_types_path       = paths['housing_types']
        self.price_trend_path         = paths['price_trend']
        self.dynamic_estate_data_path = paths['dynamic_estate_data']

        # 设置交易数据路径（仅本地开发回退用，cos 模式下通常不会执行到）
        if transaction_buy_path:
            self.transaction_buy_path = transaction_buy_path
        else:
            self.transaction_buy_path = paths.get('transaction_buy_dir', '')
    
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
    
    @lru_cache(maxsize=1)
    def load_price_trend_by_numeric_id(self) -> Dict:
        """
        加载尺价趋势数据，以 typeCode 为键转换成以 typeCode 本身为键（即 numeric_id）的字典。
        estate_static 文件的 key 即为 typeCode，value 含 name 字段，
        无需额外的 estate_info 文件建立映射。
        :return: {typeCode: monthly_price_trend_dict}
        """
        try:
            # 加载尺价趋势文件（typeCode 为键）
            with open(self.price_trend_path, 'r', encoding='utf-8') as f:
                trend_by_typecode = json.load(f)

            # estate_static 的 key 就是 typeCode，直接用于过滤（只保留存在于 static 中的条目）
            static = self.load_estate_static_info()

            result = {}
            for typecode, trend_data in trend_by_typecode.items():
                if typecode in static:
                    result[typecode] = trend_data.get('monthly_price_trend', {})

            return result
        except FileNotFoundError as e:
            print(f"警告: 尺价趋势文件未找到: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"警告: 尺价趋势数据解析失败: {e}")
            return {}
    
    @lru_cache(maxsize=1)
    def load_dynamic_estate_data(self) -> Dict:
        """
        加载预计算的动态小区数据（面积范围 + 当前尺价）
        由 preprocess_dynamic_estate_data.py 预先生成
        使用LRU缓存提高性能
        """
        try:
            with open(self.dynamic_estate_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告: 未找到预计算数据文件 {self.dynamic_estate_data_path}，将回退到实时读取交易记录")
            return {}
        except json.JSONDecodeError as e:
            print(f"警告: 预计算数据解析失败 {e}，将回退到实时读取交易记录")
            return {}

    def load_estate_transactions(self, estate_id: str) -> List[Dict]:
        """
        加载某个小区的交易记录
        :param estate_id: 小区ID
        :return: 交易记录列表
        """
        # 将estate_id转换为文件名（去除前缀）
        # 例如：'2-AABBCCDD' -> 'AABBCCDD.json'
        # if '-' in estate_id:
        #     file_id = estate_id.split('-', 1)[1]
        # else:
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
        优先从预计算的 dynamic_estate_data.json 读取，未找到时回退到实时读取交易记录
        :param estate_id: 小区ID
        :return: {'min_area': float, 'max_area': float} 或 {}
        """
        # 优先读预计算数据
        dynamic_data = self.load_dynamic_estate_data()
        if estate_id in dynamic_data:
            entry = dynamic_data[estate_id]
            if 'min_area' in entry and 'max_area' in entry:
                return {'min_area': entry['min_area'], 'max_area': entry['max_area']}

        # 回退：实时读取交易记录文件
        transactions = self.load_estate_transactions(estate_id)
        if not transactions:
            return {}

        areas = []
        for trans in transactions:
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
        优先从预计算的 dynamic_estate_data.json 读取，未找到时回退到实时读取交易记录
        :param estate_id: 小区ID
        :return: 平均尺价或None
        """
        # 优先读预计算数据
        dynamic_data = self.load_dynamic_estate_data()
        if estate_id in dynamic_data:
            price = dynamic_data[estate_id].get('current_price_per_sqft')
            if price is not None:
                return price

        # 回退：实时读取交易记录文件
        transactions = self.load_estate_transactions(estate_id)
        if not transactions:
            return None

        # 取最新5条
        recent_trans = transactions[:5]
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
                # 注意：overall_ratio_timeseries 和 room_type_ratio 已移至详情接口
                # 以减少列表接口的响应体积（微信云托管限制1MB）
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
        
        # 获取尺价趋势时序
        price_trend_data = self.load_price_trend_by_numeric_id()
        price_trend_timeseries = price_trend_data.get(estate_id, {})
        
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
            'avg_price_per_sqft': avg_price_per_sqft,  # 平均尺价
            'price_trend_timeseries': price_trend_timeseries  # 尺价趋势时序
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
    
    def reload(self):
        """
        热重载数据：
        - cos 模式：重新从 COS 下载所有数据文件到本地缓存，并刷新文件路径
        - local 模式：直接清空 lru_cache，重新读取本地文件
        供热更新接口调用（上传新数据文件后调用此方法即可生效，无需重启容器）。
        """
        if data_config.DATA_MODE == 'cos':
            # 重新下载文件并更新路径
            paths = _download_from_cos()
            self.estate_static_path       = paths['estate_static']
            self.rent_ratio_path          = paths['rent_ratio']
            self.housing_types_path       = paths['housing_types']
            self.price_trend_path         = paths['price_trend']
            self.dynamic_estate_data_path = paths['dynamic_estate_data']

        # 清空所有 lru_cache，触发下次访问时重新加载
        self.load_estate_static_info.cache_clear()
        self.load_rent_ratio_data.cache_clear()
        self.load_housing_types.cache_clear()
        self.load_price_trend_by_numeric_id.cache_clear()
        self.load_dynamic_estate_data.cache_clear()

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
