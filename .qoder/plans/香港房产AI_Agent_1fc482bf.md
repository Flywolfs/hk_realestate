# 香港房产AI Agent 构建方案

## 项目目录

新建文件夹：`/home/zhangchi/Documents/28hse/hk_property_agent/`

```
hk_property_agent/
├── agent/
│   ├── __init__.py
│   ├── agent_core.py        # LangChain ReAct Agent 主逻辑
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── estate_search.py     # 屋苑查询工具（结构化JSON）
│   │   ├── rent_sale_ratio.py   # 租售比查询工具
│   │   ├── price_trend.py       # 价格趋势查询工具
│   │   └── vector_search.py     # 向量语义检索工具（RAG）
│   └── memory.py            # 对话上下文记忆（ConversationBufferMemory）
├── data/
│   ├── loader.py            # 独立数据加载器（直接读COS，不走现有API）
│   └── vector_store.py      # 向量数据库管理（构建/热更新索引）
├── server/
│   ├── app.py               # Flask 服务，暴露 /api/agent/chat 接口
│   └── wechat_auth.py       # 微信小程序鉴权（复用现有 auth.py 逻辑）
├── scripts/
│   └── weekly_update.py     # 每周热更新脚本（拉取COS数据 → 重建向量索引）
├── .env.example
└── requirements.txt
```

---

## Task 1：数据层设计（data/）

**数据来源**：直接从 COS 对象存储读取，不经过现有 `/api/estates` 接口，避免统计失真。

读取的文件与现有 data_config.py 中相同：
- `estate_static_info_convert.json`（屋苑基础信息、坐标、户型）
- `average_rent_sale_ratio.json`（月度租售比时序）
- `dynamic_estate_data.json`（动态价格数据，来自 centanet 数据）

`data/loader.py` 实现：
- 启动时从 COS 下载数据到本地缓存
- 提供结构化查询函数（按名称、区域、户型等过滤），供 LangChain Tools 调用

**向量数据库方案**（`data/vector_store.py`）：
- 引擎：`Chroma`（轻量，支持持久化，无需独立服务器）或云托管部署 `Qdrant`（容器化，支持远程访问）
- 向量化内容：每个屋苑的文本描述（名称、地区、户型、租售比、价格走势摘要）
- Embedding 模型：`text-embedding-3-small`（OpenAI）或国内模型（如通义千问的 embedding API）
- 用途：处理模糊查询，如"荃湾有哪些租售比低于3%的大型屋苑"

---

## Task 2：Tools 设计（agent/tools/）

每个 Tool 是一个 LangChain `@tool` 装饰函数，Agent 自主决定调用哪个：

| Tool 名称 | 功能 | 输入参数 |
|---|---|---|
| `search_estate_by_name` | 按屋苑名称精确/模糊查询基本信息 | `name: str` |
| `search_estates_by_area` | 按地区（如荃湾、沙田）列出屋苑 | `area: str, limit: int` |
| `get_rent_sale_ratio` | 查询屋苑当前租售比及历史时序 | `estate_id: str` |
| `get_price_trend` | 查询屋苑近N个月成交价走势 | `estate_id: str, months: int` |
| `compare_estates` | 对比多个屋苑的租售比/价格 | `estate_ids: list[str]` |
| `semantic_search` | 向量语义检索（处理描述性问题） | `query: str, top_k: int` |

---

## Task 3：Agent 核心（agent/agent_core.py）

使用 LangChain **ReAct Agent**（`create_react_agent`）：

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory

llm = ChatOpenAI(model="gpt-4o", temperature=0)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True)
```

**System Prompt 要点**：
- 明确 Agent 角色：香港房产信息咨询助手
- 数据范围说明：仅限已收录屋苑（约9000+个）
- 默认回答语言：繁体中文 / 简体中文（按用户输入判断）
- 工具调用策略：优先用结构化工具精确查询，模糊描述时使用 semantic_search

---

## Task 4：服务层（server/app.py）

暴露接口 `POST /api/agent/chat`，供微信小程序调用：

```json
请求: { "message": "沙田有什么租售比比较低的屋苑？", "session_id": "openid_xxx" }
响应: { "reply": "...", "sources": [...], "session_id": "..." }
```

- 鉴权：复用现有 `auth.py` 的 `login_required` 装饰器（微信 openid）
- 多轮对话：以 `session_id`（微信 openid）为 key，维护各用户的独立 `ConversationBufferMemory`
- **不记录 API 请求次数**（独立于现有统计体系，避免污染数据）

---

## Task 5：热更新脚本（scripts/weekly_update.py）

每周定时执行：
1. 从 COS 重新下载最新数据文件
2. 重新构建向量索引（Chroma / Qdrant）
3. 热加载：发送请求到 `/api/agent/reload` 让运行中的服务刷新内存数据

触发方式：微信云托管定时任务，或手动调用激活 API（与现有做法一致）。

---

## Task 6：依赖与环境（requirements.txt）

核心依赖：
```
langchain>=0.3
langchain-openai
langchain-community
chromadb          # 向量数据库（本地方案）
cos-python-sdk-v5 # 腾讯云 COS SDK
flask
flask-cors
```

LLM 选型建议（可配置）：
- 主选：`gpt-4o`（效果最佳）
- 备选：`deepseek-chat`（成本更低，中文支持好，适合香港房产场景）
- Embedding：`text-embedding-3-small` 或 `nomic-embed-text`（本地免费）

---

## 关键设计决策说明

1. **数据独立**：agent 直接读 COS，完全绕过现有 `/api/estates` 接口，现有 API 统计不受影响
2. **向量数据库选型**：优先 Chroma（嵌入式，无需额外容器），若查询量大再迁移 Qdrant
3. **对话记忆**：用内存 dict 按 session_id 存储，不持久化（重启后对话上下文清空，简单可靠）
4. **云托管适配**：整个 agent 服务打包成一个独立 Docker 容器部署到微信云托管，与现有后端容器并行
