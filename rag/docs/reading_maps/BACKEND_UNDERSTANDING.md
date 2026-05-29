# 后端理解笔记

这份文档只讲后端，不解释前端。

目标不是背文件名，而是建立一张稳定的脑图：

`请求进来 -> 进入哪个 API -> 调哪个 service -> 查哪些数据 -> 返回什么结果`

---

## 1. 先把后端分层看清

这个项目的后端核心在 `app/` 下，大致可以分成 5 层。

### 1. 入口层

- `app/main.py`

作用：

- 创建 `FastAPI` 应用
- 注册路由
- 启动时初始化数据库

你可以把它理解成后端总入口。

---

### 2. API 层

- `app/api/auth.py`
- `app/api/chat.py`
- `app/api/documents.py`
- `app/api/roles.py`

作用：

- 接收 HTTP 请求
- 解析参数
- 做认证依赖注入
- 调用 service
- 把结果返回给前端

API 层通常不放重业务逻辑，它更像“路由分发层”。

---

### 3. Service 层

关键文件：

- `app/services/auth_service.py`
- `app/services/chat_service.py`
- `app/services/rag_engine.py`
- `app/services/document_service.py`
- `app/services/document_ingestion.py`
- `app/services/offline_import_service.py`

作用：

- 处理真正的业务逻辑
- 编排多个下层组件

这是你理解后端时最值得花时间的一层。

---

### 4. 数据访问层

关键文件：

- `app/database/mysql_client.py`
- `app/database/models.py`
- `app/database/milvus_client.py`
- `app/repositories/*.py`

作用：

- 定义数据库表
- 创建数据库连接和会话
- 封装对 MySQL / Milvus 的读写

---

### 5. 配置层

- `app/config.py`

作用：

- 统一管理环境变量
- 管理数据库、Redis、Milvus、LLM、Embedding、Rerank 的配置

很多“为什么行为不对”的问题，最后都要回到这里看配置。

---

## 2. 后端是怎么启动的

看 `app/main.py`。

核心顺序是：

1. 创建 `FastAPI` 应用
2. 通过 `lifespan()` 在启动时执行初始化
3. 调用 `mysql_client.init_db()`
4. 注册各个路由
5. 提供 `/health`

所以启动链路可以理解成：

`uvicorn -> app.main:app -> lifespan() -> init_db() -> 注册路由 -> 开始接请求`

这里最重要的点是：

- 应用启动时会先准备数据库
- 所有 API 最终都被挂到这一个 `app` 上

---

## 3. 数据模型在存什么

看 `app/database/models.py`。

### `User`

存用户账号信息：

- `username`
- `password_hash`
- `email`

---

### `Role`

存角色配置：

- `role_name`
- `role_type`
- `personality`
- `language_style`
- `constraints`
- `system_prompt`
- `knowledge_domains`
- `is_public`

这张表决定“这个角色怎么说话、能用哪些知识域”。

---

### `Conversation`

存聊天记录：

- `user_id`
- `role_id`
- `session_id`
- `message`
- `response`
- `retrieved_docs`

这更像持久化历史记录，不是短期记忆的唯一来源。

---

### `Document`

存文档主信息：

- `title`
- `content`
- `file_path`
- `source`
- `knowledge_domain`
- `user_id`
- `milvus_ids`
- `chunk_count`

注意：

- 文档原文不仅在磁盘上
- 也会存到数据库的 `content`

---

### `MilvusIndex`

存本地 chunk 映射：

- `doc_id`
- `milvus_id`
- `chunk_index`
- `chunk_text`

它的意义不是替代 Milvus，而是给本地回查和 fallback 提供基础。

---

## 4. 一个请求是怎么拿到当前用户的

先看：

- `app/api/auth.py`
- `app/dependencies/auth.py`
- `app/services/auth_service.py`

### 登录链路

`POST /api/auth/token`

流程：

1. API 接收用户名密码
2. `AuthService.login()` 调用 `authenticate()`
3. 校验密码
4. 生成 JWT token
5. 返回 token

---

### 认证链路

很多受保护接口都会依赖：

`Depends(get_current_user)`

实际流程：

1. 从请求头拿 `Bearer token`
2. `get_current_user()` 调 `AuthService.get_current_user_from_token()`
3. 解析 token
4. 再去数据库查用户
5. 把 `current_user` 注入给接口函数

所以你要记住：

