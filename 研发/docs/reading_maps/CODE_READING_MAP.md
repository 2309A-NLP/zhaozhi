# Code Reading Map

这份文档不是功能说明书，而是这套代码的阅读地图。目标是帮你快速回答三个问题：

1. 系统从哪里启动
2. 一条请求会经过哪些模块
3. 数据最终落到哪里

## 1. 项目本质

这是一套 `FastAPI + Streamlit + RAG` 项目。

- `FastAPI` 负责后端 API、认证、聊天、文档管理
- `Streamlit` 负责登录页和工作台 UI
- `RAG` 负责文档切块、向量化、检索、重排、调用 LLM
- `MySQL` 负责结构化数据
- `Milvus` 负责向量检索
- `Redis` 负责短期对话记忆

你可以把它看成两条主链路：

1. 文档链路
2. 对话链路

---

## 2. 从哪里启动

### 后端入口

看 `app/main.py`

- `lifespan()` 在启动时初始化数据库
- `app = FastAPI(...)` 创建应用
- `include_router(...)` 注册 `auth`、`chat`、`documents`
- `/health` 用于前端探活

先看这里的原因很简单：你会知道系统真实暴露了哪些能力，而不是先陷在实现细节里。

### 配置入口

看 `app/config.py`

重点关注这些配置：

- 数据库: `SQLALCHEMY_URL`
- 向量库: `MILVUS_HOST` / `MILVUS_PORT`
- 大模型: `LLM_BASE_URL` / `LLM_MODEL`
- 检索参数: `CHUNK_SIZE` / `RETRIEVAL_TOP_K` / `RERANK_TOP_K`
- 默认角色: `DEFAULT_ROLE_NAME` / `DEFAULT_ROLE_TYPE`

如果你不先读配置，后面会经常搞不清代码到底在用真实外部服务，还是在走降级逻辑。

---

## 3. 先理解数据长什么样

看 `app/database/models.py`

这 5 个模型最重要：

- `User`: 用户
- `Role`: 角色配置
- `Conversation`: 聊天记录
- `Document`: 文档元数据和全文
- `MilvusIndex`: 文档分块和向量索引的本地映射

建议你先回答下面这几个问题：

- 用户信息存在哪
- 角色是数据库持久化还是前端临时覆盖
- 聊天记录存的是最终答案，还是只存消息
- 文档原文是否进数据库
- 向量 ID 和文档 ID 怎么关联

只要这 5 个表读明白，后面大部分代码都会变得顺手。

---

## 4. 认证链路

认证链路最短，也最适合作为热身。

### 后端

看 `app/api/auth.py`

关键函数：

- `register()` 注册用户
- `login()` 用户名密码换 token
- `create_access_token()` 生成 JWT
- `get_current_user()` 解析 token 并查用户
- `read_users_me()` 返回当前登录用户

### 数据库连接

看 `app/database/mysql_client.py`

关键点：

- `MySQLClient` 创建异步引擎
- `init_db()` 启动时自动建表
- `get_db()` 给各 API 提供 `AsyncSession`

### 前端

看 `app/frontend_shared.py`

关键函数：

- `login()`
- `register_user()`
- `api_request()`

### 一条登录请求怎么走

`Streamlit 表单`
-> `frontend_shared.login()`
-> `POST /api/auth/token`
-> `auth.login()`
-> `authenticate_user()`
-> `create_access_token()`
-> 前端保存 token
-> `GET /api/auth/me`
-> 进入工作台

---

## 5. 文档链路

这是第一条核心主链路。

### 入口

看 `app/api/documents.py`

关键接口：

- `upload_document()`
- `list_documents()`
- `delete_document()`
- `update_document()`

### 真正入库逻辑

看 `app/services/document_ingestion.py`

关键函数：

- `save_document()`
- `index_document()`
- `replace_local_chunks()`
- `upsert_local_file()`

### 文档处理和向量化

看 `app/services/document_parser.py`
看 `app/services/embedding.py`

`embedding.py` 里重点看：

