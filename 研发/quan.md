# 项目代码说明书

## 1. 文档目标

这份文档不是再做一版泛泛的项目总结，而是直接回答两个问题：

1. 这个项目每一层里有哪些 Python 文件，它们分别做什么
2. 每个 Python 文件里的每个函数、每个方法分别做什么

为了便于阅读，下面按层拆解：

```text
项目
├─ 根目录脚本层
├─ 应用入口层
├─ API 接口层
├─ 依赖注入层
├─ Schema 数据模型层
├─ Core 核心配置层
├─ Service 业务服务层
├─ Repository 数据访问层
├─ Database 基础设施层
├─ Prompt 提示词层
├─ Streamlit 前端层
└─ 包标记文件
```

---

## 2. 根目录脚本层

## 2.1 `import_local_pdf.py`

作用：本地离线导入 PDF 到知识库的命令行脚本。

### 函数说明

`build_parser()`
- 创建命令行参数解析器
- 定义 `paths`、`--user-id`、`--knowledge-domain` 参数

`resolve_paths(raw_paths)`
- 解析命令行里传入的 PDF 路径
- 如果没有显式传路径，就扫描当前目录和 `assets/reference_docs/`
- 过滤出真实存在的 PDF 文件

`import_files(paths, user_id, knowledge_domain)`
- 初始化数据库
- 创建数据库会话
- 实例化 `OfflineImportService`
- 逐个调用导入服务，将文件写入知识库

`main()`
- 脚本主入口
- 负责参数解析、路径解析和异步导入启动

---

## 2.2 `init_db.py`

作用：初始化数据库表结构的脚本。

### 函数说明

`init_database()`
- 调用 `mysql_client.init_db()`
- 初始化数据库 schema
- 完成后关闭数据库连接

---

## 2.3 `test_ragas.py`

作用：调用聊天接口并使用 RAGAS 评估回答质量。

### 函数说明

`prepare_test_dataset()`
- 构造测试问题
- 调用 `/api/chat/` 接口拿回答和检索上下文
- 把问题、答案、上下文、参考答案组装为 `Dataset`

`run_ragas_evaluation()`
- 调用 `prepare_test_dataset()`
- 使用 `evaluate()` 执行 RAGAS 指标计算
- 输出 `context_precision`、`context_recall`、`faithfulness`、`answer_relevancy`

---

## 3. 应用入口层

## 3.1 `app/main.py`

作用：FastAPI 主入口，负责启动应用、注册路由、初始化数据库、托管静态前端。

### 函数说明

`lifespan(_)`
- FastAPI 生命周期函数
- 应用启动时初始化数据库

`root()`
- 根路径处理函数
- 若 `frontend/index.html` 存在，就直接返回前端首页
- 否则返回 API 基本信息

`health()`
- 健康检查接口
- 返回系统状态、应用名、版本号

---

## 3.2 `app/config.py`

作用：集中管理环境变量、系统参数、模型参数、数据库参数和目录参数。

### 顶层函数说明

`_env_int(name, default)`
- 从环境变量读取整数值

`_env_float(name, default)`
- 从环境变量读取浮点值

`_env_flag(name, default="0")`
- 从环境变量读取布尔开关
- 约定字符串 `"1"` 表示开启

### 类说明

`Config`
- 项目的全局配置容器

### `Config` 方法说明

`SQLALCHEMY_URL`
- 动态构造 SQLAlchemy 连接字符串
- 若设置了 `DATABASE_URL`，优先使用它
- 否则拼出 MySQL 连接地址

`ensure_directories()`
- 确保 `DATA_DIR` 和 `DOCUMENTS_DIR` 目录存在

---

## 4. API 接口层 `app/api/`

这一层负责定义 HTTP 接口，不直接承载复杂业务，只负责接请求、调服务、回响应。

## 4.1 `app/api/auth.py`

作用：认证接口。

### 函数说明

`register(user_data, db)`
- 注册用户
- 调用 `AuthService.register_user()`

`login(form_data, db)`
- 登录接口
- 接收表单中的用户名和密码
- 调用 `AuthService.login()`
- 返回访问令牌

`read_users_me(current_user)`
- 获取当前登录用户信息

---

## 4.2 `app/api/chat.py`

作用：聊天接口入口。

### 函数说明

`get_rag_engine()`
- 懒加载 `RAGEngine`
- 全局只初始化一次，避免重复加载嵌入器、重排器和 LLM 客户端

