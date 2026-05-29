# Backend Reading Map

这份文档只讲后端，目标是帮你快速建立这套后端的脑图。

你读后端时，始终抓住一条主线：

`请求进来 -> 命中哪个 API -> 调哪个 service -> 查哪些存储 -> 返回什么结果`

---

## 1. 后端整体结构

后端大致分 5 层：

1. 入口层
   - `app/main.py`
2. API 层
   - `app/api/auth.py   提供用户注册、登录与鉴权接口`
   - `app/api/chat.py   提供聊天与 RAG 对话接口 `
   - `app/api/documents.py   提供知识文档上传、查询、更新与删除接口`
3. Service 层
   - `app/services/rag_engine.py    编排检索、重排、提示构造与生成的 RAG 主流程`
   - `app/services/document_ingestion.py  处理文档入库、切块与索引写入流程 ` 
   - `app/services/embedding.py    提供文本切块与向量化服务`
   - `app/services/reranker.py   对检索结果进行相关性重排`
   - `app/services/llm_client.py   封装兼容 OpenAI 接口的大模型调用逻辑`
   - `app/services/memory.py   管理会话短期记忆与 Redis 回退逻辑 `
4. 数据访问层
   - `app/database/mysql_client.py   本模块用于管理 MySQL 异步连接、建表与会话工厂`
   - `app/database/milvus_client.py   本模块用于封装 Milvus 连接、写入与混合检索逻辑` 
   - `app/database/models.py   定义项目的 SQLAlchemy 数据模型 `
5. 配置层
   - `app/config.py`

这套代码的关键不是“框架怎么用”，而是后端怎样把三类能力串起来：

- 认证
- 文档入库
- RAG 问答

---

## 2. 先看启动过程

### 文件

- `app/main.py   创建 FastAPI 应用并注册所有接口路由 `
- `app/config.py  项目环境变量与运行配置 `
- `app/database/mysql_client.py 用于管理 MySQL 异步连接、建表与会话工厂`

### 你要看清的点

#### `app/config.py`

这里定义了整个后端依赖的外部资源和参数：

- MySQL
- Redis
- Milvus
- LLM
- embedding / rerank 模型
- chunk 大小
- 检索 top_k
+--
后面你看到任何 service 行为异常，先回来看配置。

#### `app/database/mysql_client.py  用于管理 MySQL 异步连接、建表与会话工厂`

这里做 3 件事：

1. 创建 SQLAlchemy 异步引擎
2. 创建 session factory
3. 启动时自动建表

你可以把它理解成后端里所有 MySQL 会话的总入口。

#### `app/main.py    创建 FastAPI 应用并注册所有接口路由 `

这里做 4 件事：

1. 启动时执行 `lifespan()  封装可复用的异步逻辑`
2. “封装可复用的异步逻辑”中的异步，指的是不阻塞主线程执行、允许程序在等待耗时操作（如网络请求、文件读写、定时器）期间继续执行其他任务的编程模式。
3. 在 `lifespan()` 里初始化数据库
4. 注册 3 个 router
   - `auth`
   - `chat`
   - `documents`
5. 暴露 `/health`

### 启动链路

`uvicorn 启动`
-> `app.main:app`
-> `lifespan()`
-> `mysql_client.init_db()`
-> 注册路由
-> 服务开始接收请求

---

## 3. 后端数据模型

### 文件

- `app/database/models.py`

### 核心表

#### `User`

存用户账号信息：

- 用户名
- 密码 hash
- 邮箱

#### `Role`

存角色配置：

- 角色名
- 角色类型
- personality
- language_style
- constraints
- system_prompt
- knowledge_domains

这是“聊天人格”和“知识域限制”的持久化来源。

#### `Conversation`

存聊天结果：

- user_id
- role_id
- session_id
- 用户消息
- 助手回复
- 检索到的文档片段

这张表的价值是审计和历史回看，不是短期上下文记忆的主来源。

#### `Document`

存文档主信息：

- 标题
- 全文内容
- 文件路径
- 来源类型
- knowledge_domain
- milvus_ids
- chunk_count

注意：文档全文本身是进数据库的。

#### `MilvusIndex`

存文档 chunk 和向量索引的映射：

- doc_id
- milvus_id
- chunk_index
- chunk_text

它的作用不是做向量检索，而是做“本地可回溯映射”和 fallback。

