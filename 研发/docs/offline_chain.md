# 离线部分函数链条

这个文档说明项目里“离线部分”是怎么从一个 `.py` 文件的函数，走到另一个 `.py` 文件的函数的。

这里以默认朋友角色 `friend` 为例。

## 1. 从前端进入后端的主链条

朋友角色的默认配置定义在：

- `app/frontend_shared.py` -> `get_default_role_payload(role_key)`

用户在工作台发送消息后，函数调用链条是：

1. `app/pages/1_Workspace.py` -> `process_prompt(prompt, role_payload, selected_role_key)`
2. `app/frontend_shared.py` -> `send_multi_role_chat(role_requests)`
3. `app/frontend_shared.py` -> `_run_role_chat(request_data, api_base, token)`
4. `app/frontend_shared.py` -> `send_chat(message, role_payload, session_id, role_id, api_base, token)`
5. `app/api/chat.py` -> `chat(request, db, current_user)`
6. `app/services/chat_service.py` -> `ChatService.chat(request, current_user)`
7. `app/services/rag_engine.py` -> `RAGEngine.chat(...)`

真正的“离线部分”从 `RAGEngine.chat(...)` 开始分支出来。

## 2. 离线记忆链条

短期记忆优先使用 Redis，如果 Redis 不可用，就退回到本地内存。

函数链条：

1. `app/services/rag_engine.py` -> `RAGEngine.chat(...)`
2. `app/services/memory.py` -> `MemoryService.get_recent_messages(...)`
3. 优先读取 Redis
4. 如果 Redis 异常，退回 `app/services/memory.py` 中的 `_memory_store`

对话结束后还会反向写回：

1. `app/services/rag_engine.py` -> `RAGEngine.chat(...)`
2. `app/services/memory.py` -> `MemoryService.push_message(...)`
3. 优先写入 Redis
4. 如果 Redis 异常，写入 `_memory_store`
5. `app/services/memory.py` -> `MemoryService.set_ttl(...)`

## 3. 离线检索链条

检索优先使用 Milvus 混合检索，如果 Milvus 不可用或者没有结果，就退回到本地检索。

函数链条：

1. `app/services/rag_engine.py` -> `RAGEngine.chat(...)`
2. `app/services/rag_engine.py` -> `_retrieve_documents(...)`
3. `app/database/milvus_client.py` -> `MilvusClient.hybrid_search(...)`

这里有两种离线路径。

### 路径 A：MilvusClient 内部的内存降级

1. `app/database/milvus_client.py` -> `MilvusClient.__init__(...)`
2. 连接 Milvus 失败
3. 设置 `self._use_memory = True`
4. `app/database/milvus_client.py` -> `MilvusClient.hybrid_search(...)`
5. 直接从 `app/database/milvus_client.py` 里的 `_memory_store` 做内存检索

### 路径 B：RAGEngine 的本地数据库降级

1. `app/services/rag_engine.py` -> `_retrieve_documents(...)`
2. `MilvusClient.hybrid_search(...)` 报错或返回空
3. `app/services/rag_engine.py` -> `_local_search(...)`
4. 从 `MilvusIndex.chunk_text` 和 `Document.content` 中取本地片段

## 4. 离线回答生成链条

回答生成优先调用大模型，如果大模型不可用或者超时，就退回到本地兜底回答。

函数链条：

1. `app/services/rag_engine.py` -> `RAGEngine.chat(...)`
2. `app/services/rag_engine.py` -> `_generate_response(messages, user_message, reranked_docs)`
3. `app/services/llm_client.py` -> `LLMClient.chat_with_retry(...)`
4. `app/services/llm_client.py` -> `LLMClient.chat(...)`

然后有两条离线路径。

### 路径 A：LLMClient 内部兜底

1. `app/services/llm_client.py` -> `LLMClient.chat(...)`
2. 如果 `self.client is None` 或调用异常
3. `app/services/llm_client.py` -> `LLMClient._fallback_answer(messages)`

### 路径 B：RAGEngine 超时兜底

1. `app/services/rag_engine.py` -> `_generate_response(...)`
2. 如果异步等待超时或生成失败
3. `app/services/rag_engine.py` -> `_build_timeout_fallback(user_message, reranked_docs)`

## 5. 文档侧的离线支撑链条

离线检索之所以能工作，是因为文档上传后，本地数据库里保留了 chunk。

函数链条：

1. `app/services/offline_import_service.py` -> `OfflineImportService.import_file(...)`
2. `app/services/document_ingestion.py` -> `upsert_local_file(...)`
3. `app/services/document_ingestion.py` -> `save_document(...)`
4. `app/services/document_ingestion.py` -> `index_document(document)`
5. `app/services/document_ingestion.py` -> `replace_local_chunks(db, document, chunks, milvus_ids)`

即使 Milvus 失败，`replace_local_chunks(...)` 依然会把 chunk 写进本地表，供 `_local_search(...)` 使用。

## 6. 最短版离线主链条

如果只看最核心的一条，可以记成：

1. `app/pages/1_Workspace.py` -> `process_prompt(...)`
2. `app/frontend_shared.py` -> `send_chat(...)`
3. `app/api/chat.py` -> `chat(...)`
4. `app/services/chat_service.py` -> `ChatService.chat(...)`
5. `app/services/rag_engine.py` -> `RAGEngine.chat(...)`
6. `app/services/memory.py` -> `MemoryService.get_recent_messages(...)`
7. `app/services/rag_engine.py` -> `_retrieve_documents(...)`
8. `app/database/milvus_client.py` -> `MilvusClient.hybrid_search(...)`
9. 如果失败，`app/services/rag_engine.py` -> `_local_search(...)`
10. `app/services/llm_client.py` -> `LLMClient.chat(...)`
11. 如果失败，`app/services/llm_client.py` -> `_fallback_answer(...)`
12. `app/services/memory.py` -> `MemoryService.push_message(...)`

## 7. 一句话总结

这个项目的离线部分不是一个单独模块，而是三层降级：

1. Redis 不可用，降级到 `MemoryService._memory_store`
2. Milvus 不可用，降级到 `MilvusClient._memory_store` 或 `RAGEngine._local_search(...)`
3. LLM 不可用，降级到 `LLMClient._fallback_answer(...)` 或 `RAGEngine._build_timeout_fallback(...)`
