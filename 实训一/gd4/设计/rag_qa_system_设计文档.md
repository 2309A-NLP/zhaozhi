# gd4 rag_qa_system 设计文档

## 设计主题
gd4 的核心设计是把 PDF 解析链路升级为“本地规则 + LLM 清洗 + 视觉补强”的可切换组合。

## 关键设计点
- `AppConfig` 新增大量解析模式和资源限制配置
- `MilvusRepository` 支持 database 级隔离
- `main.py` 动态装配 `PdfTextCleanupClient` 与 `PdfVisionChartClient`
- `KnowledgeService` 开始接收上传大小限制与更完整的导入依赖
- 日志支持滚动切分

## 解析策略
- `local`：纯本地解析
- `hybrid/llm`：本地抽取后再走 LLM 文本清洗
- `vision_hybrid/auto`：在复杂页面上引入视觉模型辅助

## 设计收益
- 复杂 PDF 可处理范围明显扩大
- 部署者可以按成本和效果切换模式
- 更适合多类型资料库建设

## 设计代价
- 配置复杂度明显上升
- 排障链路变长，需要更强运维能力