### 你要建立的认识

这套系统的知识数据不是只在 Milvus 里。

它至少分成三份：

1. 磁盘文件
2. `documents` 表全文
3. `milvus_index` 表 chunk 映射
4. Milvus 里的向量和 chunk

---

## 4. 认证后端怎么工作

### 文件

-`app/api/auth.py`

### 主要职责

这个文件只做认证，不做业务。

核心函数：

- `register()`
- `login()`
- `authenticate_user()`
- `create_access_token()`
- `get_current_user()`

### 链路

#### 注册

`POST /api/auth/register`
-> 校验用户名、密码、邮箱
-> 查重
-> 密码 hash
-> 写入 `users`

#### 登录

`POST /api/auth/token`
-> `authenticate_user()`
-> 校验用户名密码
-> `create_access_token()`
-> 返回 JWT
- 'JWT  是一种开放标准（RFC 7519），用于在网络应用环境间安全地传递声明（claims）。它紧凑、自包含、防篡改，常用于身份认证和信息交换'
- 'JWT  由头部、载荷和密钥生成，用于验证消息未被篡改'
#### 鉴权

需要登录的接口会依赖：

`Depends(get_current_user)`

执行过程是：

`Authorization: Bearer token`
-> `jwt.decode(...)`
-> 取出用户名
-> 查 `users`
-> 得到当前用户对象

### 你要注意的点

1. token 里存的是 `sub=username` 和 `uid`
2. 真正鉴权时还是回数据库查用户
3. 认证逻辑和业务逻辑是分开的

---

## 5. 文档入库后端怎么工作

这是第一条核心后端链路。

### API 入口

- `app/api/documents.py`

主要接口：

- `upload_document()`
- `list_documents()`
- `get_document()`
- `delete_document()`
- `update_document()`

这个文件的职责比较薄，核心是：

- 校验当前用户
- 校验文档归属
- 调用 service

真正复杂的逻辑不在这里。

### 核心 service

- `app/services/document_ingestion.py`

最重要的函数：

- `save_document()`
- `index_document()`
- `replace_local_chunks()`
- `upsert_local_file()`

### 文档处理过程

#### 第一步：抽文本

`save_document()`
-> `extract_text(filename, content)`

对应文件：

- `app/services/document_parser.py`

支持的本质是“不同格式 -> 纯文本”。

#### 第二步：保存文档主记录

`save_document()`
会先把原始文件写到：

- `data/documents/...`

然后创建或更新 `Document`。

#### 第三步：切块

`index_document()`
-> `embedding.chunk_text()`

对应文件：

- `app/services/embedding.py`

这里定义了 chunk 的基本规则：

- chunk 长度
- overlap 大小
- 按段落拼接还是切分

#### 第四步：生成向量

`index_document()`
-> `embedding.encode_full(chunks)`

这一步会同时生成：

- dense vector
- sparse vector

#### 第五步：写向量库

`index_document()`
-> `MilvusClient.upsert(...)`

对应文件：

- `app/database/milvus_client.py`

#### 第六步：写本地 chunk 映射

`replace_local_chunks()`
-> 清旧 `MilvusIndex`
-> 重新写新的 chunk 映射

#### 第七步：更新文档元数据

最终更新：

- `document.milvus_ids`
- `document.chunk_count`

### 整条链

`POST /api/documents/upload`
-> `documents.upload_document()`
-> `save_document()`
-> `extract_text()`
-> 写磁盘
-> 写/更新 `Document`
-> `index_document()`
-> `chunk_text()`
-> `encode_full()`
-> `MilvusClient.upsert()`
-> `replace_local_chunks()`
-> 更新 `Document`

### 删除文档时要理解的点

删除不是删一处，而是删三处：

1. `MilvusClient.delete_by_doc_id()`
2. 删除 `MilvusIndex`
3. 删除磁盘文件
4. 删除 `Document`

这也是为什么这个接口不能只删数据库记录。

---

## 6. RAG 问答后端怎么工作

这是整个后端最重要的一条链路。

### API 入口

- `app/api/chat.py`

这个文件做的不是“生成回答”，而是“准备这次对话的约束条件”。

你先看这些内容：

- `ROLE_DEFAULT_PROFILES`
- `build_default_role_config()`
- `build_effective_knowledge_domains()`
- `get_role_config()`
- `get_allowed_doc_ids()`
- `chat()`