`chat(request, db, current_user)`
- 聊天接口主函数
- 调用 `ChatService.chat()`
- 把 `PermissionError` 转换成 HTTP 403

---

## 4.3 `app/api/documents.py`

作用：知识文档接口。

### 函数说明

`upload_document(file, knowledge_domain, db, current_user)`
- 上传文档并入库

`list_documents(db, current_user)`
- 获取当前用户的文档列表

`get_document(doc_id, db, current_user)`
- 获取某个文档详情

`delete_document(doc_id, db, current_user)`
- 删除指定文档

`update_document(doc_id, file, knowledge_domain, db, current_user)`
- 更新文档内容并重新入库

---

## 4.4 `app/api/roles.py`

作用：角色管理接口。

### 函数说明

`create_role(role_data, current_user, db)`
- 创建角色

`list_roles(current_user, db, include_public=True)`
- 获取角色列表
- 可包含公开角色

`get_role(role_id, db)`
- 获取单个角色详情

`update_role(role_id, role_data, current_user, db)`
- 更新角色配置

`delete_role(role_id, current_user, db)`
- 删除角色

---

## 4.5 `app/api/__init__.py`

作用：把 `api` 目录标记为 Python 包。  
无业务函数。

---

## 5. 依赖注入层 `app/dependencies/`

## 5.1 `app/dependencies/auth.py`

作用：定义鉴权依赖，让受保护接口可以拿到当前登录用户。

### 函数说明

`get_current_user(token, db)`
- 从 Bearer Token 中解析出当前用户
- 内部调用 `AuthService.get_current_user_from_token()`

---

## 5.2 `app/dependencies/__init__.py`

作用：包标记文件。  
无业务函数。

---

## 6. Schema 数据模型层 `app/schemas/`

这一层主要定义：

- 请求体结构
- 响应体结构
- 参数校验规则
- 认证辅助函数

## 6.1 `app/schemas/auth.py`

作用：认证相关数据模型和辅助函数。

### 类说明

`Token`
- 登录成功后的返回模型
- 包含 `access_token` 和 `token_type`

`TokenPayload`
- JWT 解码后的载荷结构

`UserCreate`
- 注册请求体
- 内含用户名、密码、邮箱的校验规则

`UserOut`
- 用户输出结构

### 顶层函数说明

`normalize_username(username)`
- 清理用户名字符串

`normalize_optional_text(value)`
- 规范化可选文本
- 空字符串转为 `None`

`build_auth_exception(detail="无效的认证凭证")`
- 构造统一的 401 认证异常

`verify_password(plain_password, hashed_password)`
- 校验明文密码是否和数据库中的哈希匹配

`get_password_hash(password)`
- 生成密码哈希

`create_access_token(data, expires_delta=None)`
- 创建 JWT 访问令牌

`decode_access_token(token)`
- 解码 JWT
- 校验 token 类型是否为 `access`

### `UserCreate` 校验器说明

`validate_username(cls, value)`
- 校验用户名长度和空格

`validate_password(cls, value)`
- 校验密码长度

`validate_email(cls, value)`
- 校验邮箱格式

---

## 6.2 `app/schemas/chat.py`

作用：聊天请求和响应的数据结构定义。

### 类说明

`RoleConfigOverride`
- 聊天时动态覆盖角色配置的模型

`ChatRequest`
- 聊天请求体
- 包含角色 ID、会话 ID、消息内容、角色覆盖配置

`RetrievedDoc`
- 检索到的文档片段结构

`ChatResponse`
- 聊天响应结构
- 包含回答文本、会话 ID、检索片段数量、检索片段列表

---

## 6.3 `app/schemas/document.py`

作用：文档输出结构定义。

### 类说明

`DocumentOut`
- 文档对外响应模型
- 包含文档 ID、标题、知识域、用户 ID、chunk 数量、来源、创建时间

---

## 6.4 `app/schemas/role.py`

作用：角色输入输出结构定义。

### 类说明

`RoleCreate`
- 创建/更新角色时使用的请求体

`RoleOut`
- 角色响应体

---

## 6.5 `app/schemas/__init__.py`

作用：把 `schemas` 标记为包。  
无业务函数。

---

## 7. Core 核心配置层 `app/core/`

## 7.1 `app/core/role_defaults.py`

作用：定义默认角色画像和默认知识域，并提供角色配置构造函数。

### 函数说明

`get_role_profile(role_type)`
- 根据角色类型获取默认画像

