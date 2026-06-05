# 详细设计

## 模块划分
- `api/http_api.py`：HTTP 入口
- `controllers/qa_controller.py`：调用业务层
- `services/retrieval_service.py`：向量检索编排
- `services/prompt_service.py`：提示词模板
- `services/answer_service.py`：召回 + 生成
- `repositories/*.py`：Mysql / Milvus / Redis
- `models/*.py`：LLM / Embedding
- `offline/*.py`：PDF 解析和入库

## 函数调用
- `HttpApi.post_answer()` -> `QAController.handle_question()`
- `QAController.handle_question()` -> `AnswerService.answer()`
- `AnswerService.answer()` -> `RetrievalService.retrieve()`
- `RetrievalService.retrieve()` -> `EmbeddingClient.embed()` / `MilvusRepository.search()`
- `AnswerService.answer()` -> `PromptService.build_prompt()` -> `LLMClient.chat()`

