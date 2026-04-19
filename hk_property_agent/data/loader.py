"""
Agent 专用数据加载器
直接从 COS 对象存储或本地文件读取香港房产数据，
完全独立于现有后端 API 体系，不影响用户访问统计。

支持两种模式（由环境变量 DATA_MODE 控制）：
  - local : 直接读取本地 JSON 文件（开发调试用）
  - cos   : 从腾讯云 COS 下载文件到本地缓存后读取（云端部署用）
"""

import json
import os
import threading
from typing import Dict, List, Optional

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

# ============================================================
# 配置读取
# ============================================================
DATA_MODE = os.environ.get('DATA_MODE', 'local')
COS_BUCKET = os.environ.get('COS_BUCKET', '')
COS_REGION = os.environ.get('COS_REGION', 'ap-guangzhou')
COS_SECRET_ID = os.environ.get('COS_SECRET_ID', '')
COS_SECRET_KEY = os.environ.get('COS_SECRET_KEY', '')
COS_LOCAL_CACHE_DIR = os.environ.get('COS_LOCAL_CACHE_DIR', '/tmp/agent_data')

_CENTANET_DIR = os.environ.get('CENTANET_DATA_DIR',
    '/home/zhangchi/Documents/28hse/centanet_system/crawler')
_HSE28_DIR = os.environ.get('HSE28_DATA_DIR',
    '/home/zhangchi/Documents/28hse/28hse_system')

# COS 文件键名映射
COS_KEYS = {
    'estate_static':       'data/estate_info_20260221_convert.json',
    'estate_raw':          'data/estate_info_20260221.json',
    'rent_ratio':          'data/average_rent_sale_ratio.json',
    'housing_types':       'data/housing_types.json',
    'price_trend':         'data/monthly_price_trend.json',
    'dynamic_estate_data': 'data/dynamic_estate_data.json',
    'sales_volume':        'data/monthly_sales_volume.json',
    'rental_summary':      'data/rental_summary.json',
}

# 本地文件路径映射
LOCAL_PATHS = {
    'estate_static':       os.path.join(_CENTANET_DIR, 'estate_info_20260221_convert.json'),
    'estate_raw':          os.path.join(_CENTANET_DIR, 'estate_info_20260221.json'),
    'rent_ratio':          os.path.join(_CENTANET_DIR, 'average_rent_sale_ratio.json'),
    'housing_types':       os.path.join(_HSE28_DIR, 'housing_types.json'),
    'price_trend':         os.path.join(_CENTANET_DIR, 'monthly_price_trend.json'),
    'dynamic_estate_data': os.path.join(_CENTANET_DIR, 'dynamic_estate_data.json'),
    'sales_volume':        os.path.join(_CENTANET_DIR, 'monthly_sales_volume.json'),
    'rental_summary':      os.path.join(_CENTANET_DIR, 'rental_summary.json'),
}


def _download_from_cos() -> Dict[str, str]:
    """从 COS 批量下载数据文件到本地缓存，返回本地路径字典。"""
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        raise ImportError("COS 模式需要安装 cos-python-sdk-v5: pip install cos-python-sdk-v5")

    os.makedirs(COS_LOCAL_CACHE_DIR, exist_ok=True)
    config = CosConfig(Region=COS_REGION, SecretId=COS_SECRET_ID, SecretKey=COS_SECRET_KEY)
    client = CosS3Client(config)

    local_paths = {}
    for key_name, cos_key in COS_KEYS.items():
        local_file = os.path.join(COS_LOCAL_CACHE_DIR, os.path.basename(cos_key))
        try:
            client.download_file(Bucket=COS_BUCKET, Key=cos_key, DestFilePath=local_file)
            print(f"[COS] 下载成功: {cos_key} -> {local_file}")
        except Exception as e:
            print(f"[COS] 下载失败 {cos_key}: {e}，尝试使用本地缓存")
        local_paths[key_name] = local_file

    return local_paths


def _resolve_paths() -> Dict[str, str]:
    """根据 DATA_MODE 返回各数据文件的实际本地路径。"""
    if DATA_MODE == 'cos':
        return _download_from_cos()
    return dict(LOCAL_PATHS)