`build_default_role_config(role_id, default_role_name, default_role_type)`
- 构造默认角色配置字典
- 在用户未指定完整角色信息时兜底使用

`build_effective_knowledge_domains(role_config, default_role_type)`
- 计算最终生效的知识域列表
- 若角色配置里没有显式知识域，就退回到默认知识域

---

## 8. Service 业务服务层 `app/services/`

这一层是项目最核心的部分。

---

## 8.1 `app/services/auth_service.py`

作用：处理注册、登录、令牌解析等认证业务。

### 类说明

`AuthService`
- 认证业务服务

### 方法说明

`__init__(db)`
- 初始化仓储依赖

`register_user(user_data)`
- 注册用户
- 检查用户名是否重复
- 写入用户表
- 创建默认角色

`authenticate(username, password)`
- 校验用户名和密码
- 成功返回用户对象
- 失败返回 `None`

`login(username, password)`
- 执行登录逻辑
- 成功返回 JWT

`get_current_user_from_token(token)`
- 把 token 解码为用户对象

---

## 8.2 `app/services/role_service.py`

作用：处理角色创建、更新、删除、查询等业务。

### 顶层函数说明

`normalize_role_type(role_type)`
- 校验并规范化角色类型

`serialize_role(role)`
- 把 ORM 角色对象转换成 `RoleOut`

`ensure_role_owner(role, current_user, detail)`
- 校验角色归属权

`apply_role_data(role, role_data, role_type)`
- 把请求体里的角色配置写回角色实体

### 类说明

`RoleService`
- 角色业务服务

### 方法说明

`__init__(db)`
- 初始化角色仓储

`create_role(role_data, current_user)`
- 创建角色
- 限制每个用户最多 10 个角色

`list_roles(current_user, include_public)`
- 获取当前用户的角色列表
- 同时确保默认角色存在

`get_role(role_id)`
- 获取单个角色

`update_role(role_id, role_data, current_user)`
- 更新角色

`delete_role(role_id, current_user)`
- 删除角色

---

## 8.3 `app/services/default_role_service.py`

作用：确保每个用户都自动拥有内置默认角色。

### 函数说明

`ensure_user_default_roles(db, user_id)`
- 查询当前用户已有角色类型
- 找出缺失的默认角色
- 批量创建默认角色

---

## 8.4 `app/services/document_service.py`

作用：文档模块业务入口，负责文档列表、详情、上传、更新、删除。

### 顶层函数说明

`serialize_document(document)`
- 把文档 ORM 对象转成 `DocumentOut`

`ensure_document_access(document, current_user)`
- 校验当前用户是否有权访问该文档

`read_uploaded_content(file)`
- 读取上传文件内容
- 防止空文件上传

`remove_file_if_exists(file_path)`
- 删除本地磁盘上的原始文件

### 类说明

`DocumentService`
- 文档业务服务

### 方法说明

`__init__(db)`
- 初始化文档仓储

`list_documents(current_user)`
- 获取当前用户所有文档

`get_document(doc_id, current_user)`
- 获取文档详情

`upload_document(file, knowledge_domain, current_user)`
- 读取上传文件
- 调用 `save_document()` 完成正式入库

`update_document(doc_id, file, knowledge_domain, current_user)`
- 更新文档内容
- 重新执行文档入库链路

`delete_document(doc_id, current_user)`
- 删除 Milvus 中的索引
- 删除本地 chunk 映射
- 删除原始文件
- 删除文档元数据

---

## 8.5 `app/services/document_parser.py`

作用：将上传文件解析为纯文本。

### 函数说明

`_require_dependency(value, message)`
- 检查依赖是否可用
- 缺失时抛出清晰错误

`_get_ocr_engine()`
- 懒加载 PaddleOCR 引擎

`_extract_pdf_text(content)`
- 优先用 `pypdf` 抽取 PDF 文本
- 如果抽不出来，再回退到 OCR

`_extract_pdf_text_by_ocr(content)`
- 把 PDF 页面转成图片
- 对页面执行 OCR
- 拼接识别到的文本

`_extract_docx_text(content)`
- 解析 Word 文档文本

`extract_text(filename, content)`
- 根据文件后缀路由到不同解析器
- 当前支持 `txt/md/csv/json/log/pdf/docx`

---

## 8.6 `app/services/document_ingestion.py`

作用：文档入库主链路，负责原始文件保存、文本切块、向量化、Milvus 写入和本地索引映射。

### 顶层函数说明

`get_embedding()`
- 获取全局单例嵌入服务

