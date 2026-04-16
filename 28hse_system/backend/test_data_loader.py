"""
data_loader 功能验证脚本
用法：
  # 测试 local 模式（默认）
  python3 test_data_loader.py

  # 测试 cos 模式（需先在 .env 中配置 COS_* 参数）
  DATA_MODE=cos python3 test_data_loader.py

  # 测试热重载接口（需后端正在运行）
  python3 test_data_loader.py --reload --token your_secret_token
"""

import sys
import os
import json

# 将 backend 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ----------------------------------------------------------------
# 测试热重载接口（--reload 参数）
# ----------------------------------------------------------------
if '--reload' in sys.argv:
    import requests
    token_idx = sys.argv.index('--token') if '--token' in sys.argv else -1
    token = sys.argv[token_idx + 1] if token_idx != -1 else ''
    host = os.environ.get('BACKEND_URL', 'http://localhost:5000')
    url = f'{host}/api/admin/refresh-data'
    print(f'\n[热重载测试] POST {url}')
    resp = requests.post(url, headers={'X-Admin-Token': token}, timeout=60)
    print(f'状态码: {resp.status_code}')
    print(f'响应:   {resp.text}')
    sys.exit(0)


# ----------------------------------------------------------------
# 测试 data_loader 数据加载
# ----------------------------------------------------------------
from utils import data_config

print('=' * 60)
print(f'当前 DATA_MODE: {data_config.DATA_MODE}')
print('=' * 60)

# 初始化 DataLoader
from utils.data_loader import DataLoader

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
# backend 上级目录（即 28hse_system/）
BASE_PATH_PARENT = os.path.dirname(BASE_PATH)

print('\n[1] 初始化 DataLoader ...')
try:
    loader = DataLoader(BASE_PATH_PARENT)
    print('    ✓ 初始化成功')
except Exception as e:
    print(f'    ✗ 初始化失败: {e}')
    sys.exit(1)

# ---- 检查文件路径 ----
print('\n[2] 数据文件路径解析结果:')
paths = {
    'estate_static':       loader.estate_static_path,
    'rent_ratio':          loader.rent_ratio_path,
    'housing_types':       loader.housing_types_path,
    'price_trend':         loader.price_trend_path,
    'dynamic_estate_data': loader.dynamic_estate_data_path,
    'transaction_buy_dir': loader.transaction_buy_path,
}
all_ok = True
for name, path in paths.items():
    exists = os.path.exists(path) if path else False
    status = '✓' if exists else '✗ 不存在'
    print(f'    {status}  {name}: {path}')
    if not exists:
        all_ok = False

# ---- 加载各数据文件 ----
print('\n[3] 加载数据文件:')

def test_load(label, fn):
    try:
        result = fn()
        if isinstance(result, dict):
            print(f'    ✓  {label}: {len(result)} 条记录')
        elif isinstance(result, list):
            print(f'    ✓  {label}: {len(result)} 条记录')
        else:
            print(f'    ✓  {label}: {type(result).__name__}')
        return result
    except Exception as e:
        print(f'    ✗  {label}: {e}')
        return None

estate_static  = test_load('屋苑静态信息 (estate_static)',  loader.load_estate_static_info)
rent_ratio     = test_load('租售比数据 (rent_ratio)',        loader.load_rent_ratio_data)
housing_types  = test_load('公屋/居屋类型 (housing_types)', loader.load_housing_types)
price_trend    = test_load('尺价趋势 (price_trend)',         loader.load_price_trend_by_numeric_id)
dynamic_data   = test_load('预计算动态数据 (dynamic_estate)', loader.load_dynamic_estate_data)

# ---- 抽样检查 dynamic_estate_data ----
if dynamic_data:
    print('\n[4] dynamic_estate_data 抽样检查（前3条）:')
    for i, (eid, val) in enumerate(dynamic_data.items()):
        print(f'    estate_id={eid}: {json.dumps(val, ensure_ascii=False)}')
        if i >= 2:
            break

# ---- 检查 get_integrated_estates ----
print('\n[5] get_integrated_estates（屋苑列表，含坐标的）:')
try:
    estates = loader.get_integrated_estates()
    print(f'    ✓  共 {len(estates)} 个有坐标屋苑')
    if estates:
        sample = estates[0]
        print(f'    抽样: id={sample["id"]}, name={sample["name"]}, '
              f'rent_ratio={sample.get("rent_ratio")}, '
              f'price_per_sqft={sample.get("current_price_per_sqft")}')
except Exception as e:
    print(f'    ✗  {e}')

# ---- 测试 reload() ----
print('\n[6] 测试 reload()（清空缓存后重新加载）:')
try:
    loader.reload()
    estates2 = loader.get_integrated_estates()
    print(f'    ✓  reload 后屋苑数: {len(estates2)}')
except Exception as e:
    print(f'    ✗  {e}')

print('\n' + '=' * 60)
print('测试完成')
print('=' * 60)