- `chunk_text()`: 怎么切块
- `encode_dense()`: 稠密向量
- `encode_sparse()`: 稀疏向量
- `encode_full()`: 一次同时生成两类向量

### 向量库存取

看 `app/database/milvus_client.py`

重点看：

- `upsert()`
- `hybrid_search()`
- `delete_by_doc_id()`

### 一条上传请求怎么走

`前端上传文件`
-> `frontend_shared.upload_document()`
-> `POST /api/documents/upload`
-> `documents.upload_document()`
-> `document_ingestion.save_document()`
-> `extract_text()` 提取文本
-> `chunk_text()` 切块
-> `encode_full()` 生成向量
-> `MilvusClient.upsert()` 写向量库
-> `replace_local_chunks()` 写 `MilvusIndex`
-> 更新 `Document`

### 数据最终落点

上传一个文档后，数据会同时进入三处：

1. 磁盘文件
   - `data/documents/...`
2. MySQL
   - `documents`
   - `milvus_index`
3. Milvus
   - 向量和分块文本

这条链读懂以后，你会清楚“文档删除为什么不能只删数据库”。

---

## 6. 对话链路

这是第二条核心主链路，也是整个系统最重要的部分。

### API 入口

看 `app/api/chat.py`

先看这些对象和函数：

- `ROLE_DEFAULT_PROFILES`
- `build_default_role_config()`
- `build_effective_knowledge_domains()`
- `get_role_config()`
- `get_allowed_doc_ids()`
- `chat()`

这个文件的职责不是做 RAG，而是组装“这次对话的上下文约束”：

- 当前用户是谁
- 当前角色是谁
- 允许检索哪些知识域
- 允许访问哪些文档

### RAG 主引擎

看 `app/services/rag_engine.py`

最重要的函数就是这些：

- `RAGEngine.chat()`
- `_local_search()`
- `_generate_response()`
- `_build_search_query()`
- `_build_context()`
- `_build_timeout_fallback()`

你可以把 `RAGEngine.chat()` 理解成整套问答流程的总编排器。

### 记忆、重排、大模型

分别看：

- `app/services/memory.py`
- `app/services/reranker.py`
- `app/services/llm_client.py`

职责分别是：

- `MemoryService`: 维护短期多轮对话
- `BGERerankerService`: 对检索结果重排
- `LLMClient`: 调模型，失败时降级到兜底回答

### 一条聊天请求怎么走

`前端发消息`
-> `frontend_shared.send_chat()`
-> `POST /api/chat/`
-> `api/chat.py::chat()`
-> 解析用户、角色、知识域、允许文档
-> `get_rag_engine().chat()`
-> `MemoryService.get_recent_messages()` 取最近对话
-> `_build_search_query()` 组装检索 query
-> `BGEEmbeddingService.encode_dense()` / `encode_sparse()`
-> `MilvusClient.hybrid_search()`
-> `BGERerankerService.rerank_with_docs()`
-> `_build_context()` 组装 prompt
-> `LLMClient.chat_with_retry()`
-> `MemoryService.push_message()` 写短期记忆
-> `Conversation` 持久化到数据库
-> 返回前端

### 这条链要特别注意的 4 个点

1. 角色控制和知识控制在 `api/chat.py`
   - 不是在 `rag_engine.py`

2. 检索失败时不一定直接报错
   - 可能回退到 `_local_search()`

3. LLM 不可用时不一定直接崩
   - `LLMClient` 有降级回答

4. 短期记忆和长期知识分开
   - 短期记忆: `Redis` 或内存回退
   - 长期知识: `Milvus + MySQL`

---

## 7. 前端链路

前端不是这套系统最难的地方，但它决定了你怎么触发后端。

### 登录页

看 `app/streamlit_app.py`

重点看：

- `main()`
- `render_auth_tabs()`
- `render_auth_card()`

这个文件主要负责：

- 登录注册 UI
- 探测后端健康状态
- 登录后跳转工作台

### 工作台

看 `app/pages/1_Workspace.py`

重点看：

- `main()`
- `render_sidebar()`
- `render_role_selector()`
- `render_conversation()`
- `process_prompt()`

`process_prompt()` 是前端聊天总入口。