`get_milvus()`
- 获取全局单例 Milvus 客户端

`build_saved_path(user_id, filename)`
- 生成文档保存路径

`_get_document_source(filename)`
- 根据文件后缀推断文档来源类型

`_build_milvus_payload(document, chunks, dense_vecs, sparse_vecs)`
- 把 chunk 和向量结果组装成 Milvus upsert 所需结构

`replace_local_chunks(db, document, chunks, milvus_ids)`
- 删除旧的本地 chunk 映射
- 写入最新的 `MilvusIndex`

`index_document(document)`
- 对文档内容切块
- 生成 dense / sparse 向量
- 先清理该文档旧的 Milvus 数据
- 再写入新的 Milvus 数据

`save_document(db, user_id, filename, content, knowledge_domain, existing_document=None)`
- 文档正式入库主函数
- 解析文本
- 保存原始文件
- 创建或更新 `Document`
- 做向量入库
- 做本地 chunk 映射
- 更新 chunk 数量和 milvus_ids

`upsert_local_file(db, file_path, user_id, knowledge_domain)`
- 把本地已有文件作为文档导入
- 若同名文档已存在，则走更新逻辑

---

## 8.7 `app/services/offline_import_service.py`

作用：离线导入服务，复用正式入库链路。

### 类说明

`OfflineImportService`
- 本地文件导入服务

### 方法说明

`__init__(db)`
- 保存数据库会话

`import_file(file_path, user_id, knowledge_domain)`
- 调用 `upsert_local_file()`
- 把本地文件导入知识库

---

## 8.8 `app/services/chat_service.py`

作用：聊天业务总调度，负责角色配置、文档权限、调用 RAG 引擎、落会话记录。

### 顶层函数说明

`apply_role_response_rules(role_config, response)`
- 给最终回答应用角色响应规则
- 当前实现是占位逻辑，直接返回原回答

### 类说明

`ChatService`
- 聊天业务服务

### 方法说明

`__init__(db, rag_engine)`
- 初始化角色仓储、文档仓储、会话仓储和 RAG 引擎

`_get_role_config(role_id, user_id)`
- 根据角色 ID 获取最终角色基础配置
- 校验角色是否存在、是否有权限使用
- 把数据库中的角色字段覆盖到默认角色画像上

`chat(request, current_user)`
- 生成或沿用 `session_id`
- 获取角色配置
- 合并 `role_config_override`
- 计算最终知识域
- 查询允许访问的文档 ID
- 调用 `rag_engine.chat()`
- 保存对话到 `conversations`
- 异步把对话沉淀到会话向量存储
- 组装 `ChatResponse`

---

## 8.9 `app/services/rag_engine.py`

作用：RAG 核心引擎，负责检索、重排、上下文构造和大模型生成。

### 类说明

`RAGEngine`
- 系统中的核心问答引擎

### 方法说明

`__init__(current_config)`
- 初始化 embedding、reranker、milvus、memory、llm 客户端

`chat(user_id, role_id, session_id, role_config, user_message, db, allowed_doc_ids=None)`
- 完整执行一次 RAG 问答流程
- 读取最近会话记忆
- 构造检索 query
- 检索知识
- 重排
- 构造模型消息
- 生成回答
- 写回记忆

`_retrieve_documents(db, search_query, role_config, allowed_doc_ids)`
- 做混合检索
- 优先走 Milvus
- 失败时回退到本地检索

`_rerank_documents(user_message, docs)`
- 用重排器对候选文档按相关性精排

`_build_messages(role_config, user_message, docs, recent_messages)`
- 构造发给 LLM 的消息列表

`_build_doc_candidate(doc_id, text, knowledge_domain)`
- 生成统一格式的候选文档字典

`_history_lines(recent_messages, limit)`
- 把最近消息转换成“用户/助手”文本行

`_build_search_query(user_message, recent_messages)`
- 把历史消息与当前问题拼成检索查询串

`_build_context(docs, recent_messages)`
- 把检索知识和对话历史拼成上下文文本

`_local_search(db, allowed_doc_ids, top_k)`
- 本地数据库检索回退逻辑
- 优先查 `MilvusIndex.chunk_text`
- 没有就从 `Document.content` 动态切块

`_generate_response(messages, user_message, reranked_docs)`
- 调用 LLM 生成回答
- 带超时和异常保护

`_build_timeout_fallback(user_message, docs)`
- LLM 超时或失败时，构造降级回答

---

## 8.10 `app/services/embedding.py`

