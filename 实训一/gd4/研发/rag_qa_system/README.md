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
MILVUS_DATABASE=gd
MILVUS_COLLECTION_NAME=rag_chunks

LLM_BASE_URL=https://api.siliconflow.cn/v1/chat/completions
LLM_API_KEY=your-key
LLM_MODEL=deepseek-chat

PDF_PARSER_MODE=local
PDF_LLM_BASE_URL=https://api.siliconflow.cn/v1/chat/completions
PDF_LLM_API_KEY=your-siliconflow-key
PDF_LLM_MODEL=Pro/zai-org/GLM-4.7
PDF_LLM_MAX_TOKENS=1024
PDF_LLM_TEMPERATURE=0.2
PDF_LLM_TIMEOUT_SECONDS=30
PDF_LLM_CHUNK_CHARS=12000
PDF_LLM_CHUNK_OVERLAP=600

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

`PDF_PARSER_MODE` 支持：

- `local`：只使用本地 `pypdf + OCR` 解析
- `hybrid`：先本地抽取 PDF 文本，再调用 SiliconFlow `Pro/zai-org/GLM-4.7` 清洗、去噪和重组文本
- `llm`：当前与 `hybrid` 行为一致；因为这里接入的是 `chat/completions` 接口，不是原始 PDF 文件上传接口，所以仍然需要先做本地文本抽取


`MYSQL_DATABASE`、`MILVUS_DATABASE` 和 `MILVUS_COLLECTION_NAME` 不能为空。代码会自动建 MySQL 库、Milvus 数据库和集合，但前提是 MySQL、Redis、Milvus 服务本身已启动。

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

1. 用增强版 `PdfParser` 解析 PDF
2. 自动清理重复页眉、页脚、页码、水印样式文本
3. 尝试按版面重组正文行，并提取表格为 `列1 | 列2 | ...` 文本
4. 如果系统已安装 `tesseract`，会对 PDF 内嵌图片文字执行 OCR；当整份 PDF 文本层极少时，也会自动启用 OCR 后备
5. 按 `CHUNK_SIZE` / `CHUNK_OVERLAP` 切块
6. 用本地 embedding 模型生成向量
7. 文本元数据写入 MySQL
8. 向量写入 Milvus

## 复杂 PDF 支持说明

当前 `gd4` 已针对以下常见复杂 PDF 场景做增强：

- 重复页眉、页脚、页码、部分水印文本清理
- 多栏/错位文本按坐标重组
- 表格抽取并转成可检索文本行
- PDF 内嵌图片中的文字 OCR（需要本机安装 `tesseract`）
- 扫描版或几乎无文本层 PDF 的整页 OCR 后备（当前代码接口已预留，后续可继续接入更强的 PDF 渲染器）

如果你要启用 OCR，建议本机安装：

```text
Tesseract OCR
中文语言包 chi_sim
英文语言包 eng
```

安装完成后，重新执行导入命令即可自动启用 OCR，无需改代码。

## 问答流程

1. 用本地 embedding 模型向量化问题
2. 在 Milvus 中召回候选块
3. 用本地 reranker 重排
4. 用 DeepSeek 生成答案
5. 将问答日志写入 MySQL，并把检索结果缓存到 Redis
