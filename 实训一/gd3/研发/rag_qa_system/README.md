# RAG PDF QA System

这个项目现在使用真实的 MySQL、Redis、Milvus 和本地向量模型，不再使用本地 JSON 文件模拟数据层。

## 当前架构

- `backend/repositories/mysql_repo.py`：存储文档元数据、文本分块、问答日志
- `backend/repositories/milvus_repo.py`：存储文本分块向量并执行相似度搜索
- `backend/repositories/redis_repo.py`：缓存检索结果
- `backend/models/llm_client.py`：DeepSeek 对话、本地 embedding、本地 reranker
- `offline/ingest.py`：PDF 解析、切块、向量化、写入 MySQL + Milvus

## 环境变量

`.env` 采用如下配置：

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=rag_qa_system

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=

MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=rag_chunks

LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=your-key
LLM_MODEL=deepseek-chat

BGE_EMBEDDING_MODEL=C:\path\to\m3e-base
BGE_RERANKER_MODEL=C:\path\to\bge-reranker-base
ENABLE_FLAGEMBEDDING=1
ENABLE_FLAGRERANKER=1
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
```

`MYSQL_DATABASE` 和 `MILVUS_COLLECTION_NAME` 不能为空。代码会自动建库建表和建集合，但前提是 MySQL、Redis、Milvus 服务本身已启动。

## 启动

```powershell
python -m rag_qa_system.main serve
```

访问：

```text
http://127.0.0.1:8000
```

## 导入 PDF

```powershell
python -m rag_qa_system.main ingest "pdfs\\你的文件.pdf"
```

导入流程：

1. 用 `pypdf` 解析 PDF
2. 按 `CHUNK_SIZE` / `CHUNK_OVERLAP` 切块
3. 用本地 embedding 模型生成向量
4. 文本元数据写入 MySQL
5. 向量写入 Milvus

## 问答流程

1. 用本地 embedding 模型向量化问题
2. 在 Milvus 中召回候选块
3. 用本地 reranker 重排
4. 用 DeepSeek 生成答案
5. 将问答日志写入 MySQL，并把检索结果缓存到 Redis
