# gd1 rag_qa_system 设计文档

## 版本设计重点
gd1 的设计目标不是做复杂能力，而是完成 RAG 基础闭环，形成最小可运行版本。

## 模块划分
- `main.py`：装配配置、仓储、模型与服务
- `backend/api` 与 `controllers`：接口分发
- `services`：问答、提示词、检索、知识库业务
- `repositories`：MySQL、Redis、Milvus 访问
- `offline`：PDF 解析、切块、向量化、入库
- `frontend`：轻量 Web 页面

## 在线链路
用户问题 -> embedding -> Milvus 召回 -> reranker 重排 -> Prompt 组装 -> LLM 生成 -> MySQL 记录日志

## 离线链路
PDF -> 文本解析 -> chunk 切分 -> 向量生成 -> MySQL 保存元数据/文本块 -> Milvus 写入向量

## 设计边界
- 只处理单机部署
- 只提供基础 HTTP 接口
- 不做复杂 PDF 清洗，不做多轮对话记忆
