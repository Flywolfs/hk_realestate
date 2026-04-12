"""
Agent 核心模块
使用 LangChain ReAct Agent 构建香港房产咨询助手。
支持多轮对话（按 session_id 独立维护上下文），线程安全。
"""

import os
import sys
import threading
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'openai')
LLM_MODEL = os.environ.get('LLM_MODEL', 'gpt-4o')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

# 单个用户对话历史最大保留轮数（超出后截断最旧的轮次）
MAX_HISTORY_TURNS = 10


# ============================================================
# System Prompt
# ============================================================

SYSTEM_PROMPT = """你是一位专业的香港房产信息咨询助手，名字叫「港房通」。
你拥有约 9000+ 个香港屋苑的最新数据，包括：
- 屋苑基本信息（名称、地址、所在地区、建成年份、校網等）
- 月度租售比（反映租金投资回报率）及历史时序趋势
- 当前及历史每平方呎成交价（尺价）走势

【职责范围】
- 查询特定屋苑的详细信息
- 按地区列出屋苑列表及价格水平
- 分析租售比，辅助投资决策
- 对比多个屋苑的关键指标
- 根据用户描述的需求语义检索匹配屋苑

【使用工具的策略】
1. 用户直接说出屋苑名称 → 优先使用 search_estate_by_name
2. 用户询问某地区屋苑 → 使用 search_estates_by_area
3. 用户询问租售比/投资回报 → 使用 get_rent_sale_ratio
4. 用户询问价格走势 → 使用 get_price_trend
5. 用户要对比多个屋苑 → 使用 compare_estates
6. 用户描述性需求（模糊/综合条件）→ 优先使用 semantic_search

【回答规范】
- 默认使用简体中文回答（若用户用繁体中文提问则用繁体回答）
- 数据不足时诚实告知，不要编造
- 给出数据后，适当提供简短解读（如租售比含义、投资价值判断）
- 回答要简洁清晰，重要数字用粗体或列表突出显示
- 不在数据范围内的问题（如法律、贷款计算）礼貌说明超出范围

【重要提示】
- 所有数据来自爬虫定期采集，每周更新一次，可能与实时成交有偏差
- 租售比 = 月租金 ÷ 售价，数值越高表示租金回报越好，香港正常范围约 2%–5%
"""


def _build_llm():
    """根据配置构建 LLM 实例。"""
    if LLM_PROVIDER == 'openai':
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=LLM_MODEL,
            temperature=0,
            openai_api_key=OPENAI_API_KEY,
            openai_api_base=OPENAI_BASE_URL,
        )
    elif LLM_PROVIDER == 'deepseek':
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=LLM_MODEL or 'deepseek-chat',
            temperature=0,
            openai_api_key=DEEPSEEK_API_KEY,
            openai_api_base='https://api.deepseek.com/v1',
        )
    else:
        raise ValueError(f"不支持的 LLM_PROVIDER: {LLM_PROVIDER}")


class HKPropertyAgent:
    """
    香港房产咨询 Agent。
    使用 LangGraph create_react_agent（ReAct 框架），支持多轮对话。
    每个 session_id 独立维护消息历史列表（langchain_core.messages）。
    """

    def __init__(self):
        from langgraph.prebuilt import create_react_agent
        from langchain_core.messages import SystemMessage
        from agent.tools import ALL_TOOLS

        self._lock = threading.RLock()
        # session_id -> List[BaseMessage]（完整消息历史）
        self._sessions: Dict[str, list] = {}

        llm = _build_llm()

        # LangGraph create_react_agent：直接传入 system prompt 字符串
        self._graph = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
            prompt=SYSTEM_PROMPT,
        )

        print("[Agent] HKPropertyAgent 初始化完成（LangGraph ReAct）")

    def chat(self, message: str, session_id: str) -> Tuple[str, list]:
        """
        处理用户消息，返回 (回复文本, 使用的工具名称列表)。
        :param message: 用户输入
        :param session_id: 会话 ID（通常为微信 openid）
        :return: (reply, tools_used)
        """
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

        with self._lock:
            history = list(self._sessions.get(session_id, []))

        # 加入本次用户消息
        history.append(HumanMessage(content=message))

        # 截断：保留最近 MAX_HISTORY_TURNS 轮（每轮含 Human+AI 两条消息）
        max_msgs = MAX_HISTORY_TURNS * 2
        if len(history) > max_msgs:
            history = history[-max_msgs:]

        try:
            result = self._graph.invoke({"messages": history})
            # LangGraph 返回更新后的完整消息列表
            updated_messages = result["messages"]

            # 取最后一条 AIMessage 作为回复
            reply = "抱歉，我暂时无法处理您的请求，请稍后再试。"
            for msg in reversed(updated_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    reply = msg.content
                    break

            # 记录本次调用中使用的工具名称（供调试日志用）
            tools_used = [
                msg.name for msg in updated_messages
                if isinstance(msg, ToolMessage)
            ]

        except Exception as e:
            import traceback
            print(f"[Agent] 处理消息异常: {e}")
            traceback.print_exc()
            reply = f"抱歉，处理您的请求时发生错误：{str(e)[:200]}"
            updated_messages = history
            tools_used = []

        # 持久化更新后的消息历史
        # 规则：必须保留 AIMessage(tool_calls) + 紧随的 ToolMessage 成对结构，
        # 否则下一轮 invoke 时 LangGraph 会抛 ValueError。
        # 只丢弃「无 tool_calls 且无内容」的空 AIMessage。
        with self._lock:
            filtered = []
            for m in updated_messages:
                if isinstance(m, AIMessage):
                    # 有 tool_calls 或有文本内容的 AIMessage 都保留
                    if m.tool_calls or m.content:
                        filtered.append(m)
                elif isinstance(m, ToolMessage):
                    # ToolMessage 必须保留（配套 AIMessage tool_calls）
                    filtered.append(m)
                elif isinstance(m, HumanMessage):
                    filtered.append(m)
            # 截断时以「完整轮次」为单位：找到最早的 HumanMessage 位置
            if len(filtered) > max_msgs:
                filtered = filtered[-max_msgs:]
                # 若截断后首条不是 HumanMessage，继续往后找第一条 HumanMessage
                # 保证历史以 Human 开头，避免孤立的 ToolMessage/AIMessage
                for i, m in enumerate(filtered):
                    if isinstance(m, HumanMessage):
                        filtered = filtered[i:]
                        break
            self._sessions[session_id] = filtered

        return reply, tools_used

    def clear_session(self, session_id: str):
        """清除指定用户的对话历史。"""
        with self._lock:
            self._sessions.pop(session_id, None)

    def get_active_sessions(self) -> int:
        """返回当前活跃会话数。"""
        with self._lock:
            return len(self._sessions)


# 模块级单例
_agent_instance: Optional[HKPropertyAgent] = None
_agent_lock = threading.Lock()


def get_agent() -> HKPropertyAgent:
    """获取全局单例 HKPropertyAgent（懒加载 + 线程安全）。"""
    global _agent_instance
    if _agent_instance is None:
        with _agent_lock:
            if _agent_instance is None:
                _agent_instance = HKPropertyAgent()
    return _agent_instance
