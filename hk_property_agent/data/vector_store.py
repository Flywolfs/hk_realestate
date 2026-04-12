"""
向量数据库管理模块
将屋苑信息转换为自然语言文档，构建 Chroma 向量索引，
支持语义检索和每周热更新。
"""

import os
import threading
from typing import List, Optional

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

CHROMA_PERSIST_DIR  = os.environ.get('CHROMA_PERSIST_DIR', '/tmp/agent_chroma_db')
EMBEDDING_PROVIDER  = os.environ.get('EMBEDDING_PROVIDER', 'openai')
EMBEDDING_MODEL     = os.environ.get('EMBEDDING_MODEL', 'text-embedding-3-small')
OPENAI_API_KEY      = os.environ.get('OPENAI_API_KEY', '')
OPENAI_BASE_URL     = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')

# vLLM 本地 embedding 服务配置
# vLLM 以 OpenAI-compatible API 形式暴露 embedding 接口：
#   POST http://<VLLM_HOST>:<VLLM_PORT>/v1/embeddings
VLLM_HOST           = os.environ.get('VLLM_HOST', 'localhost')
VLLM_PORT           = os.environ.get('VLLM_PORT', '8000')
VLLM_EMBEDDING_MODEL = os.environ.get('VLLM_EMBEDDING_MODEL', 'BAAI/bge-m3')
# vLLM 默认不需要真实 API Key，填任意非空字符串即可
VLLM_API_KEY        = os.environ.get('VLLM_API_KEY', 'dummy')

# 向量集合名称
COLLECTION_NAME = 'hk_estates'


def _build_embedding_function():
    """
    根据 EMBEDDING_PROVIDER 构建 embedding 函数。

    支持的 EMBEDDING_PROVIDER 值：
      openai   - OpenAI / 兼容 OpenAI 接口的云端服务
      deepseek - DeepSeek 云端 embedding
      vllm     - 本地 vLLM 服务（兼容 OpenAI /v1/embeddings 接口）
                 启动方式参考 .env.example 中的注释
    """
    if EMBEDDING_PROVIDER == 'openai':
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=OPENAI_API_KEY,
            openai_api_base=OPENAI_BASE_URL,
        )

    elif EMBEDDING_PROVIDER == 'deepseek':
        # DeepSeek 兼容 OpenAI 接口
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=os.environ.get('DEEPSEEK_API_KEY', ''),
            openai_api_base='https://api.deepseek.com/v1',
        )

    elif EMBEDDING_PROVIDER == 'vllm':
        # vLLM 本地部署：以 OpenAI-compatible 模式运行，直接复用 OpenAIEmbeddings
        # vLLM 启动命令示例（在 hk_property_agent 目录下执行）：
        #   vllm serve BAAI/bge-m3 \
        #       --task embedding \
        #       --host 0.0.0.0 --port 8000 \
        #       --max-model-len 8192
        # 若模型需要本地路径，可改为：
        #   vllm serve /path/to/local/model --task embedding ...
        from langchain_openai import OpenAIEmbeddings
        vllm_base_url = f"http://{VLLM_HOST}:{VLLM_PORT}/v1"
        print(f"[Embedding] 使用 vLLM 本地服务: {vllm_base_url}，模型: {VLLM_EMBEDDING_MODEL}")
        return OpenAIEmbeddings(
            model=VLLM_EMBEDDING_MODEL,
            openai_api_key=VLLM_API_KEY,
            openai_api_base=vllm_base_url,
            # vLLM 可能不支持 check_embedding_ctx_length，关闭以避免报错
            check_embedding_ctx_length=False,
        )

    else:
        raise ValueError(
            f"不支持的 EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER}\n"
            f"可选值: openai / deepseek / vllm"
        )


def _estate_to_document(estate_id: str, info: dict, rent_ratio_data: dict, dynamic_data: dict) -> str:
    """
    将屋苑数据转换为自然语言文档字符串，用于向量化。
    包含屋苑名称、地区、租售比、尺价等关键信息，
    便于用户用自然语言描述需求时语义匹配。
    """
    name = info.get('name', '')
    name_en = info.get('name_en', '') or info.get('nameEn', '')
    address = info.get('address', '')
    area = info.get('area', '') or info.get('district', '')
    basic_info = info.get('basic_info', {})
    establish_year = info.get('establish_year') or basic_info.get('establish_year', '')
    primary_school = info.get('primary_school') or basic_info.get('primary_school', '')

    # 租售比
    rent_data = rent_ratio_data.get(estate_id, {})
    latest_ratio = None
    if isinstance(rent_data, dict):
        overall = rent_data.get('overall_ratio', {})
        if isinstance(overall, dict) and overall:
            latest_ratio = list(overall.values())[-1]
    elif isinstance(rent_data, (int, float)):
        latest_ratio = rent_data

    ratio_str = f"{latest_ratio:.2f}%" if latest_ratio is not None else "暂无数据"

    # 当前尺价和面积
    dynamic = dynamic_data.get(estate_id, {})
    price = dynamic.get('current_price_per_sqft')
    price_str = f"{price:.0f}港元/平方呎" if price else "暂无数据"
    min_area = dynamic.get('min_area')
    max_area = dynamic.get('max_area')
    area_str = f"{min_area:.0f}至{max_area:.0f}平方呎" if min_area and max_area else "暂无数据"

    doc = f"""屋苑名称：{name}
英文名称：{name_en}
所在地区：{area}
地址：{address}
建成年份：{establish_year}
校網（小学）：{primary_school}
当前租售比：{ratio_str}
当前尺价：{price_str}
实用面积范围：{area_str}
屋苑编号：{estate_id}"""

    return doc.strip()