它会决定：

- 单角色回复还是多角色回复
- 每个角色是否有独立 session
- 同一条消息是否并发发给多个角色

### 前端共享逻辑

看 `app/frontend_shared.py`

这个文件是前端和后端之间的适配层。最常用的函数是：

- `init_state()`
- `api_request()`
- `refresh_documents()`
- `upload_document()`
- `send_chat()`
- `send_multi_role_chat()`

如果你在查“按钮点下去为什么会发这个请求”，通常都要回到这里。

---

## 8. 系统里的降级逻辑

这套代码有一个很重要的阅读习惯：不要只看理想路径，要顺手看降级路径。

主要有这几类：

### 向量化降级

`embedding.py`

- 如果 `FlagEmbedding` 不可用
- 用本地 hash 方案生成 fallback dense / sparse 向量

### 重排降级

`reranker.py`

- 如果 `FlagReranker` 不可用
- 用 token overlap 做 fallback score

### Redis 降级

`memory.py`

- 如果 Redis 连不上
- 退回进程内 `_memory_store`

### Milvus 降级

`milvus_client.py`

- 如果 `pymilvus` 或连接不可用
- 退回进程内 `_memory_store`

### LLM 降级

`llm_client.py`

- 如果 OpenAI SDK 不可用
- 或模型服务不可用
- 返回基于上下文的 fallback answer

如果你调试时发现“系统居然还能回答”，但外部服务明明没起，大概率就是这些降级逻辑在生效。

---

## 9. 最有效的阅读顺序

建议按下面顺序，不要跳：

1. `app/config.py`
2. `app/main.py`
3. `app/database/models.py`
4. `app/api/auth.py`
5. `app/api/documents.py`
6. `app/services/document_ingestion.py`
7. `app/api/chat.py`
8. `app/services/rag_engine.py`
9. `app/services/embedding.py`
10. `app/services/reranker.py`
11. `app/services/memory.py`
12. `app/services/llm_client.py`
13. `app/frontend_shared.py`
14. `app/streamlit_app.py`
15. `app/pages/1_Workspace.py`

这个顺序的原则是：

- 先看系统边界
- 再看数据结构
- 再看文档链路
- 再看聊天链路
- 最后再看前端编排

---

## 10. 最值得你亲手追的 3 条路径

如果你只打算真正追代码 3 次，建议追这 3 条：

### 路径 A: 登录

`streamlit_app.py`
-> `frontend_shared.login()`
-> `api/auth.py::login()`
-> `get_current_user()`

目标：

- 搞懂 token 怎么发、怎么验、怎么存

### 路径 B: 上传 PDF

`frontend_shared.upload_document()`
-> `api/documents.py::upload_document()`
-> `document_ingestion.save_document()`
-> `embedding.encode_full()`
-> `milvus_client.upsert()`

目标：

- 搞懂文档怎样从文件变成可检索知识

### 路径 C: 发一条聊天消息

`pages/1_Workspace.py::process_prompt()`
-> `frontend_shared.send_chat()`
-> `api/chat.py::chat()`
-> `rag_engine.RAGEngine.chat()`
-> `milvus_client.hybrid_search()`
-> `reranker.rerank_with_docs()`
-> `llm_client.chat_with_retry()`

目标：

- 搞懂角色、知识域、记忆、检索、生成怎么串起来

---

## 11. 你后面可以继续看的地方

在主链路读顺以后，再补下面这些：

- `app/prompts/templates.py`
  - 看角色 prompt 怎么拼

- `app/ui_components.py`
  - 看工作台 UI 组件怎么拆

- `import_local_pdf.py`
  - 看离线导入文档的脚本入口

- `init_db.py`
  - 看数据库初始化辅助脚本

- `test_ragas.py`
  - 看 RAG 评估是怎么做的

---

## 12. 一句话总结

如果你读着读着开始迷路，就回到这个顺序：

`请求从哪来 -> 经过哪个 API -> 调了哪个 service -> 查了哪些表/索引 -> 结果返回给谁`

对这套代码，最重要的不是记住每个函数，而是始终抓住这条链。
