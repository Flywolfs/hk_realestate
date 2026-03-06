"""
微信登录认证模块
处理小程序用户登录、Token生成与验证
"""
import requests
import jwt
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
import secrets

# 微信小程序配置 (需要在config或环境变量中设置)
WECHAT_APPID = ''  # 替换为你的小程序AppID
WECHAT_SECRET = ''  # 替换为你的小程序AppSecret
jwt_secret = secrets.token_urlsafe(32)
JWT_SECRET = jwt_secret  # 用于签名JWT的密钥，生产环境请使用强密钥
JWT_EXPIRE_DAYS = 30  # Token有效期30天

# 内存存储用户访问记录 (生产环境建议使用数据库)
user_access_log = []


def get_wechat_session(code):
    """
    通过微信code获取用户session信息
    
    Args:
        code: 小程序登录时获取的临时code
        
    Returns:
        dict: 包含openid和session_key的字典，或None
    """
    url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': WECHAT_APPID,
        'secret': WECHAT_SECRET,
        'js_code': code,
        'grant_type': 'authorization_code'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'openid' in data:
            return {
                'openid': data['openid'],
                'session_key': data.get('session_key', ''),
                'unionid': data.get('unionid', '')
            }
        else:
            print(f"微信登录失败: {data}")
            return None
    except Exception as e:
        print(f"请求微信服务器失败: {str(e)}")
        return None


def generate_token(openid, user_info=None):
    """
    生成JWT Token
    
    Args:
        openid: 用户微信openid
        user_info: 可选的用户信息（昵称、头像等）
        
    Returns:
        str: JWT Token
    """
    payload = {
        'openid': openid,
        'exp': datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
        'iat': datetime.utcnow(),
        'type': 'wechat_miniprogram'
    }
    
    if user_info:
        payload['nickname'] = user_info.get('nickName', '')
        payload['avatar'] = user_info.get('avatarUrl', '')
    
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token


def verify_token(token):
    """
    验证JWT Token
    
    Args:
        token: JWT Token字符串
        
    Returns:
        dict: 解码后的payload，或None
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token已过期
    except jwt.InvalidTokenError:
        return None  # Token无效


def login_required(f):
    """
    登录验证装饰器
    用于保护需要登录才能访问的API
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从请求头获取Token
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': '请先登录',
                'code': 401
            }), 401
        
        token = auth_header[7:]  # 去掉 "Bearer " 前缀
        payload = verify_token(token)
        
        if not payload:
            return jsonify({
                'success': False,
                'error': '登录已过期，请重新登录',
                'code': 401
            }), 401
        
        # 将用户信息存入请求上下文
        request.current_user = payload
        
        # 记录用户访问
        log_user_access(payload.get('openid'), request.path)
        
        return f(*args, **kwargs)
    
    return decorated_function


def log_user_access(openid, path):
    """
    记录用户访问日志
    
    Args:
        openid: 用户openid
        path: 访问的API路径
    """
    access_record = {
        'openid': openid,
        'path': path,
        'timestamp': datetime.now().isoformat(),
        'ip': request.headers.get('X-Forwarded-For', request.remote_addr)
    }
    user_access_log.append(access_record)
    
    # 限制日志大小，保留最近1000条 (生产环境应使用数据库)
    if len(user_access_log) > 1000:
        user_access_log.pop(0)


def get_user_stats():
    """
    获取用户访问统计
    
    Returns:
        dict: 用户统计信息
    """
    unique_users = set()
    today_users = set()
    today = datetime.now().date()
    
    for record in user_access_log:
        unique_users.add(record['openid'])
        record_date = datetime.fromisoformat(record['timestamp']).date()
        if record_date == today:
            today_users.add(record['openid'])
    
    return {
        'total_visits': len(user_access_log),
        'unique_users': len(unique_users),
        'today_users': len(today_users),
        'recent_logs': user_access_log[-50:]  # 最近50条记录
    }
