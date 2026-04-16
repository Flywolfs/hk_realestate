"""
Agent 服务 Flask 入口
暴露以下接口供微信小程序调用：
  POST /api/agent/chat       - 发送消息
  POST /api/agent/login      - 微信登录（换取 JWT）
  POST /api/agent/clear      - 清除对话历史
  POST /api/agent/reload     - 热更新数据（管理接口）
  GET  /api/agent/health     - 健康检查

注意：本服务完全独立于 28hse_system/backend/app.py，
      不记录请求次数，不干扰现有 API 统计体系。
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from server.wechat_auth import login_required, get_user_from_request, get_wechat_session, generate_token
from server.security import check_rate_limit, check_content_safety
from agent.agent_core import get_agent
from data.loader import get_loader

# ============================================================
# Flask 应用初始化
# ============================================================
app = Flask(__name__)
CORS(app, origins=['*'], supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'OPTIONS'])

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# 管理接口鉴权 token（从环境变量读取）
ADMIN_TOKEN = os.environ.get('AGENT_ADMIN_TOKEN', '')


# ============================================================
# 接口实现
# ============================================================

@app.route('/api/agent/health', methods=['GET'])
def health():
    """健康检查接口，同时返回数据加载状态。"""
    try:
        loader = get_loader()
        stats = loader.get_stats()
        return jsonify({
            'success': True,
            'status': 'ok',
            'data_stats': stats,
        })
    except Exception as e:
        return jsonify({'success': False, 'status': 'error', 'error': str(e)}), 500


@app.route('/api/agent/login', methods=['POST'])
def login():
    """
    微信小程序登录接口。
    请求体: { "code": "<wx.login 获取的临时 code>" }
    响应: { "success": true, "token": "<JWT>", "openid": "..." }
    """
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')

    if not code:
        return jsonify({'success': False, 'error': '缺少 code 参数'}), 400

    session = get_wechat_session(code)
    if not session:
        return jsonify({'success': False, 'error': '微信登录失败，请重试'}), 401

    openid = session['openid']
    token = generate_token(openid)
    logger.info(f"[Login] openid: {openid[:12]}... 登录成功")

    return jsonify({
        'success': True,
        'token': token,
        'openid': openid,
    })


@app.route('/api/agent/chat', methods=['POST'])
@login_required
def chat():
    """
    对话接口（核心接口）。
    请求头: Authorization: Bearer <token>  （或云托管自动注入 X-WX-FROM-OPENID）
    请求体: { "message": "沙田有什么租售比低的屋苑？" }
    响应: { "success": true, "reply": "...", "session_id": "..." }
    """
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()

    if not message:
        return jsonify({'success': False, 'error': '消息内容不能为空'}), 400

    user = request.current_user
    session_id = user['openid']

    # 预检拦截：频率限制
    rate_ok, rate_reason = check_rate_limit(session_id)
    if not rate_ok:
        return jsonify({'success': False, 'error': rate_reason}), 429

    # 预检拦截：内容安全
    safe_ok, safe_reason = check_content_safety(message)
    if not safe_ok:
        return jsonify({'success': True, 'reply': safe_reason, 'session_id': session_id})

    logger.info(f"[Chat] session={session_id[:12]}... msg_len={len(message)}")

    try:
        agent = get_agent()
        reply, _ = agent.chat(message, session_id)
    except Exception as e:
        logger.error(f"[Chat] Agent 异常: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': '服务暂时不可用，请稍后重试',
        }), 500

    return jsonify({
        'success': True,
        'reply': reply,
        'session_id': session_id,
    })


@app.route('/api/agent/clear', methods=['POST'])
@login_required
def clear_session():
    """
    清除当前用户的对话历史（开始新对话）。
    """
    user = request.current_user
    session_id = user['openid']

    agent = get_agent()
    agent.clear_session(session_id)
    logger.info(f"[Clear] session={session_id[:12]}... 对话历史已清除")

    return jsonify({'success': True, 'message': '对话历史已清除'})


@app.route('/api/agent/reload', methods=['POST'])
def reload_data():
    """
    热更新数据接口（管理专用）。
    重新从 COS 下载最新数据并刷新内存，无需重启服务。
    鉴权：请求头 X-Admin-Token: <AGENT_ADMIN_TOKEN>
    """
    if ADMIN_TOKEN:
        provided = request.headers.get('X-Admin-Token', '')
        if provided != ADMIN_TOKEN:
            return jsonify({'success': False, 'error': '管理鉴权失败'}), 403

    logger.info("[Reload] 开始热更新数据...")
    try:
        loader = get_loader()
        loader.reload()

        # 同步重建向量索引
        rebuild_vector = request.get_json(silent=True) or {}
        if rebuild_vector.get('rebuild_vector', False):
            from data.vector_store import get_vector_store
            vs = get_vector_store()
            vs.build_index(loader=loader)
            logger.info("[Reload] 向量索引重建完成")

        stats = loader.get_stats()
        logger.info(f"[Reload] 热更新完成，屋苑总数: {stats['total_estates']}")

        return jsonify({
            'success': True,
            'message': '数据热更新完成',
            'stats': stats,
        })
    except Exception as e:
        logger.error(f"[Reload] 热更新失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/agent/stats', methods=['GET'])
def stats():
    """返回 Agent 服务运行统计（会话数、数据状态）。"""
    if ADMIN_TOKEN:
        provided = request.headers.get('X-Admin-Token', '')
        if provided != ADMIN_TOKEN:
            return jsonify({'success': False, 'error': '管理鉴权失败'}), 403

    loader = get_loader()
    agent = get_agent()
    data_stats = loader.get_stats()

    from data.vector_store import get_vector_store
    vs = get_vector_store()

    return jsonify({
        'success': True,
        'active_sessions': agent.get_active_sessions(),
        'vector_index_ready': vs.is_ready(),
        'data': data_stats,
    })


@app.route('/debug', methods=['GET'])
def debug_ui():
    """本地调试界面，仅开发时使用。"""
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        'debug_ui.html'
    )


# ============================================================
# 启动入口
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    logger.info(f"[Server] 香港房产 Agent 服务启动，监听端口 {port}")
    logger.info(f"[Server] 数据模式: {os.environ.get('DATA_MODE', 'local')}")

    app.run(host='0.0.0.0', port=port, debug=debug)