- token 只是入口
- 真正的用户对象还是从数据库查出来的

---

## 5. 文档上传这条后端链路

这是第一条核心业务链。

先看：

- `app/api/documents.py`
- `app/services/document_service.py`
- `app/services/document_ingestion.py`
- `app/services/document_parser.py`
- `app/services/embedding.py`
- `app/database/milvus_client.py`

---

### API 层做什么

`app/api/documents.py` 只做几件事：

- 接收上传文件
- 要求当前用户已登录
- 调用 `DocumentService`

它不负责切块、不负责向量化、不负责入库编排。

---

### `DocumentService` 做什么

`app/services/document_service.py` 负责：

- 权限校验
- 读取上传文件内容
- 调用 `save_document()`
- 删除时清理数据库、Milvus、磁盘文件

它是“文档业务入口”，但真正的入库细节在 `document_ingestion.py`。

---

### `save_document()` 做什么

`app/services/document_ingestion.py` 里的 `save_document()` 是文档入库主函数。

它的流程是：

1. `extract_text(filename, content)` 抽取文本
2. 把原始文件写入 `data/documents/`
3. 创建或更新 `Document`
4. 调 `index_document(document)`
5. 调 `replace_local_chunks(...)`
6. 更新 `milvus_ids` 和 `chunk_count`
7. 提交数据库事务

---

### `index_document()` 做什么

这是文档索引化的核心。

流程：

1. `embedding.chunk_text()` 把全文切成多个 chunk
2. `embedding.encode_full(chunks)` 生成向量
3. `milvus.upsert(...)` 把 chunk 和向量写入 Milvus
4. 返回 `chunks` 和 `milvus_ids`

如果 Milvus 失败，它也会尽量保留本地 chunk 结果，不会整条链完全崩掉。

---

### 删除文档时删什么

删除不是删一个地方，而是删多处：

1. Milvus 中的向量
2. `MilvusIndex` 本地映射
3. 磁盘上的原文件
4. `Document` 记录

这也是为什么后端不能只删一条数据库记录。

---

## 6. 聊天问答这条后端链路

这是第二条核心业务链，也是最重要的一条。

先看：

- `app/api/chat.py`
- `app/services/chat_service.py`
- `app/services/rag_engine.py`
- `app/services/memory.py`
- `app/services/reranker.py`
- `app/services/llm_client.py`

---

### API 层做什么

`app/api/chat.py` 很薄。

它主要做两件事：

1. 通过依赖拿到 `db` 和 `current_user`
2. 调 `ChatService(db, get_rag_engine()).chat(...)`

所以聊天接口真正的主逻辑，不在 API 文件里。

---

### `ChatService` 做什么

`app/services/chat_service.py` 更像聊天业务总调度器。

它负责：

1. 生成或接收 `session_id`
2. 根据 `role_id` 取角色配置
3. 合成最终 `role_config`
4. 计算可用的 `knowledge_domains`
5. 计算当前用户允许检索的 `allowed_doc_ids`
6. 调 `rag_engine.chat(...)`
7. 把结果写入 `Conversation`

这层非常关键，因为它把“角色限制”和“文档权限”放在真正 RAG 检索之前。

---

### `RAGEngine` 做什么

`app/services/rag_engine.py` 是从“用户问题”到“模型回答”的主编排器。

你可以把它当成后端里最核心的类。

它的 `chat()` 流程大致是：

1. 从 `memory` 取最近对话
2. 构造检索 query
3. 把 query 编码成 dense / sparse 向量
4. 调 `milvus.hybrid_search(...)`
5. 如果没搜到，再做 `_local_search(...)`
6. 调 `reranker.rerank_with_docs(...)`
7. 拼上下文和 prompt
8. 调 `llm.chat_with_retry(...)`
9. 把本轮对话写回 memory
10. 返回响应结果

---

### 为什么要先算 `allowed_doc_ids`

这是理解后端权限的重要点。

不是所有文档都能被检索。

`ChatService` 会先根据：

- 当前用户
- 当前角色允许的知识域

筛出允许检索的文档 ID。

然后 `RAGEngine` 检索时只在这些文档范围内查。

所以这个系统不是“用户一问，直接在全库搜”，而是“先做权限和域过滤，再检索”。

---

### `_local_search()` 是干什么的

这是 fallback 机制的一部分。

