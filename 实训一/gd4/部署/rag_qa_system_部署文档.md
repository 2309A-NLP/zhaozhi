# gd4 rag_qa_system 部署文档

## 部署定位
gd4 是能力跨越较大的一版，开始支持 Milvus database、SiliconFlow 模型接入、PDF 多模式解析、OCR 与视觉增强，适合复杂文档场景试部署。

## 关键依赖
- MySQL、Redis、Milvus，且需确认 `MILVUS_DATABASE`
- SiliconFlow 兼容接口可用
- 本地 embedding 与 reranker 模型
- 需要 OCR 时，本机安装 Tesseract
- 如启用视觉增强，需准备 `PDF_VISION_*` 配置

## 部署步骤
1. 进入 `gd4/研发/rag_qa_system`
2. 配置 `.env` 中的数据库、缓存、Milvus database、主问答模型参数
3. 按场景选择 `PDF_PARSER_MODE`
4. 需要 OCR 时安装 Tesseract；需要 LLM 清洗或视觉解析时配置对应 API Key
5. 先导入少量复杂 PDF 验证解析质量
6. 启动服务并检查首页、统计接口、上传接口

## 推荐模式
- 普通文本型 PDF：`local`
- 文本脏、结构乱：`hybrid`
- 图表和扫描内容较多：`vision_hybrid` 或 `auto`

## 部署验收
- Milvus 指定 database 自动创建成功
- 复杂 PDF 导入后，文本质量明显优于 gd3
- 大文件上传和导入不因请求体过大直接失败
- 日志按轮转策略写入而不是无限增长

## 风险提示
- 外部模型依赖增多，稳定性受网络与配额影响
- 视觉模式成本更高，建议只对高价值文档开启