### 这层到底干什么

#### 角色配置

角色配置来自两部分：

1. 数据库里的 `Role`
2. 默认角色模板 `ROLE_DEFAULT_PROFILES`

如果数据库没有角色，就走默认配置。

#### 知识域过滤

`build_effective_knowledge_domains()`

决定这次问答允许查哪些 domain，比如：

- `general`
- `medical`
- `legal`

#### 文档权限过滤

`get_allowed_doc_ids()`

按两个条件筛文档：

1. 只能是当前用户自己的文档
2. 只能属于当前角色允许的知识域

所以角色不仅影响 prompt，也影响检索范围。

### RAG 总编排器

- `app/services/rag_engine.py`

核心函数：

- `RAGEngine.chat()`

你可以把它看成“从用户问题到最终回答”的总流程。

### `RAGEngine.chat()` 主流程

#### 1. 取短期记忆

`self.memory.get_recent_messages(...)`

来源：

- `app/services/memory.py`

这是多轮对话上下文的主要来源。

#### 2. 构造检索 query

`_build_search_query(user_message, recent_messages)`

它不是直接拿用户当前一句话去检索，而是会把最近对话拼进去。

#### 3. 生成 query 向量

`self.embedding.encode_dense(...)`
`self.embedding.encode_sparse(...)`

来源：

- `app/services/embedding.py`

#### 4. 做混合检索

`self.milvus.hybrid_search(...)`

来源：

- `app/database/milvus_client.py`

这里会结合：

- dense similarity
- sparse similarity

如果接的是 Milvus，就走真正的 hybrid search。
如果 Milvus 不可用，就走内存 fallback。

#### 5. 必要时本地 fallback 搜索

如果 Milvus 没搜到，而且存在允许文档：

`_local_search(...)`

它会从 MySQL 里的 `MilvusIndex` 或 `Document.content` 重新构造候选片段，再做 rerank。

这个设计很重要，因为它说明：

`Milvus 不是唯一检索来源`

#### 6. 重排

`self.reranker.rerank_with_docs(...)`

来源：

- `app/services/reranker.py`

检索得到的是候选片段，重排后才是最终送进 prompt 的上下文。

#### 7. 构造 prompt

`_build_context(...)`

把两类信息拼起来：

1. 检索结果
2. 最近对话历史

再配上：

- `get_role_prompt(role_config)`

来源：

- `app/prompts/templates.py`

#### 8. 调 LLM

`_generate_response(...)`
-> `LLMClient.chat_with_retry(...)`

来源：

- `app/services/llm_client.py`

#### 9. 写短期记忆

`push_message(...)`
`set_ttl(...)`

#### 10. 返回结果

返回给 API 层：

- response
- retrieved_docs
- session_id

然后 API 层再把结果存进 `Conversation`。

### 整条链

`POST /api/chat/`
-> `api/chat.py::chat()`
-> 计算 role_config
-> 计算 effective_domains
-> 计算 allowed_doc_ids
-> `RAGEngine.chat()`
-> 取 recent_messages
-> 组装 search_query
-> query 向量化
-> hybrid_search
-> rerank
-> 构造 prompt
-> 调 LLM
-> 写短期记忆
-> API 层写 `Conversation`
-> 返回结果

---

## 7. 每个后端 service 的职责边界

### `rag_engine.py`

职责：

- 编排整个 RAG 流程

不负责：

- 用户认证
- 文档所有权校验

### `document_ingestion.py`

职责：

- 文档存盘
- 文档抽取
- chunk
- embedding
- 索引写入

不负责：

- API 权限判断

### `embedding.py`

职责：

- 切块
- 生成 dense / sparse 向量

### `reranker.py`

职责：

- 给候选 chunk 重新排序

### `llm_client.py`

职责：

- 兼容 OpenAI 风格模型接口
- 调模型
- 超时/失败降级

### `memory.py`

职责：

- 管理 session 的短期对话历史

### `milvus_client.py`

职责：

- 向量写入
- 向量删除
- hybrid search

---

## 8. 这套后端的几个 fallback 机制
Fallback（回退 / 降级）机制是一种容错设计，指当系统、服务、组件或操作执行失败时，自动切换到预先定义的备用方案，以保证整体功能可用或降低故障影响。其核心思想是“不把鸡蛋放在一个篮子里”，为每个关键环节准备“B 计划”

