# RAG 角色扮演系统部署文档

## 1. 项目概述

本项目由两部分组成：

- 后端：`FastAPI`
- 前端：`Streamlit`

核心能力：

- 注册 / 登录鉴权
- 虚拟角色对话
- 文档上传与解析（`txt` / `md` / `pdf` / `docx`）
- 知识检索增强生成（RAG）
- 支持 Milvus 检索
- 当 Milvus 不可达时，自动降级为本地切块检索

当前项目已经关闭游客模式，必须先注册账号再登录。

## 2. 目录说明

项目关键文件：

- 后端入口：`app/main.py`
- 前端入口：`app/streamlit_app.py`
- 数据库初始化：`init_db.py`
- 环境变量：`.env`
- 依赖文件：`requirements.txt`

## 3. 运行依赖

建议环境：

- Python `3.10+`
- MySQL `8.x`
- Redis `6.x/7.x`（可选）
- Milvus `2.4.x`（可选）

说明：

- MySQL：必需
- Redis：不是强依赖。不可用时，会自动退回进程内短期记忆
- Milvus：不是强依赖。不可用时，会自动退回本地切块检索
- 在线大模型 API：建议配置。当前默认走 DeepSeek 兼容接口

## 4. Python 依赖安装

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. 基础服务准备

### 5.1 MySQL

创建数据库：

```sql
CREATE DATABASE roleplay_rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

默认配置对应：

- 主机：`localhost`
- 端口：`3306`
- 用户：`root`
- 密码：`root`
- 数据库：`roleplay_rag`

如果你的实际配置不同，请修改 `.env`。

### 5.2 Redis（可选）

默认配置：

- 主机：`127.0.0.1`
- 端口：`6379`

如果你不使用 Redis，项目仍可运行，只是会退回内存记忆。

注意：你当前 `.env` 里的这一行需要自行确认：

```env
REDIS_PASSWORD=python init_db.py
```

这看起来不像正常密码，更像误写。建议改为：

- 无密码时：

```env
REDIS_PASSWORD=
```

- 或写成真实 Redis 密码

### 5.3 Milvus（可选）

当前项目配置：

```env
MILVUS_HOST=192.168.157.129
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=rag_knowledge
```

如果 Milvus 可达，系统优先使用 Milvus 检索。  
如果 Milvus 不可达，系统会自动改用本地切块检索，不会阻塞基本功能。

## 6. 环境变量配置

建议在项目根目录准备 `.env`。

可参考下面这份模板：

```env
APP_NAME=RAG 角色扮演系统
APP_VERSION=1.1.0

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=roleplay_rag

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=

MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=rag_knowledge

LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的_API_KEY
LLM_MODEL=deepseek-chat

BGE_EMBEDDING_MODEL=BAAI/bge-m3
BGE_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
ENABLE_FLAGEMBEDDING=0
ENABLE_FLAGRERANKER=0
EMBEDDING_DIM=1024
CHUNK_SIZE=500
CHUNK_OVERLAP=80

RETRIEVAL_TOP_K=6
RERANK_TOP_K=3
HYBRID_RRF_K=60
LLM_MAX_TOKENS=512
LLM_TEMPERATURE=0.5
LLM_MAX_RETRIES=1
LLM_TIMEOUT_SECONDS=12
LLM_HARD_TIMEOUT_SECONDS=15
CONTEXT_DOC_CHAR_LIMIT=400

SHORT_TERM_MAX_LEN=20
SHORT_TERM_TTL=3600

SECRET_KEY=change-this-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

DEFAULT_ROLE_NAME=AI助手
DEFAULT_ROLE_TYPE=friend
```

## 7. 数据库初始化

本项目会在启动后端时自动建表。  
也可以先手动执行一次初始化：

```bash
python init_db.py
```

作用：

- 创建所需数据表
- 不再自动创建默认管理员或游客账号

## 8. 启动方式

### 8.1 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- 健康检查：`http://127.0.0.1:8000/health`

正常返回示例：

```json
{"status":"ok","app":"RAG 角色扮演系统","version":"1.1.0"}
```

### 8.2 启动前端

```bash
streamlit run app/streamlit_app.py
```

默认前端地址：

- `http://127.0.0.1:8501`

## 9. 首次使用流程

1. 启动 MySQL
2. 启动 Redis（如果使用）
3. 启动 Milvus（如果使用）
4. 启动 FastAPI 后端
5. 启动 Streamlit 前端
6. 打开前端页面
7. 先注册账号
8. 用注册后的账号登录
9. 上传文档并开始对话

## 10. 文档上传与检索说明

上传支持：

- `.txt`
- `.md`
- `.pdf`
- `.docx`

上传后流程：

