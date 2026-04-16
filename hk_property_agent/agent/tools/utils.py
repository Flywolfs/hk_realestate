"""
工具层公共工具函数。
"""

from opencc import OpenCC

_cc_s2t = OpenCC('s2t')


def to_traditional(text: str) -> str:
    """将简体中文转换为繁体中文。用于工具接收用户输入后、查询数据前的标准化。"""
    if not text:
        return text
    return _cc_s2t.convert(text)
