"""
微信小程序鉴权模块（Agent 服务专用）
复用微信云托管的 X-WX-FROM-OPENID header 鉴权方式，
同时兼容 JWT Token 方式（供本地测试使用）。
本模块独立于现有 28hse_system/backend/auth.py，不共享 jwt_secret。
"""

import os
import jwt
import secrets
import requests
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

WECHAT_APPID = os.environ.get('WECHAT_APPID', '')
WECHAT_SECRET = os.environ.get('WECHAT_SECRET', '')

# JWT 密钥（每次启动重新生成，或从环境变量读取固定值）
JWT_SECRET = os.environ.get('AGENT_JWT_SECRET', secrets.token_urlsafe(32))
JWT_EXPIRE_DAYS = 30


def get_wechat_session(code: str) -> dict | None:
    """通过微信临时 code 换取 openid。"""
    url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': WECHAT_APPID,
        'secret': WECHAT_SECRET,
        'js_code': code,
        'grant_type': 'authorization_code',
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if 'openid' in data:
            return {
                'openid': data['openid'],
                'session_key': data.get('session_key', ''),
                'unionid': data.get('unionid', ''),
            }
        print(f"[Auth] 微信登录失败: {data}")
        return None
    except Exception as e:
        print(f"[Auth] 请求微信服务器失败: {e}")
        return None


def generate_token(openid: str) -> str:
    """生成 JWT Token（本地测试用）。"""
    payload = {
        'openid': openid,
        'exp': datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
        'iat': datetime.utcnow(),
        'type': 'agent_miniprogram',
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def verify_token(token: str) -> dict | None:
    """验证 JWT Token，返回 payload 或 None。"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def extract_user_from_headers(headers: dict) -> dict | None:
    """
    框架无关的用户提取函数。
    :param headers: HTTP 请求头字典（key 大小写不敏感需调用方处理）
    :return: 用户信息字典或 None
    """
    # 云托管云调用模式
    openid = headers.get('X-WX-FROM-OPENID') or headers.get('x-wx-from-openid')
    if openid:
        return {
            'openid': openid,
            'unionid': headers.get('X-WX-FROM-UNIONID', '') or headers.get('x-wx-from-unionid', ''),
            'appid': headers.get('X-WX-FROM-APPID', '') or headers.get('x-wx-from-appid', ''),
            'source': 'cloud_call',
        }

    # JWT Token 模式
    auth_header = headers.get('Authorization', '') or headers.get('authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        payload = verify_token(token)
        if payload:
            return {
                'openid': payload.get('openid', ''),
                'source': 'jwt_token',
            }

    return None


def get_user_from_request() -> dict | None:
    """
    从 Flask request 中提取用户身份（Flask 专用封装）。
    """
    return extract_user_from_headers(dict(request.headers))


def login_required(f):
    """登录验证装饰器，未通过鉴权返回 401。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_user_from_request()
        if not user:
            return jsonify({'success': False, 'error': '请先登录', 'code': 401}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated
