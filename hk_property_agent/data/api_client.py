"""
后台 API 客户端（扩展预留）
封装对 28hse 数据服务 API 的调用，带 TTL 缓存和超时降级。
当前 P0 工具不依赖此客户端（使用预聚合数据），保留为未来扩展点。
"""

import os
import time
import logging
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)

BACKEND_BASE_URL = os.environ.get(
    'BACKEND_API_URL',
    'http://localhost:5000'
)
REQUEST_TIMEOUT = 10  # seconds


class _TTLCache:
    """简单的 TTL 缓存实现。"""

    def __init__(self, maxsize: int = 256, ttl: int = 600):
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            if time.time() - self._timestamps[key] < self._ttl:
                return self._cache[key]
            del self._cache[key]
            del self._timestamps[key]
        return None

    def set(self, key: str, value: Any):
        # Evict oldest if full
        if len(self._cache) >= self._maxsize:
            oldest_key = min(self._timestamps, key=self._timestamps.get)
            del self._cache[oldest_key]
            del self._timestamps[oldest_key]
        self._cache[key] = value
        self._timestamps[key] = time.time()


class BackendAPIClient:
    """
    28hse 数据服务 API 客户端。
    带 TTL 缓存 + 超时处理 + 降级逻辑。
    """

    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = (base_url or BACKEND_BASE_URL).rstrip('/')
        self.timeout = timeout or REQUEST_TIMEOUT
        self._cache = _TTLCache(maxsize=256, ttl=600)
        self._session = requests.Session()

    def get_estates(self, page: int = 1, limit: int = 20) -> Optional[Dict]:
        return self._get(f'/api/estates?page={page}&limit={limit}')

    def get_estate(self, estate_id: str) -> Optional[Dict]:
        return self._get(f'/api/estates/{estate_id}')

    def search_estates(self, query: str) -> Optional[Dict]:
        return self._get(f'/api/search?q={query}')

    def get_rent_ratios(self) -> Optional[Dict]:
        return self._get('/api/rent-ratios')

    def _get(self, path: str) -> Optional[Dict]:
        url = f'{self.base_url}{path}'

        # Check cache
        cached = self._cache.get(url)
        if cached is not None:
            return cached

        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            self._cache.set(url, data)
            return data
        except requests.Timeout:
            logger.warning(f"[APIClient] 超时: {url}")
            return None
        except requests.RequestException as e:
            logger.warning(f"[APIClient] 请求失败: {url} - {e}")
            return None


# 模块级单例
_client_instance: Optional[BackendAPIClient] = None


def get_api_client() -> BackendAPIClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = BackendAPIClient()
    return _client_instance
