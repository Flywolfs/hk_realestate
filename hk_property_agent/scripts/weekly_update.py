"""
每周数据热更新脚本
执行以下操作：
  1. 从 COS 对象存储下载最新数据文件到本地缓存
  2. 重新构建 Chroma 向量索引
  3. 发送 POST /api/agent/reload 请求通知运行中的服务刷新内存

使用方式：
  # 本地手动执行
  python scripts/weekly_update.py

  # 只下载数据，不重建向量索引
  python scripts/weekly_update.py --no-vector

  # 只重建向量索引（数据已是最新）
  python scripts/weekly_update.py --vector-only

  # 指定 Agent 服务地址（默认 http://localhost:5001）
  python scripts/weekly_update.py --server http://your-server:5001

触发方式（云托管）：
  在微信云托管定时任务中调用 POST /api/agent/reload?rebuild_vector=true
"""

import argparse
import os
import sys
import time

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass


def step_download_data():
    """Step 1: 从 COS 下载最新数据文件。"""
    print("\n[Step 1] 从 COS 下载最新数据...")

    data_mode = os.environ.get('DATA_MODE', 'local')
    if data_mode != 'cos':
        print(f"  DATA_MODE={data_mode}，跳过 COS 下载（local 模式直接使用本地文件）")
        return True

    try:
        from data.loader import _download_from_cos
        paths = _download_from_cos()
        print(f"  下载完成，共 {len(paths)} 个文件")
        for k, v in paths.items():
            print(f"    {k}: {v}")
        return True
    except Exception as e:
        print(f"  [ERROR] COS 下载失败: {e}")
        return False


def step_reload_data_in_process():
    """Step 2a: 在当前进程中重新加载数据（适合独立运行时）。"""
    print("\n[Step 2] 重新加载数据到内存...")
    try:
        from data.loader import get_loader
        loader = get_loader()
        loader.reload()
        stats = loader.get_stats()
        print(f"  数据加载完成: {stats['total_estates']} 个屋苑，{stats['total_areas']} 个地区")
        return loader
    except Exception as e:
        print(f"  [ERROR] 数据加载失败: {e}")
        return None


def step_build_vector_index(loader=None):
    """Step 3: 重新构建向量索引。"""
    print("\n[Step 3] 构建向量索引...")
    start = time.time()
    try:
        from data.vector_store import get_vector_store
        vs = get_vector_store()
        vs.build_index(loader=loader)
        elapsed = time.time() - start
        print(f"  向量索引构建完成，耗时 {elapsed:.1f} 秒")
        return True
    except Exception as e:
        print(f"  [ERROR] 向量索引构建失败: {e}")
        return False


def step_notify_server(server_url: str, rebuild_vector: bool, admin_token: str):
    """Step 4: 通知运行中的 Agent 服务执行热更新。"""
    print(f"\n[Step 4] 通知服务端热更新: {server_url}")
    try:
        import requests
        url = f"{server_url.rstrip('/')}/api/agent/reload"
        headers = {}
        if admin_token:
            headers['X-Admin-Token'] = admin_token

        payload = {'rebuild_vector': rebuild_vector}
        resp = requests.post(url, json=payload, headers=headers, timeout=300)
        data = resp.json()

        if data.get('success'):
            stats = data.get('stats', {})
            print(f"  服务端热更新成功: {stats.get('total_estates', '?')} 个屋苑")
            return True
        else:
            print(f"  [ERROR] 服务端返回失败: {data.get('error', '未知错误')}")
            return False
    except Exception as e:
        print(f"  [WARNING] 通知服务端失败（服务可能未启动）: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='香港房产 Agent 数据热更新脚本')
    parser.add_argument('--no-vector', action='store_true', help='跳过向量索引重建')
    parser.add_argument('--vector-only', action='store_true', help='只重建向量索引，不重新下载数据')
    parser.add_argument('--server', default='', help='Agent 服务地址（默认从 AGENT_SERVER_URL 环境变量读取）')
    parser.add_argument('--no-notify', action='store_true', help='不通知运行中的服务')
    args = parser.parse_args()

    server_url = args.server or os.environ.get('AGENT_SERVER_URL', 'http://localhost:5001')
    admin_token = os.environ.get('AGENT_ADMIN_TOKEN', '')

    print("=" * 60)
    print("  香港房产 Agent 数据热更新")
    print("=" * 60)

    loader = None

    if not args.vector_only:
        # Step 1: 下载数据
        step_download_data()

        # Step 2: 加载数据
        loader = step_reload_data_in_process()

    if not args.no_vector:
        # Step 3: 重建向量索引
        step_build_vector_index(loader=loader)

    if not args.no_notify:
        # Step 4: 通知服务端
        step_notify_server(
            server_url=server_url,
            rebuild_vector=not args.no_vector,
            admin_token=admin_token,
        )

    print("\n[Done] 热更新流程执行完毕")
    print("=" * 60)


if __name__ == '__main__':
    main()
