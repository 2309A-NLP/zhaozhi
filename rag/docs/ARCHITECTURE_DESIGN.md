# 角色扮演 RAG 系统架构设计

## 1. 设计目标

本项目重构后的目标如下：

1. 前后端分离：前端只包含 `html / css / vue / js`，不包含 Python 代码。
2. 接口层无业务逻辑：接口层只负责 `HTTP + JSON` 入参出参转换。
3. 业务逻辑下沉：鉴权、角色管理、文档入库、RAG 对话全部进入服务层。
4. 数据访问独立：MySQL / SQLite、Milvus、Redis 的访问统一收敛到数据层与基础服务。
5. 模块可复用：一个 `py` 提供多个函数或类，另一个 `py` 中 `import` 后调用，避免大而全脚本。
6. 离线/在线流程分离：离线负责数据准备和知识库导入，在线负责查询、检索、提示词拼装与生成。

---

## 2. 概要设计

### 2.1 子系统划分

系统分为五个子系统：

1. 前端子系统
2. 接口层子系统
3. 业务逻辑子系统
4. 数据层子系统
5. 模型层子系统

### 2.2 子系统交互方式

#### 前端 -> 接口层

- 交互协议：`HTTP + JSON`
- 典型接口：
  - `POST /api/auth/register`
  - `POST /api/auth/token`
  - `GET /api/auth/me`
  - `GET /api/roles/`
  - `POST /api/documents/upload`
  - `POST /api/chat/`

#### 接口层 -> 业务逻辑层

- 交互方式：Python 函数 / 类方法调用
- 示例：
  - `AuthService.register_user(...)`
  - `DocumentService.upload_document(...)`
  - `ChatService.chat(...)`

#### 业务逻辑层 -> 数据层

- 交互方式：`import` 仓储类或基础数据服务后调用
- 涉及组件：
  - MySQL / SQLite：用户、角色、文档、会话元数据
  - Milvus：向量索引与检索
  - Redis：短期记忆

#### 业务逻辑层 -> 模型层

- 交互方式：函数 / 类方法调用
- 典型组件：
  - `LLMClient`
  - `BGEEmbeddingService`
  - `BGERerankerService`

---

## 3. 分层架构

### 3.1 前端层

目录：`frontend/`

- `index.html`
- `styles.css`
- `app.js`

职责：

- 页面展示
- 用户交互
- 调用后端 HTTP JSON 接口
- 不承载任何 Python 业务逻辑

### 3.2 接口层

目录：`app/api/`

- `auth.py`
- `roles.py`
- `documents.py`
- `chat.py`

职责：

- 定义路由
- 接收请求参数
- 返回 JSON 响应
- 调用业务层服务

约束：

- 不直接写复杂业务逻辑
- 不直接拼装底层数据访问细节

### 3.3 业务逻辑层

目录：`app/services/`

- `auth_service.py`
- `role_service.py`
- `document_service.py`
- `chat_service.py`
- `offline_import_service.py`
- `rag_engine.py`

职责：

- 承载核心用例
- 编排模型层与数据层
- 封装跨模块流程

### 3.4 数据层

目录：

- `app/repositories/`
- `app/database/`

职责：

- MySQL / SQLite：
  - 用户表
  - 角色表
  - 文档表
  - 会话表
- Milvus：
  - 向量存储
  - 向量检索
- Redis：
  - 短期记忆
  - session 对话缓存

### 3.5 模型层

目录：`app/services/`

- `llm_client.py`
- `embedding.py`
- `reranker.py`

职责：

- 大模型 API 调用
- 文本向量化
- 重排

---

## 4. 详细设计

### 4.1 模块划分

#### 核心配置与共享定义

- `app/config.py`
  - 管理环境变量
  - 统一数据库、Milvus、Redis、LLM 配置

- `app/core/role_defaults.py`
  - 管理角色默认画像
  - 提供默认角色配置函数

#### 接口模型层

- `app/schemas/auth.py`
- `app/schemas/role.py`
- `app/schemas/document.py`
- `app/schemas/chat.py`

职责：

- 请求体定义
- 响应体定义
- 参数校验

#### 仓储层

- `app/repositories/user_repository.py`
- `app/repositories/role_repository.py`
- `app/repositories/document_repository.py`
- `app/repositories/conversation_repository.py`

职责：

- 只做数据读写
- 不写业务判断

#### 业务服务层

- `AuthService`
  - 注册
  - 登录
  - token 用户解析

- `RoleService`
  - 角色增删改查

- `DocumentService`
  - 文档上传
  - 文档更新
  - 文档删除
  - 文档查询

- `ChatService`
  - 角色配置拼装
  - 文档权限过滤
  - 调用 RAGEngine
  - 会话落库

- `OfflineImportService`
  - 离线导入本地 PDF

#### RAG 流程层

- `rag_engine.py`
  - 查询改写 / 上下文搜索词拼装
  - 向量检索
  - 本地降级检索
  - rerank
  - prompt 上下文构造
  - 调用大模型生成

