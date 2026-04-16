"""
Agent 服务 FastAPI 入口
提供异步接口 + 流式输出 + 轮询模式支持。

端点：
  POST /api/agent/chat              - 发送消息（默认异步任务模式，?sync=true 同步）
  POST /api/agent/chat/stream       - 流式发送消息（chunked response）
  GET  /api/agent/chat/result       - 轮询任务结果（?task_id=xxx）
  POST /api/agent/login             - 微信登录
  POST /api/agent/clear             - 清除对话历史
  POST /api/agent/reload            - 热更新数据
  GET  /api/agent/health            - 健康检查
  GET  /api/agent/stats             - 运行统计
  GET  /debug                       - 调试界面
"""

import json
import os
import sys
import logging
import asyncio
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from server.wechat_auth import extract_user_from_headers, get_wechat_session, generate_token
from server.security import check_rate_limit, check_content_safety
from agent.agent_core import get_agent
from data.loader import get_loader

# ============================================================
# FastAPI 应用初始化
# ============================================================
app = FastAPI(title="港房通 Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

ADMIN_TOKEN = os.environ.get('AGENT_ADMIN_TOKEN', '')

# ============================================================
# 异步任务存储（轮询模式，供小程序 callContainer 使用）
# ============================================================
_TASK_TTL = 300  # 任务结果保留 5 分钟
_task_store: dict = {}  # task_id -> {status, partial_reply, tools_used, created_at, ...}


def _cleanup_expired_tasks():
    """清理过期任务（惰性清理，每次创建新任务时调用）。"""
    now = time.time()
    expired = [tid for tid, t in _task_store.items() if now - t['created_at'] > _TASK_TTL]
    for tid in expired:
        del _task_store[tid]


async def _run_agent_task(task_id: str, message: str, session_id: str):
    """后台协程：执行 Agent 对话并实时更新任务状态。"""
    task = _task_store.get(task_id)
    if not task:
        return
    try:
        agent = get_agent()
        async for event in agent.astream_chat(message, session_id):
            if task_id not in _task_store:
                return  # 任务已被清理
            if event.get('type') == 'token':
                task['partial_reply'] += event.get('text', '')
            elif event.get('type') == 'status':
                task['status_text'] = event.get('text', '')
                tool_name = event.get('tool', '')
                if tool_name and tool_name not in task['tools_used']:
                    task['tools_used'].append(tool_name)
            elif event.get('type') == 'done':
                break
        task['status'] = 'done'
    except Exception as e:
        logger.error(f"[Task] {task_id} 异常: {e}", exc_info=True)
        task['status'] = 'error'
        task['error'] = str(e)[:200]
        if not task['partial_reply']:
            task['partial_reply'] = '服务暂时不可用，请稍后重试'


# ============================================================
# 鉴权依赖
# ============================================================

async def get_current_user(request: Request) -> dict:
    """FastAPI 依赖注入：从请求头提取用户身份。"""
    headers = dict(request.headers)
    user = extract_user_from_headers(headers)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def verify_admin(request: Request):
    """管理接口鉴权。"""
    if ADMIN_TOKEN:
        provided = request.headers.get('X-Admin-Token', '')
        if provided != ADMIN_TOKEN:
            raise HTTPException(status_code=403, detail="管理鉴权失败")


# ============================================================
# 请求体模型
# ============================================================

class ChatRequest(BaseModel):
    message: str

class LoginRequest(BaseModel):
    code: str

class ReloadRequest(BaseModel):
    rebuild_vector: bool = False


# ============================================================
# 接口实现
# ============================================================

@app.get('/api/agent/health')
async def health():
    try:
        loader = get_loader()
        stats = loader.get_stats()
        return {'success': True, 'status': 'ok', 'data_stats': stats}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={'success': False, 'status': 'error', 'error': str(e)},
        )


@app.post('/api/agent/login')
async def login(body: LoginRequest):
    if not body.code:
        raise HTTPException(status_code=400, detail="缺少 code 参数")

    session = get_wechat_session(body.code)
    if not session:
        raise HTTPException(status_code=401, detail="微信登录失败，请重试")

    openid = session['openid']
    token = generate_token(openid)
    logger.info(f"[Login] openid: {openid[:12]}... 登录成功")

    return {'success': True, 'token': token, 'openid': openid}