作用：负责文本切块、dense 编码、sparse 编码。

### 类说明

`BGEEmbeddingService`
- 项目统一的嵌入服务

### 方法说明

`__init__(model_name="BAAI/bge-m3", dim=None)`
- 初始化模型名、维度和后端状态

`_tokenize(text)`
- 用正则把中文和英文数字切成 token

`_normalize(vector)`
- 对向量做归一化

`_looks_like_sentence_transformer_model(model_name)`
- 判断模型是否更像 `SentenceTransformer` 格式

`_prepare_texts(texts, is_query)`
- 查询文本时自动加查询指令前缀

`_fit_dense_dim(vectors)`
- 把 dense 向量裁剪或补齐到目标维度

`_ensure_model()`
- 按优先顺序尝试加载真实嵌入模型
- 不可用时保留 fallback 模式

`_fallback_dense(texts)`
- 无真实模型时，用哈希词袋方式构造简化 dense 向量

`_fallback_sparse(texts)`
- 无真实模型时，用哈希 token 权重构造 sparse 向量

`encode_dense(texts, is_query=True)`
- 生成 dense 向量

`encode_sparse(texts)`
- 生成 sparse 向量

`encode_full(texts)`
- 同时生成 dense 和 sparse 向量

`chunk_text(text, chunk_size=500, overlap=80)`
- 对文本按段落和长度进行切块
- 支持重叠窗口

---

## 8.11 `app/services/reranker.py`

作用：对召回到的候选文档进行重排序。

### 顶层函数说明

`_tokenize(text)`
- 将文本切成 token 集合
- 给 fallback 重排评分使用

### 类说明

`BGERerankerService`
- 文档重排序服务

### 方法说明

`__init__(model_name="BAAI/bge-reranker-v2-m3")`
- 初始化重排序模型参数和后端状态

`_ensure_model()`
- 尝试加载 FlagEmbedding 或 HuggingFace 重排序模型

`_fallback_score(query, document)`
- 用词重叠覆盖率计算简化相关分

`_hf_scores(query, documents)`
- 用 HuggingFace 分类模型给 query-doc 对打分

`rerank(query, documents, top_k=5)`
- 对文档文本列表打分并返回 top_k

`rerank_with_docs(query, docs_with_text, top_k=5)`
- 对完整文档对象列表重排
- 保留原元数据并补充 `rerank_score`

---

## 8.12 `app/services/llm_client.py`

作用：封装兼容 OpenAI 风格接口的大模型调用逻辑。

### 类说明

`LLMClient`
- 大模型客户端适配器

### 方法说明

`__init__(base_url, api_key, model, timeout=45)`
- 初始化模型标识、超时和底层 client

`_build_client(api_key)`
- 构造 OpenAI 客户端
- 若检测到本地死循环地址或 SDK 不可用，则返回 `None`

`_looks_like_local_backend_loop(base_url)`
- 防止把后端自己的 `http://localhost:8000/v1` 当成上游 LLM 服务

`_is_deepseek()`
- 判断当前上游是不是 DeepSeek

`_extract_context(user_content)`
- 从用户消息中提取“相关知识”部分

`_extract_latest_question(user_content)`
- 从拼装后的消息中抽出用户最新问题

`_fallback_answer(messages)`
- 当真实 LLM 不可用时，用上下文拼一个降级回答

`chat(messages, temperature=0.5, max_tokens=768, stream=False)`
- 发起一次模型调用
- 若异常则走 fallback

`chat_with_retry(messages, max_retries=1, temperature=0.5, max_tokens=768)`
- 带重试的模型调用封装

---

## 8.13 `app/services/memory.py`

作用：管理短期会话记忆，优先 Redis，失败时回退到进程内内存。

### 顶层函数说明

`_decode_messages(messages)`
- 把 JSON 字符串列表还原为字典列表

### 类说明

`MemoryService`
- 会话短期记忆服务

### 方法说明

`__init__(host, port, password=None)`
- 初始化 Redis 客户端
- Redis 不可用时保持为 `None`

`get_session_key(user_id, role_id, session_id)`
- 生成某个用户某个角色某个会话对应的唯一 key

`push_message(user_id, role_id, session_id, user_msg, assistant_msg, max_len=20)`
- 写入一轮对话
- Redis 模式下做 list 追加和裁剪
- 内存模式下写入本地缓存

`get_recent_messages(user_id, role_id, session_id, n=5)`
- 获取最近 n 条消息