1. 文档被解析为纯文本
2. 文本被按配置切块
3. 尝试写入 Milvus
4. 同时把切块副本写入 MySQL 的本地表

因此现在的检索逻辑是：

- Milvus 可用：优先使用 Milvus
- Milvus 不可用：自动使用本地切块检索

这意味着：

- 即使 Milvus 服务不在同一网络区域
- 或暂时连不上 `19530`
- 系统依然可以继续做知识问答

## 11. 推荐部署模式

### 模式 A：本机开发模式

适合单机调试：

- MySQL：本机
- Redis：本机或不启
- Milvus：可不启
- LLM：在线 API

优点：

- 部署最简单
- 不依赖复杂网络

### 模式 B：局域网完整模式

适合内网服务器：

- MySQL：服务器
- Redis：服务器
- Milvus：服务器
- LLM：在线 API 或本地模型

要求：

- 应用服务器必须能访问 Milvus 的 `19530`
- 如果前后端不在同机，需确认网络和防火墙放行

### 模式 C：公网 / 生产模式

建议：

- 后端：`uvicorn/gunicorn + 反向代理`
- 前端：`streamlit` 单独跑
- MySQL / Redis / Milvus 分离部署
- `.env` 使用生产密钥
- 关闭 `--reload`

## 12. 生产部署建议

### 后端

不要使用开发模式：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端

可以指定端口：

```bash
streamlit run app/streamlit_app.py --server.port 8501
```

### 反向代理

建议把以下服务分开：

- `/api/*` 反代到 FastAPI
- `/` 反代到 Streamlit

### 安全项

至少修改：

- `SECRET_KEY`
- `LLM_API_KEY`
- `MYSQL_PASSWORD`
- `REDIS_PASSWORD`

## 13. 自检命令

### 后端健康检查

```bash
curl http://127.0.0.1:8000/health
```

### 聊天接口测试

```bash
python -c "import requests; payload={'user_id':1,'role_id':0,'message':'你好','role_config_override':{'role_name':'医生','role_type':'doctor','knowledge_domains':['medical']}}; r=requests.post('http://127.0.0.1:8000/api/chat/', json=payload, timeout=30); print(r.status_code); print(r.text)"
```

注意：当前系统已经启用登录鉴权。  
如果你直接调 `/api/chat/`，生产情况下应带登录后的 Bearer Token。

### Milvus 端口检查

Windows：

```powershell
Test-NetConnection 192.168.157.129 -Port 19530
```

Linux：

```bash
nc -zv 127.0.0.1 19530
```

## 14. 常见问题

### 14.1 后端能启动，但问答超时

优先检查：

- 在线 API Key 是否有效
- `LLM_BASE_URL` 是否正确
- 网络能否访问外部模型接口
- `LLM_TIMEOUT_SECONDS` 和 `LLM_HARD_TIMEOUT_SECONDS`

### 14.2 Milvus 连不上

现象：

- `pymilvus` 连接报错
- `Test-NetConnection ... 19530` 失败

排查：

- Milvus 容器是否 `healthy`
- `19530` 是否映射
- Ubuntu 防火墙 / 云防火墙是否放行
- Windows 到 Linux 虚拟机端口是否可达

当前项目已支持自动降级，所以 Milvus 连不上不会导致系统完全不可用。

### 14.3 Redis 连不上

项目会自动退回内存记忆：

- 会话仍可进行
- 但服务重启后短期记忆会丢失

### 14.4 前端能打开但无法登录

检查：

- 后端是否已经启动
- `/health` 是否正常
- MySQL 是否可连接
- 是否已先注册账号

### 14.5 文档上传成功，但检索效果差

检查：

- `knowledge_domain` 是否设置正确
- 文档内容是否成功解析
- `ENABLE_FLAGEMBEDDING` / `ENABLE_FLAGRERANKER` 是否开启
- 当前是否在 Milvus 模式还是本地降级检索模式

## 15. 建议的部署顺序

推荐严格按下面顺序进行：

1. 配置 `.env`
2. 启动 MySQL
3. 启动 Redis（可选）
4. 启动 Milvus（可选）
5. `pip install -r requirements.txt`
6. `python init_db.py`
7. `uvicorn app.main:app --host 0.0.0.0 --port 8000`
8. `streamlit run app/streamlit_app.py`
9. 注册账号并登录
10. 上传文档进行问答测试

## 16. 部署完成判定

满足以下条件即可认为部署成功：

- `http://127.0.0.1:8000/health` 返回 `ok`
- 前端登录页可打开
- 能成功注册并登录
- 能上传 PDF / 文本
- 提问时能返回回答
- 即使 Milvus 不通，系统仍能基于本地切块回答

