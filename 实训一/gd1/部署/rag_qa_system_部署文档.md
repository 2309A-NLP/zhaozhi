# gd1 rag_qa_system 部署文档

## 部署定位
gd1 是第一版落地形态，重点是把 PDF 问答从本地 JSON 迁移到 MySQL、Redis、Milvus 三层存储，并接入本地 embedding 与 reranker。

## 依赖准备
- Python 运行环境可用，能够执行 `python -m rag_qa_system.main serve`
- MySQL 已启动，并预留 `rag_qa_system` 库账号
- Redis 已启动，作为检索结果短期缓存
- Milvus 已启动，默认端口为 `19530`
- 本地 embedding 模型和 reranker 模型路径已配置
- LLM API Key 已写入 `.env`

## 推荐部署步骤
1. 进入 `gd1/研发/rag_qa_system`
2. 检查 `.env` 中的 `MYSQL_*`、`REDIS_*`、`MILVUS_*`、`BGE_*`、`LLM_*`
3. 先单独确认 MySQL、Redis、Milvus 连通
4. 执行 `python -m rag_qa_system.main ingest "pdfs\\示例.pdf"` 完成首份知识库导入
5. 执行 `python -m rag_qa_system.main serve`
6. 访问 `http://127.0.0.1:8000`

## 部署验收
- `/api/health` 返回 `status=ok`
- `/api/files` 能看到导入文件
- `/api/stats` 有文档和分块统计
- `/api/ask` 能返回答案且 MySQL 中产生问答日志

## 当前部署风险
- 已有日志显示 Milvus 在 `127.0.0.1:19530` 存在连接失败记录，部署前必须先做连通性检查
- 首次加载本地向量模型较慢，适合先预热再开放给使用者
- 该版本对复杂 PDF 清洗能力较弱，导入质量高度依赖原始文本层