`get_full_conversation(user_id, role_id, session_id)`
- 获取完整会话历史

`clear_session(user_id, role_id, session_id)`
- 清空某个会话缓存

`set_ttl(user_id, role_id, session_id, ttl=3600)`
- 给 Redis 会话 key 设置过期时间

---

## 8.14 `app/services/conversation_ingestion.py`

作用：把会话记录额外向量化并写入单独的会话集合。

### 顶层函数说明

`get_embedding()`
- 获取会话入库用的嵌入服务单例

`get_milvus()`
- 获取会话集合对应的 Milvus 客户端单例

`_build_conversation_text(conversation)`
- 把一条会话记录序列化成带元数据的文本

`save_conversation(conversation)`
- 把一条对话记录切块、向量化并写入会话 Milvus 集合

---

## 8.15 `app/services/__init__.py`

作用：包标记文件。  
无业务函数。

---

## 9. Repository 数据访问层 `app/repositories/`

这一层原则上只负责数据读写，不承载复杂业务决策。

## 9.1 `app/repositories/user_repository.py`

作用：用户数据访问。

### 类说明

`UserRepository`

### 方法说明

`__init__(db)`
- 保存数据库会话

`get_by_username(username)`
- 按用户名查询用户
- 忽略大小写

`create(username, password_hash, email)`
- 创建用户并提交数据库

---

## 9.2 `app/repositories/role_repository.py`

作用：角色数据访问。

### 类说明

`RoleRepository`

### 方法说明

`__init__(db)`
- 保存数据库会话

`get_by_id(role_id)`
- 按角色 ID 查询

`count_by_user(user_id)`
- 统计某个用户的角色数量

`list_for_user(user_id, include_public)`
- 获取用户角色列表
- 可选择是否包含公开角色

`save(role)`
- 保存角色

`delete(role)`
- 删除角色

---

## 9.3 `app/repositories/document_repository.py`

作用：文档数据访问。

### 类说明

`DocumentRepository`

### 方法说明

`__init__(db)`
- 保存数据库会话

`get_by_id(doc_id)`
- 获取单个文档

`list_by_user(user_id)`
- 获取某个用户的文档列表
- 按创建时间倒序

`list_doc_ids_by_user_and_domains(user_id, knowledge_domains)`
- 获取用户在指定知识域下可访问的文档 ID 列表

---

## 9.4 `app/repositories/conversation_repository.py`

作用：会话记录数据访问。

### 类说明

`ConversationRepository`

### 方法说明

`__init__(db)`
- 保存数据库会话

`create(user_id, role_id, session_id, message, response, retrieved_docs)`
- 创建一条会话记录

---

## 9.5 `app/repositories/__init__.py`

作用：包标记文件。  
无业务函数。

---

## 10. Database 基础设施层 `app/database/`

这一层负责 ORM、数据库连接、Milvus 连接等底层设施。

## 10.1 `app/database/models.py`

作用：定义 SQLAlchemy ORM 模型。

### 顶层函数说明

`_timestamp_column(**kwargs)`
- 创建统一的时间戳字段

### 模型说明

`User`
- 用户表

`Role`
- 角色表

`Conversation`
- 会话表

`Document`
- 文档表

`MilvusIndex`
- 本地 chunk 映射表

这些类本身主要用于表结构映射，没有复杂业务方法。

---

## 10.2 `app/database/mysql_client.py`

作用：异步数据库引擎、会话工厂、建表与迁移逻辑。

### 类说明

`MySQLClient`

### 方法说明

`__init__()`
- 创建异步数据库引擎和 session maker

`_build_engine_kwargs()`
- 根据数据库类型决定引擎参数
- SQLite 使用 `check_same_thread=False`
- MySQL 使用连接池参数

`_migrate_roles_schema(conn)`
- 针对 SQLite 的角色表结构做兼容迁移

`init_db()`
- 执行建表
- 针对 MySQL 调整 `documents.content` 为 LONGTEXT
- 执行角色表迁移

`close()`
- 关闭数据库引擎

### 顶层函数说明

`get_db()`
- FastAPI 依赖函数
- 为每个请求提供一个异步数据库会话

---

## 10.3 `app/database/milvus_client.py`

作用：封装 Milvus 的连接、集合初始化、混合检索、写入和删除逻辑。

### 顶层函数说明

`_cosine_similarity(left, right)`
- 计算两个稠密向量的余弦相似度
- 主要给内存回退模式使用

