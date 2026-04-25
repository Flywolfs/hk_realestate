"""
用户对话日志模块
记录用户提问、ReAct 推理过程、最终回复，支持本地 JSONL 文件 + COS 双写。

架构：
  1. 写本地 JSONL 文件（即时，零延迟）
  2. 异步上传到 COS（后台线程，去抖 3 秒）

文件组织：
  - 本地: /tmp/agent_logs/YYYY-MM-DD.jsonl
  - COS:  logs/YYYY-MM-DD.jsonl
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

# ============================================================
# 配置
# ============================================================
LOG_DIR = os.environ.get('AGENT_LOG_DIR', '/tmp/agent_logs')
COS_LOG_PREFIX = 'logs/'

# COS 日志专用凭证（独立于数据服务的只读凭证）
# 优先使用日志专用环境变量，若无则回退到数据服务凭证
COS_BUCKET = os.environ.get('COS_LOG_BUCKET', '') or os.environ.get('COS_BUCKET', '')
COS_REGION = os.environ.get('COS_LOG_REGION', '') or os.environ.get('COS_REGION', 'ap-guangzhou')
COS_SECRET_ID = os.environ.get('COS_LOG_SECRET_ID', '') or os.environ.get('COS_SECRET_ID', '')
COS_SECRET_KEY = os.environ.get('COS_LOG_SECRET_KEY', '') or os.environ.get('COS_SECRET_KEY', '')


class ConversationLogger:
    """
    线程安全的对话日志记录器（模块级单例）。

    每次对话生成一条 JSONL 记录，包含：
    - openid, source, question, timestamp
    - react_steps: ReAct 推理过程（thought / tool_call / tool_result）
    - tools_used, final_reply, duration_ms, mode
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cos_client = None
        self._cos_enabled = bool(COS_BUCKET and COS_SECRET_ID and COS_SECRET_KEY)
        # 去抖定时器
        self._sync_timer: Optional[threading.Timer] = None
        self._sync_debounce_seconds = 3.0
        os.makedirs(LOG_DIR, exist_ok=True)

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def log_conversation(
        self,
        openid: str,
        source: str,
        question: str,
        react_steps: list,
        tools_used: list,
        final_reply: str,
        duration_ms: int,
        mode: str,
        question_time: str = '',
    ):
        """
        记录一次完整的对话。

        :param openid: 用户标识
        :param source: 鉴权来源（call_container / cloud_call / jwt_token）
        :param question: 用户提问
        :param react_steps: ReAct 推理步骤列表
        :param tools_used: 使用的工具名称列表
        :param final_reply: 最终回复
        :param duration_ms: 耗时（毫秒）
        :param mode: 对话模式（sync / stream / async）
        :param question_time: 用户提问时间（ISO格式），若为空则取当前时间
        """
        record = {
            'id': uuid.uuid4().hex[:16],
            'timestamp': question_time or datetime.now().isoformat(),
            'openid': openid,
            'source': source,
            'question': question,
            'react_steps': react_steps,
            'tools_used': tools_used,
            'final_reply': final_reply[:2000] if final_reply else '',
            'duration_ms': duration_ms,
            'mode': mode,
        }

        self._write_local(record)
        self._schedule_cos_sync()

    def get_recent_logs(self, date: Optional[str] = None, limit: int = 50) -> list:
        """
        读取本地日志记录。

        :param date: 日期字符串 YYYY-MM-DD，默认今天
        :param limit: 最大返回条数
        :return: 日志记录列表（最新在前）
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        file_path = os.path.join(LOG_DIR, f'{date}.jsonl')

        if not os.path.exists(file_path):
            return []

        records = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"[ConversationLogger] 读取日志失败: {e}")

        # 最新在前
        records.reverse()
        return records[:limit]

    def get_available_dates(self) -> list:
        """返回本地有日志文件的日期列表（最新在前）。"""
        dates = []
        try:
            for fname in os.listdir(LOG_DIR):
                if fname.endswith('.jsonl') and len(fname) == 14:
                    dates.append(fname[:-6])  # 去掉 .jsonl
        except Exception:
            pass
        dates.sort(reverse=True)
        return dates

    def download_log_file(self, date: Optional[str] = None) -> Optional[str]:
        """
        返回日志文件路径供下载。

        :param date: 日期字符串，默认今天
        :return: 文件路径或 None
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        file_path = os.path.join(LOG_DIR, f'{date}.jsonl')

        if os.path.exists(file_path):
            return file_path

        # 本地不存在，尝试从 COS 下载
        if self._cos_enabled:
            return self._download_from_cos(date)

        return None

    def trigger_cos_sync(self, date: Optional[str] = None) -> dict:
        """
        手动触发 COS 同步。

        :param date: 日期字符串，默认今天
        :return: 同步结果
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        file_path = os.path.join(LOG_DIR, f'{date}.jsonl')

        if not os.path.exists(file_path):
            return {'success': False, 'error': f'{date} 的日志文件不存在'}

        if not self._cos_enabled:
            return {'success': False, 'error': 'COS 未配置（缺少 COS_BUCKET/COS_SECRET_ID/COS_SECRET_KEY）'}

        ok = self._upload_to_cos(file_path, date)
        if ok:
            return {'success': True, 'message': f'{date} 日志已上传到 COS'}
        else:
            return {'success': False, 'error': '上传失败，请查看服务日志'}

    def test_cos_write(self) -> dict:
        """测试 COS 写入权限，返回诊断结果。"""
        if not self._cos_enabled:
            return {'success': False, 'error': 'COS 未配置（缺少 COS_BUCKET/COS_SECRET_ID/COS_SECRET_KEY）'}

        client = self._get_cos_client()
        if client is None:
            return {'success': False, 'error': 'COS 客户端初始化失败'}

        import tempfile
        test_content = f'cos-write-test-{datetime.now().isoformat()}'
        results = {}

        # 测试1: 尝试上传到 logs/ 前缀
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(test_content)
                tmp_path = f.name
            client.upload_file(Bucket=COS_BUCKET, Key='logs/_write_test.txt', LocalFilePath=tmp_path)
            results['logs_prefix'] = {'success': True}
            # 清理测试文件
            try:
                client.delete_object(Bucket=COS_BUCKET, Key='logs/_write_test.txt')
            except Exception:
                pass
        except Exception as e:
            results['logs_prefix'] = {'success': False, 'error': str(e)[:300]}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # 测试2: 尝试上传到 data/ 前缀（现有数据所在路径）
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(test_content)
                tmp_path = f.name
            client.upload_file(Bucket=COS_BUCKET, Key='data/_write_test.txt', LocalFilePath=tmp_path)
            results['data_prefix'] = {'success': True}
            # 清理测试文件
            try:
                client.delete_object(Bucket=COS_BUCKET, Key='data/_write_test.txt')
            except Exception:
                pass
        except Exception as e:
            results['data_prefix'] = {'success': False, 'error': str(e)[:300]}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # 测试3: 尝试上传到根路径
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(test_content)
                tmp_path = f.name
            client.upload_file(Bucket=COS_BUCKET, Key='_write_test.txt', LocalFilePath=tmp_path)
            results['root_prefix'] = {'success': True}
            try:
                client.delete_object(Bucket=COS_BUCKET, Key='_write_test.txt')
            except Exception:
                pass
        except Exception as e:
            results['root_prefix'] = {'success': False, 'error': str(e)[:300]}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # 测试4: 读取权限（确认读取正常）
        try:
            client.head_object(Bucket=COS_BUCKET, Key='data/')
            results['read_access'] = {'success': True, 'note': '读取权限正常'}
        except Exception as e:
            results['read_access'] = {'success': False, 'error': str(e)[:200]}

        results['cos_bucket'] = COS_BUCKET
        results['cos_region'] = COS_REGION
        return results

    # ----------------------------------------------------------
    # 本地文件写入
    # ----------------------------------------------------------

    def _write_local(self, record: dict):
        """写入本地 JSONL 文件（线程安全，追加写入）。"""
        date_str = record['timestamp'][:10]  # YYYY-MM-DD
        file_path = os.path.join(LOG_DIR, f'{date_str}.jsonl')

        try:
            with self._lock:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[ConversationLogger] 写入本地日志失败: {e}")

    # ----------------------------------------------------------
    # COS 同步
    # ----------------------------------------------------------

    def _get_cos_client(self):
        """获取 COS 客户端（懒加载）。"""
        if self._cos_client is not None:
            return self._cos_client

        try:
            from qcloud_cos import CosConfig, CosS3Client
            config = CosConfig(Region=COS_REGION, SecretId=COS_SECRET_ID, SecretKey=COS_SECRET_KEY)
            self._cos_client = CosS3Client(config)
            return self._cos_client
        except ImportError:
            print("[ConversationLogger] cos-python-sdk-v5 未安装，COS 同步不可用")
            return None
        except Exception as e:
            print(f"[ConversationLogger] 初始化 COS 客户端失败: {e}")
            return None

    def _schedule_cos_sync(self):
        """去抖调度：3 秒内多次调用只执行最后一次上传。"""
        if not self._cos_enabled:
            return

        # 取消已有的定时器
        if self._sync_timer is not None:
            self._sync_timer.cancel()

        self._sync_timer = threading.Timer(
            self._sync_debounce_seconds,
            self._do_cos_sync_today,
        )
        self._sync_timer.daemon = True
        self._sync_timer.start()

    def _do_cos_sync_today(self):
        """上传当天的日志文件到 COS。"""
        today = datetime.now().strftime('%Y-%m-%d')
        file_path = os.path.join(LOG_DIR, f'{today}.jsonl')

        if not os.path.exists(file_path):
            return

        self._upload_to_cos(file_path, today)

    def _upload_to_cos(self, file_path: str, date: str) -> bool:
        """将指定日期的日志文件上传到 COS。"""
        client = self._get_cos_client()
        if client is None:
            return False

        cos_key = f'{COS_LOG_PREFIX}{date}.jsonl'
        try:
            client.upload_file(
                Bucket=COS_BUCKET,
                Key=cos_key,
                LocalFilePath=file_path,
            )
            print(f"[ConversationLogger] COS 上传成功: {cos_key}")
            return True
        except Exception as e:
            print(f"[ConversationLogger] COS 上传失败 {cos_key}: {e}")
            return False

    def _download_from_cos(self, date: str) -> Optional[str]:
        """从 COS 下载日志文件到本地。"""
        client = self._get_cos_client()
        if client is None:
            return None

        cos_key = f'{COS_LOG_PREFIX}{date}.jsonl'
        file_path = os.path.join(LOG_DIR, f'{date}.jsonl')

        try:
            client.download_file(
                Bucket=COS_BUCKET,
                Key=cos_key,
                DestFilePath=file_path,
            )
            print(f"[ConversationLogger] COS 下载成功: {cos_key} -> {file_path}")
            return file_path
        except Exception as e:
            print(f"[ConversationLogger] COS 下载失败 {cos_key}: {e}")
            return None


# ============================================================
# 模块级单例
# ============================================================
_logger_instance: Optional[ConversationLogger] = None
_logger_lock = threading.Lock()


def get_conversation_logger() -> ConversationLogger:
    """获取全局单例 ConversationLogger（懒加载 + 线程安全）。"""
    global _logger_instance
    if _logger_instance is None:
        with _logger_lock:
            if _logger_instance is None:
                _logger_instance = ConversationLogger()
    return _logger_instance