@app.post('/api/agent/chat')
async def chat(
    body: ChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    sync: bool = Query(default=False, description="同步模式：等待完整回复后返回"),
):
    """
    对话接口。

    默认异步任务模式（适配小程序 callContainer 轮询）：
      - 立即返回 {task_id}，后台协程执行 Agent 对话
      - 小程序通过 GET /api/agent/chat/result?task_id=xxx 轮询结果

    ?sync=true 同步模式（Debug UI / 直连场景）：
      - 等待 Agent 执行完毕后返回完整 JSON
    """
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    session_id = user['openid']

    # 预检拦截
    rate_ok, rate_reason = check_rate_limit(session_id)
    if not rate_ok:
        return JSONResponse(status_code=429, content={'success': False, 'error': rate_reason})

    safe_ok, safe_reason = check_content_safety(message)
    if not safe_ok:
        return {'success': True, 'reply': safe_reason, 'session_id': session_id}

    logger.info(f"[Chat] session={session_id[:12]}... msg_len={len(message)} sync={sync}")

    # --- 同步模式 ---
    if sync:
        try:
            agent = get_agent()
            reply, tools_used = await agent.achat(message, session_id)
        except Exception as e:
            logger.error(f"[Chat] Agent 异常: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={'success': False, 'error': '服务暂时不可用，请稍后重试'},
            )
        return {'success': True, 'reply': reply, 'session_id': session_id, 'tools_used': tools_used}

    # --- 异步任务模式 ---
    _cleanup_expired_tasks()

    task_id = uuid.uuid4().hex[:16]
    _task_store[task_id] = {
        'status': 'processing',
        'partial_reply': '',
        'tools_used': [],
        'status_text': '',
        'error': '',
        'session_id': session_id,
        'created_at': time.time(),
    }

    asyncio.create_task(_run_agent_task(task_id, message, session_id))
    logger.info(f"[Task] 创建任务 {task_id} for session={session_id[:12]}...")

    return {'success': True, 'task_id': task_id, 'session_id': session_id}


@app.get('/api/agent/chat/result')
async def chat_result(
    task_id: str = Query(..., description="任务 ID"),
    user: dict = Depends(get_current_user),
):
    """
    轮询任务结果。

    小程序通过 callContainer 每 1s 调用此接口获取进度。

    返回：
      - status: "processing" | "done" | "error"
      - partial_reply: 当前已生成的回复文本（实时递增）
      - tools_used: 已调用的工具列表
      - status_text: 当前状态描述（如 "正在查询太古城价格趋势..."）
    """
    task = _task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    # 验证任务归属
    if task['session_id'] != user['openid']:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    return {
        'success': True,
        'status': task['status'],
        'partial_reply': task['partial_reply'],
        'tools_used': task['tools_used'],
        'status_text': task['status_text'],
    }


@app.post('/api/agent/chat/stream')
async def chat_stream(body: ChatRequest, user: dict = Depends(get_current_user)):
    """流式对话接口（chunked response）。"""
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    session_id = user['openid']

    # 预检拦截
    rate_ok, rate_reason = check_rate_limit(session_id)
    if not rate_ok:
        return JSONResponse(status_code=429, content={'success': False, 'error': rate_reason})

    safe_ok, safe_reason = check_content_safety(message)
    if not safe_ok:
        async def reject_gen():
            yield json.dumps({"type": "token", "text": safe_reason}, ensure_ascii=False) + "\n"
            yield json.dumps({"type": "done", "text": ""}) + "\n"
        return StreamingResponse(reject_gen(), media_type="text/plain; charset=utf-8")

    logger.info(f"[Stream] session={session_id[:12]}... msg_len={len(message)}")

    async def event_generator():
        try:
            agent = get_agent()
            async for event in agent.astream_chat(message, session_id):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as e:
            logger.error(f"[Stream] 异常: {e}", exc_info=True)
            yield json.dumps({"type": "token", "text": f"服务异常：{str(e)[:200]}"}, ensure_ascii=False) + "\n"
            yield json.dumps({"type": "done", "text": ""}) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Accel-Buffering": "no"},  # Disable nginx buffering
    )


@app.post('/api/agent/clear')
async def clear_session(user: dict = Depends(get_current_user)):
    session_id = user['openid']
    agent = get_agent()
    agent.clear_session(session_id)
    logger.info(f"[Clear] session={session_id[:12]}... 对话历史已清除")
    return {'success': True, 'message': '对话历史已清除'}


@app.post('/api/agent/reload')
async def reload_data(body: ReloadRequest, request: Request):
    verify_admin(request)

    logger.info("[Reload] 开始热更新数据...")
    try:
        loader = get_loader()
        loader.reload()

        if body.rebuild_vector:
            from data.vector_store import get_vector_store
            vs = get_vector_store()
            vs.build_index(loader=loader)
            logger.info("[Reload] 向量索引重建完成")

        stats = loader.get_stats()
        logger.info(f"[Reload] 热更新完成，屋苑总数: {stats['total_estates']}")
        return {'success': True, 'message': '数据热更新完成', 'stats': stats}
    except Exception as e:
        logger.error(f"[Reload] 热更新失败: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@app.get('/api/agent/stats')
async def stats(request: Request):
    verify_admin(request)

    loader = get_loader()
    agent = get_agent()
    data_stats = loader.get_stats()

    from data.vector_store import get_vector_store
    vs = get_vector_store()

    return {
        'success': True,
        'active_sessions': agent.get_active_sessions(),
        'vector_index_ready': vs.is_ready(),
        'data': data_stats,
    }


@app.get('/debug')
async def debug_ui():
    ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_ui.html')
    return FileResponse(ui_path, media_type='text/html')


# ============================================================
# 启动入口
# ============================================================

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('FLASK_PORT', 5001))
    logger.info(f"[Server] 港房通 Agent 服务启动 (FastAPI)，监听端口 {port}")
    uvicorn.run(app, host='0.0.0.0', port=port)
