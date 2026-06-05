# gd6 rag_qa_system 部署文档

## 部署定位
gd6 是 gd5 的检索增强版，在多轮问答基础上引入混合召回融合参数 `HYBRID_RRF_K`，更关注召回质量。

## 新增部署关注点
- `HYBRID_RRF_K`
- `CONVERSATION_MAX_MESSAGES`
- `CONVERSATION_TTL_SECONDS`
- `MIN_CONTEXT_SCORE`
- PDF 清洗参数

## 推荐部署步骤
1. 完成底层依赖与模型配置
2. 设置对话参数和 `HYBRID_RRF_K`
3. 导入一组结构相近但表述不同的 PDF
4. 用同义表达问题做召回验证
5. 启动服务并做多轮问答回归

## 部署验收
- 同义问题的命中率较 gd5 更稳定
- 多轮对话与混合召回能同时正常工作
- `HYBRID_RRF_K` 调整后结果变化可感知、可解释

## 风险提示
- 融合参数设置不当会稀释高质量候选
- 多轮上下文与混合召回叠加后，排障复杂度进一步提升
