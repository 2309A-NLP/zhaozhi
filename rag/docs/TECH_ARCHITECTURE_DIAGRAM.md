# 技术架构图

基于当前代码结构生成，覆盖双前端入口、FastAPI API 层、服务层、RAG 核心链路、数据存储以及文档入库流程。

## 1. 总体架构图

```mermaid
flowchart LR
    U[用户]

    subgraph FE[前端入口]
        WEB[静态前端\nfrontend/index.html + app.js + styles.css]
        ST[Streamlit 工作台\napp/streamlit_app.py\napp/pages/1_Workspace.py]
    end

    subgraph BE[应用入口]
        FASTAPI[FastAPI\napp/main.py]
        AUTH_DEP[认证依赖\napp/dependencies/auth.py]
    end

    subgraph API[接口层 app/api]
        AUTH_API[auth.py]
        ROLE_API[roles.py]
        DOC_API[documents.py]
        CHAT_API[chat.py]
    end

    subgraph SVC[服务层 app/services]
        AUTH_SVC[AuthService]
        ROLE_SVC[RoleService]
        DOC_SVC[DocumentService]
        CHAT_SVC[ChatService]
        OFFLINE_SVC[OfflineImportService]
        INGEST[document_ingestion.py]
        RAG[RAGEngine]
        MEMORY[MemoryService]
        EMBED[BGEEmbeddingService]
        RERANK[BGERerankerService]
        LLM[LLMClient]
        PARSER[document_parser.py]
    end

    subgraph REPO[仓储层 app/repositories]
        USER_REPO[UserRepository]
        ROLE_REPO[RoleRepository]
        DOC_REPO[DocumentRepository]
        CONV_REPO[ConversationRepository]
    end

    subgraph DATA[数据层]
        SQL[(MySQL / SQLite\nusers roles documents conversations milvus_index)]
        MILVUS[(Milvus\n向量检索)]
        REDIS[(Redis\n短期会话记忆)]
        FILES[(data/documents\n原始文件)]
    end

    U --> WEB
    U --> ST

    WEB --> FASTAPI
    ST --> FASTAPI

    FASTAPI --> AUTH_API
    FASTAPI --> ROLE_API
    FASTAPI --> DOC_API
    FASTAPI --> CHAT_API
    AUTH_API --> AUTH_DEP
    ROLE_API --> AUTH_DEP
    DOC_API --> AUTH_DEP
    CHAT_API --> AUTH_DEP

    AUTH_API --> AUTH_SVC
    ROLE_API --> ROLE_SVC
    DOC_API --> DOC_SVC
    CHAT_API --> CHAT_SVC

    AUTH_SVC --> USER_REPO
    ROLE_SVC --> ROLE_REPO
    DOC_SVC --> DOC_REPO
    DOC_SVC --> INGEST
    CHAT_SVC --> ROLE_REPO
    CHAT_SVC --> DOC_REPO
    CHAT_SVC --> CONV_REPO
    CHAT_SVC --> RAG
    OFFLINE_SVC --> INGEST

    USER_REPO --> SQL
    ROLE_REPO --> SQL
    DOC_REPO --> SQL
    CONV_REPO --> SQL

    INGEST --> PARSER
    INGEST --> EMBED
    INGEST --> MILVUS
    INGEST --> SQL
    INGEST --> FILES

    RAG --> MEMORY
    RAG --> EMBED
    RAG --> RERANK
    RAG --> LLM
    RAG --> MILVUS
    RAG --> SQL

    MEMORY --> REDIS
    MEMORY -. Redis 不可用时回退 .-> SQL
    RAG -. Milvus 检索失败时回退本地 chunk .-> SQL
    MILVUS -. 不可用时回退内存索引 .-> RAG
```

## 2. 在线对话 RAG 链路

```mermaid
flowchart TD
    A[POST /api/chat] --> B[Chat API]
    B --> C[ChatService.chat]
    C --> D[加载角色配置\nRoleRepository]
    C --> E[筛选允许访问的文档\nDocumentRepository]
    C --> F[RAGEngine.chat]

    F --> G[读取短期记忆\nMemoryService.get_recent_messages]
    G --> G1[(Redis)]
    G -. 回退 .-> G2[(内存缓存)]

    F --> H[拼接 search query]
    H --> I[Embedding 编码\ndense + sparse]
    I --> J[Milvus hybrid_search]
    J -. 失败时回退 .-> K[SQL 中的本地 chunk 搜索\nMilvusIndex + Document]

    J --> L[候选文档]
    K --> L
    L --> M[Reranker 重排]
    M --> N[构造 system/user messages]
    N --> O[LLMClient.chat_with_retry]
    O --> P[生成回复]

    P --> Q[写回短期记忆\npush_message + TTL]
    Q --> G1
    Q -. 回退 .-> G2

    P --> R[ConversationRepository.create]
    R --> S[(MySQL / SQLite conversations)]
    P --> T[返回 ChatResponse]
```

## 3. 文档入库链路

```mermaid
flowchart TD
    A1[上传文件 / 本地导入] --> A2[DocumentService / OfflineImportService]
    A2 --> A3[document_ingestion.save_document]
    A3 --> A4[document_parser.extract_text]
    A4 --> A5[保存原始文件到 data/documents]
    A5 --> A6[写入 documents 表]
    A6 --> A7[index_document]
    A7 --> A8[chunk_text]
    A8 --> A9[Embedding encode_full]
    A9 --> A10[Milvus upsert]
    A10 --> A11[replace_local_chunks]
    A11 --> A12[(milvus_index / documents)]
```

## 4. 代码对应关系

- 应用入口：`app/main.py`
- 静态前端：`frontend/`
- Streamlit 工作台：`app/streamlit_app.py`、`app/pages/1_Workspace.py`
- API 层：`app/api/*.py`
- 服务层：`app/services/*.py`
- 仓储层：`app/repositories/*.py`
- 数据访问：`app/database/mysql_client.py`、`app/database/milvus_client.py`
- 短期记忆：`app/services/memory.py`

