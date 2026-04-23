"""
工具层公共工具函数。
"""

import logging
import time

from opencc import OpenCC

_cc_s2t = OpenCC('s2t')

# 工具调用日志 logger
logger = logging.getLogger("agent.tools")


def to_traditional(text: str) -> str:
    """将简体中文转换为繁体中文。用于工具接收用户输入后、查询数据前的标准化。"""
    if not text:
        return text
    return _cc_s2t.convert(text)


# ------------------------------------------------------------------
# 工具调用日志
# ------------------------------------------------------------------

def setup_tool_logging():
    """配置工具调用日志，格式包含文件名和行号。只初始化一次。"""
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(filename)s:%(lineno)d [%(levelname)s] %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def wrap_tool_with_logging(tool):
    """
    为 LangChain Tool 包装底层函数，自动记录入参和返回结果。
    使用 StructuredTool.from_function 重建工具，保留原始 name/description/args_schema。
    """
    from langchain_core.tools import StructuredTool

    original_func = tool.func
    tool_name = tool.name

    def logged_func(*args, **kwargs):
        # 过滤掉值为 None 的默认参数，减少日志噪音
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        params = filtered_kwargs if filtered_kwargs else (args if args else {})
        logger.info("[Tool调用] %s | 入参=%s", tool_name, _safe_str(params, 300))
        start_time = time.time()
        try:
            result = original_func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(
                "[Tool返回] %s | 耗时=%.2fs | 结果=%s",
                tool_name, elapsed, _safe_str(result, 500)
            )
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "[Tool异常] %s | 耗时=%.2fs | 错误=%s",
                tool_name, elapsed, e
            )
            raise

    return StructuredTool.from_function(
        func=logged_func,
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
    )


def _safe_str(obj, max_len=200):
    """安全地将对象转为字符串，截断过长内容。"""
    try:
        s = str(obj)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s
    except Exception:
        return "<无法序列化>"


if __name__ == "__main__":
    # ====== 手动调试入口 ======
    # 用法: python agent/tools/utils.py

    test_cases = [
        "沙田区",       # 简体
        "沙田區",       # 繁体
        "将军澳",       # 简体
        "將軍澳",       # 繁体
        "",             # 空字符串
    ]

    print("===== to_traditional 测试 =====")
    for t in test_cases:
        result = to_traditional(t)
        print(f"  输入: {repr(t):12s} -> 输出: {repr(result)}")