class AgentDataLoader:
    """
    Agent 专用数据加载器，提供结构化查询接口供 LangChain Tools 调用。
    使用读写锁保证热更新时的线程安全。
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._data: Dict = {}
        self._paths: Dict[str, str] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------

    def _load_all(self):
        """加载所有数据文件到内存。"""
        print("[DataLoader] 开始加载数据...")
        paths = _resolve_paths()
        data = {}

        for key, path in paths.items():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                data[key] = raw
                print(f"[DataLoader] 已加载: {key} ({path})")
            except FileNotFoundError:
                print(f"[DataLoader] 警告: 文件未找到 {path}，跳过")
                data[key] = {} if key != 'housing_types' else {'gongwu': {'names': []}, 'juwu': {'names': []}}
            except json.JSONDecodeError as e:
                print(f"[DataLoader] 警告: JSON 解析失败 {path}: {e}")
                data[key] = {}

        with self._lock:
            self._paths = paths
            self._data = data
            self._build_indexes()

        print("[DataLoader] 数据加载完成")

    def _build_indexes(self):
        """构建内存索引，加速查询。（在持锁状态下调用）"""
        estate_static = self._data.get('estate_static', {})

        # ----------------------------------------------------------
        # 从原始 estate_info 提取 scope 地区数据，补充到 estate_static
        # 原始文件结构: {"count": N, "data": [{typeCode, scope, ...}, ...]}
        # ----------------------------------------------------------
        estate_raw = self._data.get('estate_raw', {})
        raw_list = estate_raw.get('data', []) if isinstance(estate_raw, dict) else []
        scope_map = {}  # typeCode -> {area, sub_area, territory}
        for item in raw_list:
            type_code = item.get('typeCode', '')
            scope = item.get('scope', {})
            if type_code and scope:
                db = scope.get('db', '')  # e.g. "將軍澳 (西貢區)"
                web_scope = scope.get('webScope', '')  # e.g. "將軍澳"
                territory = scope.get('terr', '')  # e.g. "九龍"
                # 从 db 字段提取区名，格式: "將軍澳 (西貢區)" -> "西貢區"
                district = ''
                if '(' in db:
                    district = db.split('(')[-1].rstrip(')')
                elif '（' in db:
                    district = db.split('（')[-1].rstrip('）')
                else:
                    district = db
                scope_map[type_code] = {
                    'area': district,       # 区级: "西貢區"
                    'sub_area': web_scope,  # 子区域: "將軍澳"
                    'territory': territory, # 大区: "九龍"
                }

        # 将 scope 数据合并到 estate_static
        enriched_count = 0
        for estate_id, info in estate_static.items():
            if not info.get('area') and not info.get('district'):
                scope_info = scope_map.get(estate_id, {})
                if scope_info:
                    info['area'] = scope_info['area']
                    info['sub_area'] = scope_info['sub_area']
                    info['territory'] = scope_info['territory']
                    enriched_count += 1

        if enriched_count:
            print(f"[DataLoader] 从原始文件补充了 {enriched_count} 条地区数据")

        # 名称 -> 屋苑ID 的反向索引（支持中英文名称）
        self._name_to_id: Dict[str, str] = {}
        for estate_id, info in estate_static.items():
            name = info.get('name', '')
            if name:
                self._name_to_id[name.lower()] = estate_id
                self._name_to_id[name] = estate_id

            # 英文名称
            eng_name = info.get('name_en', '') or info.get('nameEn', '')
            if eng_name:
                self._name_to_id[eng_name.lower()] = estate_id

        # 地区 -> 屋苑ID列表 的索引
        self._area_index: Dict[str, List[str]] = {}
        for estate_id, info in estate_static.items():
            area = info.get('area', '') or info.get('district', '')
            if area:
                self._area_index.setdefault(area, []).append(estate_id)
            # 同时按子区域建立索引（如 "將軍澳"）
            sub_area = info.get('sub_area', '')
            if sub_area and sub_area != area:
                self._area_index.setdefault(sub_area, []).append(estate_id)

        # 公屋/居屋名称集合（用于默认过滤）
        housing_types = self._data.get('housing_types', {})
        gongwu_names = set(housing_types.get('gongwu', {}).get('names', []))
        juwu_names = set(housing_types.get('juwu', {}).get('names', []))
        self._gongwu_names = gongwu_names
        self._juwu_names = juwu_names

        print(f"[DataLoader] 索引构建完成: {len(self._name_to_id)} 条名称索引, {len(self._area_index)} 个地区, 公屋 {len(gongwu_names)} 个, 居屋 {len(juwu_names)} 个")

    def reload(self):
        """热更新：重新从 COS 下载并刷新内存数据（线程安全）。"""
        print("[DataLoader] 开始热更新...")
        self._load_all()
        print("[DataLoader] 热更新完成")

    # ------------------------------------------------------------------
    # 内部数据访问
    # ------------------------------------------------------------------

    @property
    def estate_static(self) -> Dict:
        with self._lock:
            return self._data.get('estate_static', {})

    @property
    def rent_ratio_data(self) -> Dict:
        with self._lock:
            raw = self._data.get('rent_ratio', {})
            return raw.get('data', {}) if isinstance(raw, dict) and 'data' in raw else raw

    @property
    def housing_types(self) -> Dict:
        with self._lock:
            return self._data.get('housing_types', {})

    @property
    def price_trend(self) -> Dict:
        with self._lock:
            return self._data.get('price_trend', {})

    @property
    def dynamic_estate_data(self) -> Dict:
        with self._lock:
            return self._data.get('dynamic_estate_data', {})

    @property
    def sales_volume_data(self) -> Dict:
        with self._lock:
            raw = self._data.get('sales_volume', {})
            return raw.get('data', {}) if isinstance(raw, dict) and 'data' in raw else raw

    @property
    def rental_summary_data(self) -> Dict:
        with self._lock:
            raw = self._data.get('rental_summary', {})
            return raw.get('data', {}) if isinstance(raw, dict) and 'data' in raw else raw

    @property
    def gongwu_names(self) -> set:
        """公屋名称集合"""
        with self._lock:
            return self._gongwu_names

    @property
    def juwu_names(self) -> set:
        """居屋名称集合"""
        with self._lock:
            return self._juwu_names

    # ------------------------------------------------------------------
    # 结构化查询接口
    # ------------------------------------------------------------------

    def find_estate_by_name(self, name: str) -> Optional[Dict]:
        """
        按名称查找屋苑（精确匹配，忽略大小写）。
        返回包含完整信息的字典，若未找到返回 None。
        """
        with self._lock:
            estate_id = self._name_to_id.get(name) or self._name_to_id.get(name.lower())
        if not estate_id:
            return None
        return self.get_estate_full_info(estate_id)

    def fuzzy_search_by_name(self, query: str, limit: int = 10) -> List[Dict]:
        """
        模糊搜索屋苑名称（包含匹配）。
        返回最多 limit 个结果列表。
        """
        results = []
        query_lower = query.lower()
        seen = set()

        with self._lock:
            estate_static = self._data.get('estate_static', {})

        for estate_id, info in estate_static.items():
            if estate_id in seen:
                continue
            name = info.get('name', '')
            name_en = info.get('name_en', '') or info.get('nameEn', '')
            if query_lower in name.lower() or query_lower in name_en.lower():
                seen.add(estate_id)
                results.append(self._build_summary(estate_id, info))
                if len(results) >= limit:
                    break

        return results

    def list_estates_by_area(self, area: str, limit: int = 20) -> List[Dict]:
        """
        按地区（如"荃湾"、"沙田"）列出屋苑，返回最多 limit 条摘要信息。
        """
        with self._lock:
            ids = self._area_index.get(area, [])[:limit]
            estate_static = self._data.get('estate_static', {})

        return [self._build_summary(eid, estate_static.get(eid, {})) for eid in ids]

    def get_estate_full_info(self, estate_id: str) -> Optional[Dict]:
        """
        获取指定屋苑的完整信息（静态+租售比+价格趋势）。
        """
        static = self.estate_static.get(estate_id)
        if not static:
            return None

        rent_data = self.rent_ratio_data.get(estate_id, {})
        dynamic = self.dynamic_estate_data.get(estate_id, {})

        # 解析租售比时序
        overall_timeseries = {}
        room_type_ratio = {}
        latest_ratio = None
        if isinstance(rent_data, dict):
            overall_timeseries = rent_data.get('overall_ratio', {})
            room_type_ratio = rent_data.get('room_type_ratio', {})
            if isinstance(overall_timeseries, dict) and overall_timeseries:
                latest_ratio = list(overall_timeseries.values())[-1]

        # 价格趋势
        price_trend = self.price_trend.get(estate_id, {})
        monthly_trend = price_trend.get('monthly_price_trend', {}) if isinstance(price_trend, dict) else {}

        return {
            'id': estate_id,
            'name': static.get('name', ''),
            'name_en': static.get('name_en', '') or static.get('nameEn', ''),
            'address': static.get('address', ''),
            'area': static.get('area', '') or static.get('district', ''),
            'coordinates': static.get('coordinates'),
            'basic_info': static.get('basic_info', {}),
            'establish_year': static.get('establish_year') or static.get('basic_info', {}).get('establish_year'),
            'primary_school': static.get('primary_school') or static.get('basic_info', {}).get('primary_school'),
            'type_code': static.get('typeCode', estate_id),
            # 租售比
            'rent_ratio_latest': latest_ratio,
            'rent_ratio_timeseries': overall_timeseries,
            'room_type_ratio': room_type_ratio,
            # 价格
            'current_price_per_sqft': dynamic.get('current_price_per_sqft'),
            'min_area': dynamic.get('min_area'),
            'max_area': dynamic.get('max_area'),
            'monthly_price_trend': monthly_trend,
        }

    def get_rent_ratio_info(self, estate_id: str) -> Optional[Dict]:
        """
        获取指定屋苑的租售比详情（时序+户型分类）。
        """
        rent_data = self.rent_ratio_data.get(estate_id)
        if not rent_data:
            return None

        if isinstance(rent_data, dict):
            overall = rent_data.get('overall_ratio', {})
            room_type = rent_data.get('room_type_ratio', {})
            latest = list(overall.values())[-1] if isinstance(overall, dict) and overall else None
        else:
            overall = {}
            room_type = {}
            latest = rent_data if isinstance(rent_data, (int, float)) else None

        return {
            'estate_id': estate_id,
            'latest_ratio': latest,
            'timeseries': overall,
            'room_type_ratio': room_type,
        }

    def get_price_trend_info(self, estate_id: str, months: int = 12) -> Optional[Dict]:
        """
        获取指定屋苑近 months 个月的尺价趋势。
        """
        price_trend = self.price_trend.get(estate_id, {})
        monthly = price_trend.get('monthly_price_trend', {}) if isinstance(price_trend, dict) else {}

        if not monthly:
            # 尝试从 dynamic_estate_data 获取当前尺价
            dynamic = self.dynamic_estate_data.get(estate_id, {})
            current = dynamic.get('current_price_per_sqft')
            return {'estate_id': estate_id, 'monthly_trend': {}, 'current_price_per_sqft': current}

        # 取最近 months 个月
        sorted_months = sorted(monthly.keys())[-months:]
        recent_trend = {m: monthly[m] for m in sorted_months}

        return {
            'estate_id': estate_id,
            'monthly_trend': recent_trend,
            'current_price_per_sqft': self.dynamic_estate_data.get(estate_id, {}).get('current_price_per_sqft'),
        }

    def get_sales_volume(self, estate_id: str = None, area: str = None, months: int = 12) -> Optional[Dict]:
        """
        获取成交量数据。
        :param estate_id: 指定屋苑ID（可选）
        :param area: 指定地区（可选），会聚合该地区所有屋苑
        :param months: 最近几个月，默认12
        """
        months = min(36, max(1, months))
        volume_data = self.sales_volume_data

        if estate_id:
            estate_vol = volume_data.get(estate_id, {})
            if not estate_vol:
                return None
            sorted_months = sorted(estate_vol.keys())[-months:]
            return {
                'estate_id': estate_id,
                'monthly_volume': {m: estate_vol[m] for m in sorted_months},
            }

        if area:
            # 聚合该地区所有屋苑的成交量
            with self._lock:
                ids = self._area_index.get(area, [])
            if not ids:
                return None
            aggregated = {}
            for eid in ids:
                estate_vol = volume_data.get(eid, {})
                for month, data in estate_vol.items():
                    if month not in aggregated:
                        aggregated[month] = {'count': 0, 'total_price_sum': 0, 'total_price_count': 0}
                    if isinstance(data, dict):
                        aggregated[month]['count'] += data.get('count', 0)
                        avg_p = data.get('avg_price', 0)
                        cnt = data.get('count', 0)
                        if avg_p and cnt:
                            aggregated[month]['total_price_sum'] += avg_p * cnt
                            aggregated[month]['total_price_count'] += cnt
            # 计算区域月均价
            result = {}
            for month, agg in aggregated.items():
                result[month] = {
                    'count': agg['count'],
                    'avg_price': round(agg['total_price_sum'] / agg['total_price_count']) if agg['total_price_count'] else None,
                }
            sorted_months = sorted(result.keys())[-months:]
            return {
                'area': area,
                'monthly_volume': {m: result[m] for m in sorted_months},
            }

        return None

    def get_rental_info(self, estate_id: str) -> Optional[Dict]:
        """获取指定屋苑的租金摘要数据。"""
        rental_data = self.rental_summary_data.get(estate_id)
        if not rental_data:
            return None
        return {
            'estate_id': estate_id,
            'recent_rentals': rental_data.get('recent_rentals', []),
            'avg_rent': rental_data.get('avg_rent'),
            'rent_per_sqft': rental_data.get('rent_per_sqft'),
        }

    def filter_estates(self, area: str = None, min_price: float = None,
                       max_price: float = None, min_rent_ratio: float = None,
                       max_rent_ratio: float = None, min_area_size: float = None,
                       max_area_size: float = None, sort_by: str = 'rent_ratio',
                       sort_order: str = 'desc', limit: int = 10,
                       include_public_housing: bool = False,
                       include_hos: bool = False,
                       min_rent: float = None, max_rent: float = None,
                       min_building_age: float = None, max_building_age: float = None) -> List[Dict]:
        """
        按数值条件筛选屋苑。
        价格为尺价（港元/平方呎），租售比为百分比，面积为实用面积（平方呎）。
        租金为平均月租（港元），楼龄为年数。
        默认排除公屋和居屋，可通过 include_public_housing/include_hos 参数包含。
        """
        limit = min(30, max(1, limit))
        estate_static = self.estate_static
        rent_ratio_data = self.rent_ratio_data
        dynamic_data = self.dynamic_estate_data
        rental_data = self.rental_summary_data

        # 确定候选屋苑范围
        if area:
            with self._lock:
                candidate_ids = self._area_index.get(area, [])
            if not candidate_ids:
                return []
        else:
            candidate_ids = list(estate_static.keys())

        # 公屋/居屋名称集合
        with self._lock:
            gongwu = self._gongwu_names
            juwu = self._juwu_names

        current_year = 2026

        results = []
        for eid in candidate_ids:
            info = estate_static.get(eid, {})
            dynamic = dynamic_data.get(eid, {})

            name = info.get('name', '')

            # 默认排除公屋/居屋
            if not include_public_housing and name in gongwu:
                continue
            if not include_hos and name in juwu:
                continue

            price = dynamic.get('current_price_per_sqft')
            min_a = dynamic.get('min_area')
            max_a = dynamic.get('max_area')

            # 获取租售比
            rent_data = rent_ratio_data.get(eid, {})
            ratio = None
            if isinstance(rent_data, dict):
                overall = rent_data.get('overall_ratio', {})
                if isinstance(overall, dict) and overall:
                    ratio = list(overall.values())[-1]
            elif isinstance(rent_data, (int, float)):
                ratio = rent_data

            # 获取租金
            rental_info = rental_data.get(eid, {})
            avg_rent = rental_info.get('avg_rent') if isinstance(rental_info, dict) else None
            rent_per_sqft = rental_info.get('rent_per_sqft') if isinstance(rental_info, dict) else None

            # 计算楼龄
            establish_year = info.get('establish_year') or info.get('basic_info', {}).get('establish_year')
            # 如果 establish_year 是字符串（如 "1987年"），提取数字部分
            if isinstance(establish_year, str):
                import re
                m = re.search(r'\d+', establish_year)
                establish_year = int(m.group()) if m else None
            building_age = None
            if isinstance(establish_year, (int, float)) and establish_year:
                building_age = current_year - int(establish_year)

            # 应用筛选条件
            if min_price is not None and (price is None or price < min_price):
                continue
            if max_price is not None and (price is None or price > max_price):
                continue
            if min_rent_ratio is not None and (ratio is None or ratio < min_rent_ratio):
                continue
            if max_rent_ratio is not None and (ratio is None or ratio > max_rent_ratio):
                continue
            if min_area_size is not None and (min_a is None or min_a < min_area_size):
                continue
            if max_area_size is not None and (max_a is None or max_a > max_area_size):
                continue
            if min_rent is not None and (avg_rent is None or avg_rent < min_rent):
                continue
            if max_rent is not None and (avg_rent is None or avg_rent > max_rent):
                continue
            if min_building_age is not None and (building_age is None or building_age < min_building_age):
                continue
            if max_building_age is not None and (building_age is None or building_age > max_building_age):
                continue

            results.append({
                'id': eid,
                'name': name,
                'area': info.get('area', '') or info.get('district', ''),
                'sub_area': info.get('sub_area', ''),
                'current_price_per_sqft': price,
                'rent_ratio_latest': ratio,
                'min_area': min_a,
                'max_area': max_a,
                'avg_rent': avg_rent,
                'rent_per_sqft': rent_per_sqft,
                'building_age': building_age,
                'establish_year': establish_year if isinstance(establish_year, (int, float)) else None,
            })

        # 排序
        sort_key_map = {
            'rent_ratio': 'rent_ratio_latest',
            'price': 'current_price_per_sqft',
            'area_size': 'max_area',
            'rent': 'avg_rent',
            'building_age': 'building_age',
        }
        key_field = sort_key_map.get(sort_by, 'rent_ratio_latest')
        reverse = sort_order != 'asc'
        results.sort(key=lambda x: x.get(key_field) or 0, reverse=reverse)

        return results[:limit]

    def get_area_statistics(self, area: str = None) -> Optional[Dict]:
        """
        获取地区统计数据。
        :param area: 指定地区名，不传则返回所有地区概览。
        """
        import statistics

        if area:
            with self._lock:
                ids = self._area_index.get(area, [])
            if not ids:
                return None

            estate_static = self.estate_static
            dynamic_data = self.dynamic_estate_data
            rent_ratio_data = self.rent_ratio_data

            prices = []
            ratios = []
            estates_info = []
            for eid in ids:
                info = estate_static.get(eid, {})
                dynamic = dynamic_data.get(eid, {})
                price = dynamic.get('current_price_per_sqft')
                if price:
                    prices.append(price)

                rent_data = rent_ratio_data.get(eid, {})
                ratio = None
                if isinstance(rent_data, dict):
                    overall = rent_data.get('overall_ratio', {})
                    if isinstance(overall, dict) and overall:
                        ratio = list(overall.values())[-1]
                elif isinstance(rent_data, (int, float)):
                    ratio = rent_data
                if ratio:
                    ratios.append(ratio)

                estates_info.append({
                    'id': eid,
                    'name': info.get('name', ''),
                    'price': price,
                    'ratio': ratio,
                })

            # Top 5 按租售比排序
            top5 = sorted(
                [e for e in estates_info if e.get('ratio')],
                key=lambda x: x['ratio'], reverse=True
            )[:5]

            # 近3月价格变化
            price_change = self._calc_area_price_change(ids, months=3)

            return {
                'area': area,
                'total_estates': len(ids),
                'median_price': round(statistics.median(prices)) if prices else None,
                'median_rent_ratio': round(statistics.median(ratios), 2) if ratios else None,
                'price_change_3m': price_change,
                'top5_by_rent_ratio': [
                    {'name': e['name'], 'ratio': e['ratio'], 'price': e['price']}
                    for e in top5
                ],
            }

        # 全港概览：每个地区一行摘要
        with self._lock:
            all_areas = dict(self._area_index)

        estate_static = self.estate_static
        dynamic_data = self.dynamic_estate_data

        overview = []
        for area_name, ids in sorted(all_areas.items()):
            prices = []
            for eid in ids:
                dynamic = dynamic_data.get(eid, {})
                p = dynamic.get('current_price_per_sqft')
                if p:
                    prices.append(p)
            overview.append({
                'area': area_name,
                'estate_count': len(ids),
                'median_price': round(statistics.median(prices)) if prices else None,
            })

        return {'overview': overview}

    def _calc_area_price_change(self, estate_ids: List[str], months: int = 3) -> Optional[Dict]:
        """计算地区近 N 月尺价变化百分比。"""
        price_trend = self.price_trend
        all_months_set = set()
        monthly_prices = {}

        for eid in estate_ids:
            trend = price_trend.get(eid, {})
            monthly = trend.get('monthly_price_trend', {}) if isinstance(trend, dict) else {}
            for m, v in monthly.items():
                val = v if isinstance(v, (int, float)) else None
                if val:
                    all_months_set.add(m)
                    monthly_prices.setdefault(m, []).append(val)

        if not monthly_prices:
            return None

        sorted_months = sorted(all_months_set)
        if len(sorted_months) < 2:
            return None

        recent = sorted_months[-1]
        compare = sorted_months[-min(months + 1, len(sorted_months))]

        avg_recent = sum(monthly_prices.get(recent, [])) / len(monthly_prices.get(recent, [1]))
        avg_compare = sum(monthly_prices.get(compare, [])) / len(monthly_prices.get(compare, [1]))

        if avg_compare == 0:
            return None

        pct = (avg_recent - avg_compare) / avg_compare * 100
        return {
            'from_month': compare,
            'to_month': recent,
            'change_pct': round(pct, 1),
        }

    def list_all_areas(self) -> List[str]:
        """返回所有可用地区名称列表。"""
        with self._lock:
            return sorted(self._area_index.keys())

    def get_stats(self) -> Dict:
        """返回数据概况（屋苑总数、覆盖地区数等）。"""
        static = self.estate_static
        return {
            'total_estates': len(static),
            'total_areas': len(self._area_index),
            'areas': list(self._area_index.keys()),
            'data_mode': DATA_MODE,
        }

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _build_summary(self, estate_id: str, info: Dict) -> Dict:
        """构建屋苑摘要（供列表展示使用）。"""
        rent_data = self.rent_ratio_data.get(estate_id, {})
        latest_ratio = None
        if isinstance(rent_data, dict):
            overall = rent_data.get('overall_ratio', {})
            if isinstance(overall, dict) and overall:
                latest_ratio = list(overall.values())[-1]
        elif isinstance(rent_data, (int, float)):
            latest_ratio = rent_data

        dynamic = self.dynamic_estate_data.get(estate_id, {})

        return {
            'id': estate_id,
            'name': info.get('name', ''),
            'name_en': info.get('name_en', '') or info.get('nameEn', ''),
            'address': info.get('address', ''),
            'area': info.get('area', '') or info.get('district', ''),
            'rent_ratio_latest': latest_ratio,
            'current_price_per_sqft': dynamic.get('current_price_per_sqft'),
            'min_area': dynamic.get('min_area'),
            'max_area': dynamic.get('max_area'),
        }


# 模块级单例，服务启动时初始化一次
_loader_instance: Optional[AgentDataLoader] = None
_loader_lock = threading.Lock()


def get_loader() -> AgentDataLoader:
    """获取全局单例 AgentDataLoader（懒加载 + 线程安全）。"""
    global _loader_instance
    if _loader_instance is None:
        with _loader_lock:
            if _loader_instance is None:
                _loader_instance = AgentDataLoader()
    return _loader_instance
