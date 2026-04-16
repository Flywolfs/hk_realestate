"""
安全防护模块
提供预检拦截（频率限制、内容安全）和输出截断功能。
"""

import re
import time
import functools
from collections import defaultdict, deque
from typing import Tuple


# ============================================================
# 频率限制
# ============================================================

# {openid: deque([timestamp, ...])}
_rate_limits = defaultdict(lambda: deque(maxlen=200))

# 配置
RATE_LIMIT_PER_MINUTE = 5
RATE_LIMIT_PER_DAY = 50


def check_rate_limit(openid: str) -> Tuple[bool, str]:
    """
    检查用户请求频率。
    :return: (通过, 拒绝原因)。通过时原因为空字符串。
    """
    now = time.time()
    timestamps = _rate_limits[openid]

    # 清理超过 24h 的旧记录
    while timestamps and now - timestamps[0] > 86400:
        timestamps.popleft()

    # 检查每分钟限制
    recent_1min = sum(1 for t in timestamps if now - t < 60)
    if recent_1min >= RATE_LIMIT_PER_MINUTE:
        return False, "您的提问太频繁了，请稍等一分钟再试。"

    # 检查每日限制
    if len(timestamps) >= RATE_LIMIT_PER_DAY:
        return False, "您今日的提问次数已达上限，请明天再来。"

    timestamps.append(now)
    return True, ""


# ============================================================
# 内容安全检查
# ============================================================

# 关键词/模式黑名单（检测 prompt injection 和明显无关话题）
_BLOCKED_PATTERNS = [
    # Prompt injection
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"forget\s+(all\s+)?(previous|above|your)\s+(instructions|rules|prompt)",
    r"disregard\s+(all\s+)?(previous|above|your)",
    r"you\s+are\s+now\s+",
    r"new\s+instructions?\s*:",
    r"system\s*prompt",
    r"reveal\s+(your|the)\s+(system|initial|original)\s*(prompt|instructions|message)",
    r"repeat\s+(your|the)\s+(system|initial|original)\s*(prompt|instructions|message)",
    r"print\s+(your|the)\s+(system|initial|original)\s*(prompt|instructions|message)",
    r"output\s+(your|the)\s+(system|initial|original)\s*(prompt|instructions|message)",
    r"act\s+as\s+(a\s+)?(?!property|real\s*estate|房产|楼市)",
    r"pretend\s+(to\s+be|you\s+are)",
    r"jailbreak",
    r"DAN\s+mode",
    # 明显无关话题
    r"(写|帮我写|生成)(一[篇段个份])?[代码程序脚本]",
    r"(翻译|translate)\s*(以下|这段|this)",
    r"(写|帮我写)(一[篇段])?[作文论文报告]",
]

_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]


def check_content_safety(message: str) -> Tuple[bool, str]:
    """
    检查消息内容安全性。
    :return: (通过, 拒绝原因)。通过时原因为空字符串。
    """
    # 长度限制
    if len(message) > 500:
        return False, "消息太长了，请精简您的问题（不超过500字）。"

    # 关键词检测
    for pattern in _compiled_patterns:
        if pattern.search(message):
            return False, "我是港房通，专注于香港房产咨询。请提出与香港房产相关的问题。"

    return True, ""


# ============================================================
# 输出截断
# ============================================================

MAX_OUTPUT_CHARS = 2000


def truncate_output(func):
    """装饰器：截断工具返回文本，防止过长输出消耗过多 token。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, str) and len(result) > MAX_OUTPUT_CHARS:
            return result[:MAX_OUTPUT_CHARS] + "\n\n...（数据过多，已截断。请缩小查询范围以获取更详细的结果。）"
        return result
    return wrapper
