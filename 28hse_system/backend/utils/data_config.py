"""
数据源配置文件
支持两种模式，通过环境变量 DATA_MODE 切换：
  - local : 直接读取本地文件路径（默认，用于本地开发调试）
  - cos   : 从微信云托管对象存储（COS）下载文件后读取（用于云端部署）

使用方式：
  本地调试：复制 .env.example 为 .env，填写实际值，无需改动代码。
  云托管部署：在云托管控制台「服务设置 → 环境变量」中直接配置，不使用 .env 文件。
"""

import os

# 本地开发时从 .env 文件加载环境变量
# 云托管容器中环境变量由控制台注入，dotenv 不会覆盖已存在的系统环境变量
try:
    from dotenv import load_dotenv
    # .env 文件与 utils/ 目录同级（backend/.env）
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass  # 未安装 python-dotenv 时跳过（云托管镜像中不依赖此库）

# ============================================================
# 模式开关（local / cos）
# ============================================================
DATA_MODE = os.environ.get('DATA_MODE', 'local')

# ============================================================
# LOCAL 模式：本地文件绝对路径
# 本地调试时修改这里即可
# ============================================================
_LOCAL_CENTANET_DIR = '/home/zhangchi/Documents/28hse/centanet_system/crawler'
_LOCAL_28HSE_DIR    = '/home/zhangchi/Documents/28hse/28hse_system'

LOCAL_PATHS = {
    # 屋苑静态信息（含坐标、基本资料）
    'estate_static':       f'{_LOCAL_CENTANET_DIR}/estate_info_20260221_convert.json',
    # 租售比数据
    'rent_ratio':          f'{_LOCAL_CENTANET_DIR}/average_rent_sale_ratio.json',
    # 公屋/居屋类型名单
    'housing_types':       f'{_LOCAL_28HSE_DIR}/housing_types.json',
    # 月度尺价趋势（以 typeCode 为键）
    'price_trend':         f'{_LOCAL_CENTANET_DIR}/monthly_price_trend_20260314.json',
    # 屋苑 typeCode -> estateName 映射源文件
    'estate_info':         f'{_LOCAL_CENTANET_DIR}/estate_info_20260221.json',
    # 预计算动态数据（面积范围 + 当前尺价），由 preprocess_dynamic_estate_data.py 生成
    'dynamic_estate_data': f'{_LOCAL_CENTANET_DIR}/dynamic_estate_data.json',
    # 交易记录 buy 目录（本地回退用）
    'transaction_buy_dir': f'{_LOCAL_CENTANET_DIR}/transaction_record_20260314_trans/buy',
}

# ============================================================
# COS 模式：云托管对象存储配置
# 所有敏感参数通过环境变量传入，不要硬编码在代码中
# ============================================================

# COS bucket 名称（如 prod-xxxxxxxx，可在云托管控制台查看）
COS_BUCKET = os.environ.get('COS_BUCKET', '')
# COS 地域（如 ap-guangzhou 或 ap-hongkong）
COS_REGION = os.environ.get('COS_REGION', 'ap-guangzhou')
# 腾讯云访问密钥（建议使用子账号最小权限）
COS_SECRET_ID  = os.environ.get('COS_SECRET_ID', '')
COS_SECRET_KEY = os.environ.get('COS_SECRET_KEY', '')

# 容器内数据文件下载目录（运行时写入，不打包进镜像）
COS_LOCAL_CACHE_DIR = os.environ.get('COS_LOCAL_CACHE_DIR', '/tmp/data')

# COS 上各数据文件的对象键（Key）
# 上传数据文件时请保持与此处一致的路径
COS_KEYS = {
    'estate_static':       'data/estate_info_convert.json',
    'rent_ratio':          'data/average_rent_sale_ratio.json',
    'housing_types':       'data/housing_types.json',
    'price_trend':         'data/monthly_price_trend.json',
    'estate_info':         'data/estate_info.json',
    'dynamic_estate_data': 'data/dynamic_estate_data.json',
}