理解后端时，不看 fallback 很容易误判系统状态。

### Redis fallback

文件：

- `app/services/memory.py`

如果 Redis 不可用：

- 用进程内 `_memory_store`

### Milvus fallback

文件：

- `app/database/milvus_client.py`

如果 Milvus 或 `pymilvus` 不可用：

- 用进程内 `_memory_store`

### Embedding fallback

文件：

- `app/services/embedding.py`

如果 `FlagEmbedding` 不可用：

- 用 hash 方案构造向量

### Rerank fallback

文件：

- `app/services/reranker.py`

如果 `FlagReranker` 不可用：

- 用 token overlap 算分

### LLM fallback

文件：

- `app/services/llm_client.py`

如果模型服务不可用：

- 用上下文生成一个兜底回答

### 你要形成的判断

这套后端很多时候“能跑”，不代表外部依赖真的都正常。

它可能只是进入了 fallback。

---

## 9. 最推荐的后端阅读顺序

不要按文件夹顺序读，按下面顺序读效率最高：

1. `app/config.py    项目环境变量与运行配置 `
_env_int，_env_float，_env_flag这个三个函数读取环境变量，并转化为int，float，布尔值 bool
config这个类的作用是 统一管理整个项目运行时需要的配置 ，这样在其他文件中，就不需要再次定义，直接调用，就可以了
2. `app/main.py    创建 FastAPI 应用并注册所有接口路由`
lifespan这个函数作用是在 FastAPI 应用启动时执行初始化逻辑
app = FastAPI()  作用是集中列出所有接口路由模块
API_ROUTERS  集中列出所有接口路由模块
app.add_middleware(CORSMiddleware, ...)   允许前端跨域访问后端
app.include_router(...)  把 auth/chat/documents 这些子模块的接口正式挂到主应用上   auth.py 里写的接口，不会自动生效
必须通过 include_router() 挂到 app 上，外部才能访问
3. `app/database/models.py   定义项目的 SQLAlchemy 数据模型`

4. `app/database/mysql_client.py    用于管理 MySQL 异步连接、建表与会话工厂`

5. `app/api/auth.py    提供用户注册、登录与鉴权接口 `

6. `app/api/documents.py   提供知识文档上传、查询、更新与删除接口`

7. `app/services/document_ingestion.py   处理文档入库、切块与索引写入流程`

8. `app/services/embedding.py   提供文本切块与向量化服务`

9. `app/database/milvus_client.py   用于封装 Milvus 连接、写入与混合检索逻辑`

10. `app/api/chat.py   提供聊天与 RAG 对话接口`

11. `app/services/rag_engine.py   编排检索、重排、提示构造与生成的 RAG 主流程`

12. `app/services/reranker.py    对检索结果进行相关性重排`

13. `app/services/memory.py   管理会话短期记忆与 Redis 回退逻辑`

14. `app/services/llm_client.py   封装兼容 OpenAI 接口的大模型调用逻辑`


这个顺序的原则是：

- 先搞清系统怎么启动
- 再搞清数据长什么样
- 再看文档链路
- 最后看最复杂的聊天链路

---

## 10. 最值得你亲手追的 3 个后端问题

### 问题 1

“上传一个 PDF 后，系统具体把数据写到了哪里？”

你要追：

`documents.py`
-> `document_ingestion.py`
-> `embedding.py`
-> `milvus_client.py`
-> `models.py`

### 问题 2

“用户发一条消息时，哪些文档能被检索到？”

你要追：

`api/chat.py`
-> `build_effective_knowledge_domains()`
-> `get_allowed_doc_ids()`
-> `rag_engine.py`

### 问题 3

“如果 Milvus / Redis / LLM 挂了，后端会怎么退化？”

你要追：

- `memory.py`
- `milvus_client.py`
- `embedding.py`
- `reranker.py`
- `llm_client.py`

---

## 11. 一句话抓总

理解这套后端，核心不是记函数名，而是记住两条主业务链：

1. `文档 -> 抽取 -> 切块 -> 向量化 -> 入库`
2. `问题 -> 角色约束 -> 文档过滤 -> 检索 -> 重排 -> 生成`

只要这两条链在你脑子里是通的，后端就基本读通了。