当 Milvus 检索失败或者没结果时，`RAGEngine` 不一定直接放弃，而是：

1. 先从 `MilvusIndex` 取本地 chunk
2. 如果还不够，再从 `Document.content` 临时切块
3. 再用 reranker 选出更相关的内容

所以你要形成一个认知：

- Milvus 不是唯一检索来源
- MySQL 里的文本和 chunk 映射也是兜底来源

---

### 记忆和历史记录不是一回事

`RAGEngine` 里会用 `MemoryService` 取最近消息。

这部分更像“短期上下文记忆”。

而 `Conversation` 表更像“长期持久化聊天记录”。

不要把这两者混成一个概念。

---

## 7. 你当前打开的 `import_local_pdf.py` 在后端里属于什么

这是一个离线导入入口，不走前端页面，也不走 HTTP 上传接口。

它的作用是：

1. 从命令行接收 PDF 路径
2. 初始化数据库
3. 创建数据库 session
4. 调 `OfflineImportService.import_file(...)`
5. 最终复用 `upsert_local_file(...)`
6. 再进入 `save_document(...)` 那套正式入库流程

也就是说：

`import_local_pdf.py` 不是另起炉灶的一套逻辑，
而是“绕过 API，直接复用后端 service”。

它的链路可以理解成：

`命令行 -> OfflineImportService -> upsert_local_file() -> save_document() -> index_document()`

这个文件非常适合理解后端，因为它把“文档入库主链路”暴露得很直接。

---

## 8. 读后端时最值得抓的两条主链

### 主链 1：文档入库

`文件 -> 抽文本 -> 保存原文件 -> 保存 Document -> 切 chunk -> 向量化 -> 写入 Milvus -> 写本地 chunk 映射`

对应文件：

- `app/api/documents.py`
- `app/services/document_service.py`
- `app/services/document_ingestion.py`

---

### 主链 2：聊天问答

`问题 -> 角色配置 -> 文档权限过滤 -> 检索 -> fallback 检索 -> rerank -> 拼 prompt -> 调 LLM -> 写 memory -> 落库 Conversation`

对应文件：

- `app/api/chat.py`
- `app/services/chat_service.py`
- `app/services/rag_engine.py`

---

## 9. 推荐你的阅读顺序

按下面顺序读，理解会最快：

1. `app/config.py    项目环境变量与运行配置`
2. `app/main.py   创建 FastAPI 应用，注册 API 路由，并托管静态前端页面`
3. `app/database/models.py   应用程序的 SQLAlchemy 模型`
4. `app/database/mysql_client.py  异步数据库客户端、模式初始化与会话工厂`
5. `app/api/auth.py   认证 API 层`
6. `app/services/auth_service.py   认证应用服务（或 身份验证应用服务）` 
7. `app/api/documents.py   文档 API 层`
8. `app/services/document_service.py   文档应用服务`
9. `app/services/document_ingestion.py   处理文档入库、切块与索引写入流程`
10. `app/api/chat.py   聊天 API 层`
11. `app/services/chat_service.py   聊天应用服务`
12. `app/services/rag_engine.py   编排检索、重排、提示构造与生成的 RAG 主流程`
13. `import_local_pdf.py  将本地 PDF 文件导入知识库`

这个顺序的原则是：

- 先看系统怎么启动
- 再看数据长什么样
- 再看简单链路
- 最后看最复杂的 RAG 主流程


---

## 10. 你读这套后端时要反复问自己的问题

### 问题 1

上传一个 PDF 后，数据到底写到了哪里？

你应该追：

`documents API -> DocumentService -> save_document -> index_document -> Milvus / MySQL / 磁盘`

---

### 问题 2

用户发一条消息时，系统到底允许检索哪些文档？

你应该追：

`chat API -> ChatService -> knowledge_domains -> allowed_doc_ids -> RAGEngine`

---

### 问题 3

如果 Milvus 或 LLM 出问题，系统会怎么退化？

你应该追：

- `rag_engine.py`
- `memory.py`
- `milvus_client.py`
- `reranker.py`
- `llm_client.py`

---

## 11. 一句话总结

理解这套后端，关键不是记住所有函数，而是把两条链路打通：

1. `文档 -> 入库 -> 切块 -> 建索引`
2. `问题 -> 过滤 -> 检索 -> 重排 -> 生成`

只要这两条链在你脑子里是通的，这个项目的后端就基本读通了。
