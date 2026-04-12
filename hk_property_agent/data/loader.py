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
    'rent_ratio':          'data/average_rent_sale_ratio.json',
    'housing_types':       'data/housing_types.json',
    'price_trend':         'data/monthly_price_trend.json',
    'dynamic_estate_data': 'data/dynamic_estate_data.json',
}

# 本地文件路径映射
LOCAL_PATHS = {
    'estate_static':       os.path.join(_CENTANET_DIR, 'estate_info_20260221_convert.json'),
    'rent_ratio':          os.path.join(_CENTANET_DIR, 'average_rent_sale_ratio.json'),
    'housing_types':       os.path.join(_HSE28_DIR, 'housing_types.json'),
    'price_trend':         os.path.join(_CENTANET_DIR, 'monthly_price_trend.json'),
    'dynamic_estate_data': os.path.join(_CENTANET_DIR, 'dynamic_estate_data.json'),
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

        print(f"[DataLoader] 索引构建完成: {len(self._name_to_id)} 条名称索引, {len(self._area_index)} 个地区")

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
