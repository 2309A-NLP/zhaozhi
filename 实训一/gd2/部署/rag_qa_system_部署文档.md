# gd2 rag_qa_system 部署文档

## 部署定位
gd2 在 gd1 基础上加入 `min_context_score`，开始控制“检索内容不足但仍硬答”的问题，部署重点从“能跑起来”转向“回答更稳”。

## 依赖要求
- 与 gd1 相同的 MySQL、Redis、Milvus、本地 embedding、reranker、LLM 能力
- `.env` 中额外确认 `MIN_CONTEXT_SCORE`

## 部署步骤
1. 进入 `gd2/研发/rag_qa_system`
2. 配置基础连接与模型路径
3. 设置 `MIN_CONTEXT_SCORE`，建议先从较保守值开始
4. 导入一批基准 PDF
5. 启动服务并对已知问题做回归测试

## 部署验收
- 基础接口全部可用
- 对知识库外问题，系统能更稳定地返回“信息不足”而不是编造答案
- 对知识库内高相关问题，不应因为阈值过高而拒答

## 部署关注点
- `MIN_CONTEXT_SCORE` 过低会退化为 gd1 行为
- `MIN_CONTEXT_SCORE` 过高会导致高频拒答
- 建议先在小样本问答集上调阈值，再给真实用户使用