---

## 5. 模块间调用关系

### 5.1 HTTP 调用

前端 Vue 页面调用后端：

1. `frontend/app.js`
2. `fetch('/api/...')`
3. `app/api/*.py`
4. `app/services/*.py`
5. `app/repositories/*.py` / `MilvusClient` / `MemoryService` / `LLMClient`

### 5.2 Python import 调用

示例 1：接口层调用业务层

- `app/api/chat.py`
  - `from ..services.chat_service import ChatService`
  - `await ChatService(db, get_rag_engine()).chat(request, current_user)`

示例 2：业务层调用仓储层

- `app/services/chat_service.py`
  - `from ..repositories.document_repository import DocumentRepository`
  - `await self.documents.list_doc_ids_by_user_and_domains(...)`

示例 3：业务层调用模型层

- `app/services/chat_service.py`
  - `await self.rag_engine.chat(...)`

示例 4：离线脚本调用服务层

- `import_local_pdf.py`
  - `from app.services.offline_import_service import OfflineImportService`
  - `await service.import_file(...)`

---

## 6. RAG 设计

### 6.1 离线部分：数据准备与知识库导入

离线入口：

- `import_local_pdf.py`
- `DocumentService.upload_document(...)`
- `OfflineImportService.import_file(...)`

离线流程：

1. 读取本地 PDF / 上传文件
2. 解析文档文本
3. 文本切块
4. 文本向量化
5. 写入 Milvus
6. 文档元数据写入 MySQL / SQLite
7. 切块副本写入本地表，作为 Milvus 不可用时的回退

对应模块：

- 文档解析：`app/services/document_parser.py`
- 文档入库：`app/services/document_ingestion.py`
- 离线编排：`app/services/offline_import_service.py`

### 6.2 在线部分：查询、提示词、生成

在线入口：

- `POST /api/chat/`

在线流程：

1. 接收用户问题
2. 获取角色配置
3. 获取允许访问的知识文档范围
4. 将用户问题转为检索 query
5. query 向量化
6. Milvus 混合检索
7. 若 Milvus 失败，则本地切块检索
8. 使用 reranker 重排
9. 构造 prompt 模板
10. 调用大模型 API 生成答案
11. 写入 Redis 短期记忆
12. 写入 MySQL / SQLite 会话表

对应模块：

- 编排入口：`app/services/chat_service.py`
- 检索与生成：`app/services/rag_engine.py`
- 提示词模板：`app/prompts/templates.py`
- 模型调用：`app/services/llm_client.py`

---

## 7. 数据层设计

### 7.1 MySQL / SQLite

用途：

- 用户信息
- 角色配置
- 文档元数据
- 会话日志
- 本地切块索引

对应文件：

- `app/database/models.py`
- `app/database/mysql_client.py`
- `app/repositories/*.py`

### 7.2 Milvus

用途：

- 存储文档 chunk 向量
- 提供向量检索与混合检索

对应文件：

- `app/database/milvus_client.py`

### 7.3 Redis

用途：

- 保存短期多轮对话记忆
- session 维度缓存最近消息

对应文件：

- `app/services/memory.py`

---

## 8. 函数设计与封装原则

### 8.1 一个 py 提供多个函数，在另一个 py 中 import 后调用

示例：

- `app/core/role_defaults.py`
  - `get_role_profile`
  - `build_default_role_config`
  - `build_effective_knowledge_domains`

- `app/services/chat_service.py`
  - `from ..core.role_defaults import build_default_role_config`

### 8.2 封装成函数 / 类方法，函数间调用

示例：

- `DocumentService.upload_document`
  - 调用 `read_uploaded_content`
  - 调用 `save_document`
  - 调用 `serialize_document`

- `ChatService.chat`
  - 调用 `_get_role_config`
  - 调用 `build_effective_knowledge_domains`
  - 调用 `rag_engine.chat`

### 8.3 设计原则

1. 接口层只调服务层
2. 服务层只编排，不直接写原始 SQL
3. 仓储层只做数据访问
4. 模型层只做模型能力调用
5. 公共规则收敛到 `core / schemas / repositories`

---

## 9. 当前目录建议

```text
frontend/
  index.html
  styles.css
  app.js

app/
  api/
  core/
  dependencies/
  schemas/
  repositories/
  services/
  database/
  prompts/
  main.py
```

---

## 10. 总结

本次重构后，系统已经具备以下结构特征：

1. 前端和后端完全分离，前端通过 HTTP JSON 调后端。
2. 接口层不做核心业务，只做参数接收和服务调用。
3. 业务逻辑层承载 RAG、鉴权、角色、文档等完整流程。
4. 数据层清晰区分 MySQL / SQLite、Milvus、Redis。
5. 离线导入和在线检索生成拆分明确。
6. 函数、类和模块之间通过 `import` 调用，符合面向对象与模块化设计要求。