`_sparse_score(query_sparse, doc_sparse)`
- 计算两个稀疏向量的点积分数
- 主要给内存回退模式使用

### 类说明

`MilvusClient`
- Milvus 客户端封装

### 方法说明

`__init__(host, port, collection_name=None)`
- 初始化连接参数
- 尝试连接真实 Milvus
- 如果失败则进入内存回退模式

`_connect()`
- 建立 Milvus 连接

`_ensure_collection(dim=1024)`
- 确保目标集合存在
- 若不存在则创建集合和索引

`hybrid_search(query_dense, query_sparse, domains=None, doc_ids=None, top_k=20)`
- 执行混合检索
- 支持知识域过滤和文档 ID 过滤
- 在内存模式下用本地算法模拟检索

`upsert(data)`
- 向集合中插入或更新向量数据
- 内存模式下写入本地列表

`delete_by_doc_id(doc_id)`
- 删除某个文档对应的全部向量数据

---

## 10.4 `app/database/__init__.py`

作用：包标记文件。  
无业务函数。

---

## 11. Prompt 提示词层 `app/prompts/`

## 11.1 `app/prompts/templates.py`

作用：根据角色配置构造 system prompt。

### 函数说明

`_get_role_description(role_type)`
- 根据角色类型返回角色说明

`_get_role_specific_rules(role_type)`
- 根据角色类型返回角色专属规则

`get_role_prompt(role_config)`
- 组装完整 system prompt
- 把角色名称、性格、语言风格、知识域、约束、角色规则等整合进去

---

## 11.2 `app/prompts/__init__.py`

作用：包标记文件。  
无业务函数。

---

## 12. Streamlit 前端层

这一层主要服务于本地工作台和可视化操作。

## 12.1 `app/frontend_shared.py`

作用：为 Streamlit 页面提供共享状态管理、接口访问、登录登出、文档刷新、多角色聊天等能力。

### 顶层函数说明

`_new_session_id()`
- 生成新的 UUID 会话 ID

`_request_error_detail(exc)`
- 从请求异常中提取可展示的错误详情

`_reset_workspace_state()`
- 重置整个工作台状态

`_get_thread_payload(role_key, thread=None)`
- 获取某个角色线程当前使用的角色配置

`_run_role_chat(request_data, api_base, token)`
- 执行单个角色的一次聊天请求

`_format_role_result(role_key, data=None, error=None)`
- 把单角色请求结果整理成统一结构

`get_role_label(role_key)`
- 获取角色显示名

`get_knowledge_domain_label(domain_key)`
- 获取知识域显示名

`normalize_api_base(value)`
- 规范化后端地址

`parse_knowledge_domains(value)`
- 把输入字符串解析成知识域列表

`get_default_role_payload(role_key)`
- 获取某个角色类型的默认前端角色配置

`_build_thread(role_key, role_payload=None)`
- 构造一个新的角色聊天线程对象

`ensure_role_thread(role_key)`
- 确保某个角色的聊天线程存在

`set_active_role_keys(role_keys)`
- 设置当前启用的角色列表

`init_state()`
- 初始化 Streamlit `session_state`

`get_headers(include_auth=False, token=None)`
- 构造请求头

`api_request(method, path, include_auth=False, api_base=None, token=None, **kwargs)`
- 通用 API 请求封装

`check_backend_health()`
- 请求后端健康检查接口

`login(username, password)`
- 登录并保存 token、用户信息和工作台访问状态

`register_user(username, password, email="")`
- 注册账号

`logout()`
- 登出并清空会话状态

`refresh_documents()`
- 刷新文档缓存

`upload_document(file, knowledge_domain)`
- 上传一个文档到后端

`send_chat(message, role_payload, session_id, role_id=0, api_base=None, token=None)`
- 发起一次单角色聊天请求

`send_multi_role_chat(role_requests)`
- 支持一个或多个角色并行聊天
- 多角色模式下用线程池并发请求

`reset_chat(role_key=None)`
- 重置某个角色或全部角色的聊天线程

---

## 12.2 `app/streamlit_app.py`

作用：Streamlit 登录入口页面。

### 函数说明

`_html(block)`
- 去掉多行 HTML/CSS 字符串的多余缩进

`inject_login_style()`
- 注入登录页的整套自定义样式

`render_connection_box()`
- 渲染后端连接设置面板

`render_auth_tabs()`
- 渲染登录和注册两个 Tab

`render_showcase_panel()`
- 渲染左侧项目展示面板