class VectorStore:
    """
    基于 Chroma 的屋苑语义检索向量库。
    支持懒加载、热更新，线程安全。
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._vectordb = None
        self._embeddings = None

    def _get_embeddings(self):
        if self._embeddings is None:
            self._embeddings = _build_embedding_function()
        return self._embeddings

    def _get_or_load_db(self):
        """懒加载向量数据库（若持久化目录已有索引，则直接加载）。"""
        if self._vectordb is not None:
            return self._vectordb

        import chromadb
        from langchain_community.vectorstores import Chroma

        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        embeddings = self._get_embeddings()

        self._vectordb = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )
        print(f"[VectorStore] 已加载向量数据库，持久化目录: {CHROMA_PERSIST_DIR}")
        return self._vectordb

    def build_index(self, loader=None):
        """
        构建（或重建）向量索引。
        :param loader: AgentDataLoader 实例，None 时自动获取全局单例。
        """
        from data.loader import get_loader
        if loader is None:
            loader = get_loader()

        from langchain_community.vectorstores import Chroma
        from langchain_core.documents import Document

        print("[VectorStore] 开始构建向量索引...")
        estate_static = loader.estate_static
        rent_ratio = loader.rent_ratio_data
        dynamic = loader.dynamic_estate_data

        if not estate_static:
            print("[VectorStore] 警告: 屋苑数据为空，跳过索引构建")
            return

        docs = []
        metadatas = []
        ids = []

        for estate_id, info in estate_static.items():
            text = _estate_to_document(estate_id, info, rent_ratio, dynamic)
            docs.append(Document(page_content=text, metadata={
                'estate_id': estate_id,
                'name': info.get('name', ''),
                'area': info.get('area', '') or info.get('district', ''),
            }))

        print(f"[VectorStore] 待索引文档数: {len(docs)}")

        embeddings = self._get_embeddings()
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

        # 批量构建，每批 500 条，避免 embedding API 超时
        batch_size = 500
        with self._lock:
            # 清空旧集合后重建
            try:
                import chromadb
                client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
                try:
                    client.delete_collection(COLLECTION_NAME)
                    print("[VectorStore] 已清空旧索引")
                except Exception:
                    pass
            except Exception as e:
                print(f"[VectorStore] 清空旧索引失败（可忽略）: {e}")

            self._vectordb = None  # 强制重新加载

            all_batches = [docs[i:i + batch_size] for i in range(0, len(docs), batch_size)]
            for idx, batch in enumerate(all_batches):
                print(f"[VectorStore] 正在向量化第 {idx + 1}/{len(all_batches)} 批 ({len(batch)} 条)...")
                if idx == 0:
                    self._vectordb = Chroma.from_documents(
                        documents=batch,
                        embedding=embeddings,
                        collection_name=COLLECTION_NAME,
                        persist_directory=CHROMA_PERSIST_DIR,
                    )
                else:
                    self._vectordb.add_documents(batch)

        print(f"[VectorStore] 向量索引构建完成，共 {len(docs)} 条")

    def similarity_search(self, query: str, top_k: int = 5, area_filter: Optional[str] = None) -> List[dict]:
        """
        语义相似度检索。
        :param query: 用户自然语言查询
        :param top_k: 返回结果数
        :param area_filter: 可选地区过滤（在结果中筛选）
        :return: 屋苑信息字典列表
        """
        with self._lock:
            db = self._get_or_load_db()

        if db is None:
            return []

        try:
            # 先多取一些，再按地区过滤
            fetch_k = top_k * 3 if area_filter else top_k
            results = db.similarity_search_with_score(query, k=fetch_k)
        except Exception as e:
            print(f"[VectorStore] 检索失败: {e}")
            return []

        output = []
        for doc, score in results:
            meta = doc.metadata
            if area_filter and area_filter not in meta.get('area', ''):
                continue
            output.append({
                'estate_id': meta.get('estate_id', ''),
                'name': meta.get('name', ''),
                'area': meta.get('area', ''),
                'score': round(1 - score, 4),  # Chroma 返回 L2 距离，转为相似度
                'content': doc.page_content,
            })
            if len(output) >= top_k:
                break

        return output

    def is_ready(self) -> bool:
        """检查向量索引是否已构建（持久化目录非空）。"""
        if not os.path.exists(CHROMA_PERSIST_DIR):
            return False
        try:
            import chromadb
            client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
            col = client.get_collection(COLLECTION_NAME)
            return col.count() > 0
        except Exception:
            return False


# 模块级单例
_vector_store_instance: Optional[VectorStore] = None
_vs_lock = threading.Lock()


def get_vector_store() -> VectorStore:
    """获取全局单例 VectorStore（懒加载 + 线程安全）。"""
    global _vector_store_instance
    if _vector_store_instance is None:
        with _vs_lock:
            if _vector_store_instance is None:
                _vector_store_instance = VectorStore()
    return _vector_store_instance
