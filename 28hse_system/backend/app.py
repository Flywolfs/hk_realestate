"""
Flask API服务
提供租售比地图可视化所需的RESTful API
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import sys
import logging
from datetime import datetime
from collections import defaultdict
from functools import wraps

# 添加父目录到路径,以便导入data_loader
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_loader import DataLoader
from auth import (
    get_wechat_session, generate_token, verify_token, 
    login_required, get_user_stats, log_user_access,
    get_user_from_request
)

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='')

# CORS配置 - 支持Web和微信小程序
CORS(app, 
     origins=['*'],  # 开发环境允许所有来源,生产环境应改为具体域名
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('access.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 设置Flask自带的日志级别为WARNING，减少噪音
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# 简单的IP请求频率限制(生产环境建议使用Redis)
ip_request_tracker = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 30
BLOCK_DURATION_MINUTES = 10
blocked_ips = {}

# 初始化数据加载器
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_loader = DataLoader(BASE_PATH)


def rate_limit(f):
    """IP请求频率限制装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if not client_ip:
            client_ip = request.remote_addr
        
        # 检查是否在黑名单中
        if client_ip in blocked_ips:
            block_time = blocked_ips[client_ip]
            if (datetime.now() - block_time).total_seconds() < BLOCK_DURATION_MINUTES * 60:
                logger.warning(f"Blocked IP attempt: {client_ip}")
                return jsonify({
                    'success': False,
                    'error': 'Too many requests. Please try again later.'
                }), 429
            else:
                # 解除封禁
                del blocked_ips[client_ip]
                ip_request_tracker[client_ip] = []
        
        # 清理过期的请求记录
        now = datetime.now()
        ip_request_tracker[client_ip] = [
            req_time for req_time in ip_request_tracker[client_ip]
            if (now - req_time).total_seconds() < 60
        ]
        
        # 检查请求频率
        if len(ip_request_tracker[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
            blocked_ips[client_ip] = now
            logger.warning(f"IP blocked due to rate limit: {client_ip}")
            return jsonify({
                'success': False,
                'error': 'Rate limit exceeded. IP temporarily blocked.'
            }), 429
        
        # 记录本次请求
        ip_request_tracker[client_ip].append(now)
        
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def log_request_info():
    """记录所有请求信息用于安全审计"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    # 检测可疑请求
    suspicious_patterns = [
        b'\x16\x03\x01',  # TLS handshake
        b'SSH-',           # SSH protocol
        'script',          # XSS attempts
        '../',             # Path traversal
        'SELECT',          # SQL injection
        'UNION',
    ]
    
    is_suspicious = False
    for pattern in suspicious_patterns:
        if isinstance(pattern, bytes):
            if pattern in request.data:
                is_suspicious = True
                break
        elif pattern.lower() in str(request.url).lower() or pattern.lower() in str(request.data).lower():
            is_suspicious = True
            break
    
    if is_suspicious:
        logger.warning(
            f"SUSPICIOUS REQUEST - IP: {client_ip}, "
            f"Method: {request.method}, Path: {request.path}, "
            f"User-Agent: {user_agent}"
        )
    else:
        logger.info(
            f"IP: {client_ip}, Method: {request.method}, "
            f"Path: {request.path}, User-Agent: {user_agent}"
        )

@app.route('/api/estates', methods=['GET'])
@rate_limit
def get_all_estates():
    """
    获取所有有坐标的小区列表
    返回基本信息用于地图标记
    查询参数:
      - page: 页码（从1开始，不传则返回全部）
      - limit: 每页条数（默认200，最大500）
    """
    try:
        estates = data_loader.get_integrated_estates()
        total = len(estates)

        # 分页参数
        page_str = request.args.get('page')
        limit_str = request.args.get('limit', '200')

        if page_str is not None:
            try:
                page = max(1, int(page_str))
                limit = min(2000, max(1, int(limit_str)))
            except ValueError:
                return jsonify({'success': False, 'error': 'page/limit 参数必须为整数'}), 400

            start = (page - 1) * limit
            end = start + limit
            page_data = estates[start:end]
            total_pages = (total + limit - 1) // limit

            return jsonify({
                'success': True,
                'count': total,
                'page': page,
                'limit': limit,
                'total_pages': total_pages,
                'data': page_data
            })
        else:
            # 未传 page 时返回全部（兼容旧调用方式）
            return jsonify({
                'success': True,
                'count': total,
                'data': estates
            })
    except Exception as e:
        logger.error(f"Error in get_all_estates: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/estates/<estate_id>', methods=['GET'])
@rate_limit
def get_estate_detail(estate_id):
    """
    获取特定小区的详细信息
    """
    try:
        detail = data_loader.get_estate_detail(estate_id)
        if detail:
            return jsonify({
                'success': True,
                'data': detail
            })
        else:
            return jsonify({
                'success': False,
                'error': f'未找到ID为 {estate_id} 的小区'
            }), 404
    except Exception as e:
        logger.error(f"Error in get_estate_detail for {estate_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/rent-ratios', methods=['GET'])
@rate_limit
def get_rent_ratios():
    """
    获取租售比统计信息
    包含最小值、最大值、平均值,用于前端色彩映射
    """
    try:
        stats = data_loader.get_rent_ratio_statistics()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Error in get_rent_ratios: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/search', methods=['GET'])
@rate_limit
def search_estates():
    """
    按小区名称模糊搜索
    查询参数: keyword
    """
    try:
        keyword = request.args.get('keyword', '')
        if not keyword:
            return jsonify({
                'success': False,
                'error': '请提供搜索关键词'
            }), 400
        
        results = data_loader.search_estates_by_name(keyword)
        return jsonify({
            'success': True,
            'count': len(results),
            'data': results
        })
    except Exception as e:
        logger.error(f"Error in search_estates with keyword '{keyword}': {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/primary-schools', methods=['GET'])
@rate_limit
def get_primary_schools():
    """
    获取所有小学校网列表
    返回按小区数量排序的校网
    """
    try:
        estates = data_loader.get_integrated_estates()
        
        # 统计每个校网的小区数量
        school_count = {}
        for estate in estates:
            school = estate.get('primary_school')
            if school is not None and school != '':
                school_count[school] = school_count.get(school, 0) + 1
        
        # 按数量排序
        sorted_schools = sorted(school_count.items(), key=lambda x: x[1], reverse=True)
        
        # 返回所有校网
        result = [
            {'school': school, 'count': count}
            for school, count in sorted_schools
        ]
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        logger.error(f"Error in get_primary_schools: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/auth/login', methods=['POST'])
@rate_limit
def wechat_login():
    """
    微信小程序登录接口
    接收code，返回JWT Token
    
    请求体: {"code": "xxx", "userInfo": {...}}
    """
    try:
        data = request.get_json()
        code = data.get('code')
        user_info = data.get('userInfo', {})
        
        if not code:
            return jsonify({
                'success': False,
                'error': '缺少code参数'
            }), 400
        
        # 获取微信session
        session_data = get_wechat_session(code)
        if not session_data:
            return jsonify({
                'success': False,
                'error': '微信登录失败，请重试'
            }), 401
        
        openid = session_data['openid']
        
        # 生成JWT Token
        token = generate_token(openid, user_info)
        
        # 记录登录
        log_user_access(openid, '/api/auth/login')
        
        return jsonify({
            'success': True,
            'data': {
                'token': token,
                'openid': openid,  # 注意：生产环境建议不要返回openid
                'expires_in': 30 * 24 * 3600  # 30天，单位秒
            }
        })
        
    except Exception as e:
        logger.error(f"Error in wechat_login: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': '登录失败，请重试'
        }), 500


@app.route('/api/auth/verify', methods=['GET'])
@rate_limit
def verify_user_token():
    """
    验证用户身份是否有效
    支持两种方式：
    1. 云调用模式：从 header 自动获取用户信息
    2. JWT 模式：验证 Token 有效性
    """
    # 优先检查云调用模式
    user = get_user_from_request()
    
    if user:
        return jsonify({
            'success': True,
            'valid': True,
            'data': {
                'openid': user.get('openid'),
                'nickname': user.get('nickname', ''),
                'avatar': user.get('avatar', ''),
                'source': user.get('source', 'unknown')
            }
        })
    
    # 未获取到用户信息
    return jsonify({
        'success': False,
        'valid': False,
        'error': '未登录或登录已过期'
    }), 401


@app.route('/api/user/stats', methods=['GET'])
@rate_limit
def get_user_access_stats():
    """
    获取用户访问统计（仅管理员使用）
    生产环境应添加管理员权限验证
    """
    try:
        stats = get_user_stats()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Error in get_user_access_stats: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/refresh-data', methods=['POST'])
def refresh_data():
    """
    热重载数据（仅管理员使用）
    - cos 模式：重新从 COS 下载所有数据文件，再清空缓存
    - local 模式：直接清空缓存，重新读取本地文件
    需在请求头携带 X-Admin-Token，值与环境变量 ADMIN_RELOAD_TOKEN 一致
    """
    # Token 鉴权
    expected_token = os.environ.get('ADMIN_RELOAD_TOKEN', '')
    provided_token = request.headers.get('X-Admin-Token', '')
    if not expected_token or provided_token != expected_token:
        logger.warning(f"Unauthorized reload attempt from {request.remote_addr}")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        # 调用 reload()：cos 模式先重新下载文件，再清空所有 lru_cache
        data_loader.reload()
        logger.info("数据热重载完成")
        return jsonify({
            'success': True,
            'message': '数据已重新加载，新数据即时生效'
        })
    except Exception as e:
        logger.error(f"Error reloading data: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """
    服务前端静态文件
    """
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend/dist')
    
    # 检查dist目录是否存在
    if not os.path.exists(dist_dir):
        return jsonify({
            'message': 'Frontend not built yet. Please run: cd frontend && npm install && npm run build'
        }), 404
    
    if path and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    else:
        return send_from_directory(dist_dir, 'index.html')


@app.errorhandler(404)
def not_found(e):
    """处理404错误"""
    logger.warning(f"404 Not Found: {request.url}")
    return jsonify({
        'success': False,
        'error': '资源未找到'
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """处理500错误"""
    logger.error(f"500 Internal Server Error: {str(e)}", exc_info=True)
    return jsonify({
        'success': False,
        'error': '服务器内部错误'
    }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("香港小区租售比地图可视化系统 - Flask API服务")
    print("=" * 60)
    print(f"数据源路径: {BASE_PATH}")
    print(f"API服务运行在: http://localhost:5000")
    print(f"API端点:")
    print(f"  - GET /api/estates")
    print(f"  - GET /api/estates/<id>")
    print(f"  - GET /api/rent-ratios")
    print(f"  - GET /api/search?keyword=<关键词>")
    print(f"  - GET /api/primary-schools")
    print("\n安全特性:")
    print(f"  - IP请求频率限制: {MAX_REQUESTS_PER_MINUTE}次/分钟")
    print(f"  - 可疑请求检测与日志记录")
    print(f"  - 访问日志: access.log")
    print("=" * 60)
    
    # 启动Flask应用
    # 生产环境建议关闭debug模式
    app.run(host='0.0.0.0', port=5000, debug=True)