`render_auth_panel(health)`
- 渲染右侧登录面板

`main()`
- Streamlit 登录页主入口
- 初始化状态、检测后端、渲染登录页面

---

## 12.3 `app/pages/1_Workspace.py`

作用：登录后的主工作台页面。

### 函数说明

`_html(block)`
- 格式化 HTML 片段

`inject_workspace_style()`
- 注入工作台专用样式

`render_role_editor(role_key)`
- 显示当前角色的人设、知识域、约束等信息

`render_sidebar(selected_role_key)`
- 渲染侧边栏
- 包含账号信息、退出登录、角色信息、文档上传、文档列表

`render_header(selected_role_key, health)`
- 渲染工作台头部概览
- 包含后端状态、当前角色、文档缓存、检索链路等摘要

`render_role_selector(selected_role_key)`
- 渲染单角色/多角色切换区域
- 管理当前启用角色和查看角色

`render_docs(docs)`
- 渲染检索到的参考知识片段

`render_conversation(selected_role_key)`
- 渲染当前角色的聊天记录

`process_prompt(prompt, role_payload, selected_role_key)`
- 处理用户输入
- 构造单角色或多角色请求
- 调用 `send_multi_role_chat()`
- 把回答回写到对应线程消息列表

`main()`
- 工作台页面主入口
- 检查登录状态
- 拉取健康状态和文档缓存
- 渲染头部、侧边栏、聊天区和输入框

---

## 12.4 `app/ui_components.py`

作用：封装一批 Streamlit 可复用 UI 组件和统一视觉样式。

### 函数说明

`_html(block)`
- 整理 HTML 模板字符串

`inject_theme()`
- 注入整套全局 UI 主题样式

`render_hero(title, subtitle, eyebrow, chips=None)`
- 渲染 Hero 区块

`render_section_intro(kicker, title, subtitle)`
- 渲染小节标题区域

`render_stat_cards(items)`
- 渲染统计卡片组

`render_glass_card(title, body)`
- 渲染玻璃态信息卡片

`render_feature_list(items)`
- 渲染特性列表

`render_status_pill(text, tone="ok")`
- 渲染状态胶囊标签

`render_role_banner(title, subtitle)`
- 渲染角色横幅

`render_workspace_strip(items)`
- 渲染工作台顶部摘要卡片条

`render_tag_cloud(tags)`
- 渲染标签云

`render_note_panel(title, body)`
- 渲染提示说明面板

`render_empty_stage(title, body)`
- 渲染空状态占位区

---

## 13. 包标记文件

这些文件的作用都比较简单，主要是把目录声明为 Python 包：

`app/__init__.py`
- 标记 `app` 为应用主包

`app/api/__init__.py`
- 标记 `api` 为接口子包

`app/database/__init__.py`
- 标记 `database` 为数据库子包

`app/dependencies/__init__.py`
- 标记 `dependencies` 为依赖子包

`app/prompts/__init__.py`
- 标记 `prompts` 为提示词子包

`app/repositories/__init__.py`
- 标记 `repositories` 为仓储子包

`app/schemas/__init__.py`
- 标记 `schemas` 为数据模型子包

`app/services/__init__.py`
- 标记 `services` 为服务子包

这些文件没有业务函数。

---

## 14. 最重要的阅读顺序

如果你想顺着代码真正看懂项目，建议按这个顺序：

1. `app/main.py`
2. `app/api/chat.py`
3. `app/services/chat_service.py`
4. `app/services/rag_engine.py`
5. `app/services/document_ingestion.py`
6. `app/services/document_parser.py`
7. `app/services/auth_service.py`
8. `app/services/role_service.py`
9. `app/repositories/*.py`
10. `app/database/models.py`
11. `app/database/milvus_client.py`
12. `app/frontend_shared.py`
13. `app/pages/1_Workspace.py`

---

## 15. 一句话总结

这个项目的 Python 代码可以概括为：

- `api` 负责收请求
- `dependencies` 负责鉴权注入
- `schemas` 负责数据结构
- `services` 负责真正业务
- `repositories` 负责数据库读写
- `database` 负责底层存储设施
- `prompts` 负责 system prompt
- `frontend_shared / streamlit_app / pages / ui_components` 负责 Streamlit 工作台交互
- 根目录脚本负责初始化、离线导入和评测

如果你接下来要，我可以继续把这份文档再升级成两种版本之一：

1. “精确到每个类方法输入输出”的更细版
2. “带调用链箭头和函数关系图”的结构版

