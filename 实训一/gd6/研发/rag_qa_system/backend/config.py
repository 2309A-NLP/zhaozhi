"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env_file(env_file: Path = ENV_FILE) -> None:
    """Load simple KEY=VALUE pairs from a .env file into os.environ."""
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


@dataclass(frozen=True)
class AppConfig:
    """Central configuration shared across layers."""

    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    pdf_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "pdfs")
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "logs")
    frontend_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "frontend")
    uploads_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "uploads")
    app_log_file: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "logs" / "app.log")
    mysql_host: str = field(default_factory=lambda: os.getenv("MYSQL_HOST", "127.0.0.1"))
    mysql_port: int = field(default_factory=lambda: int(os.getenv("MYSQL_PORT", "3306")))
    mysql_user: str = field(default_factory=lambda: os.getenv("MYSQL_USER", "root"))
    mysql_password: str = field(default_factory=lambda: os.getenv("MYSQL_PASSWORD", ""))
    mysql_database: str = field(default_factory=lambda: os.getenv("MYSQL_DATABASE", "rag_qa_system"))
    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "127.0.0.1"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_password: str = field(default_factory=lambda: os.getenv("REDIS_PASSWORD", ""))
    milvus_host: str = field(default_factory=lambda: os.getenv("MILVUS_HOST", "127.0.0.1"))
    milvus_port: int = field(default_factory=lambda: int(os.getenv("MILVUS_PORT", "19530")))
    milvus_collection_name: str = field(default_factory=lambda: os.getenv("MILVUS_COLLECTION_NAME", "rag_chunks"))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.deepseek.com"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-chat"))
    llm_max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "512")))
    llm_temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.5")))
    llm_max_retries: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "1")))
    llm_timeout_seconds: int = field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT_SECONDS", "12")))
    llm_hard_timeout_seconds: int = field(default_factory=lambda: int(os.getenv("LLM_HARD_TIMEOUT_SECONDS", "15")))
    embedding_model_path: str = field(default_factory=lambda: os.getenv("BGE_EMBEDDING_MODEL", ""))
    reranker_model_path: str = field(default_factory=lambda: os.getenv("BGE_RERANKER_MODEL", ""))
    enable_flag_embedding: bool = field(default_factory=lambda: os.getenv("ENABLE_FLAGEMBEDDING", "1") == "1")
    enable_flag_reranker: bool = field(default_factory=lambda: os.getenv("ENABLE_FLAGRERANKER", "1") == "1")
    embedding_dim: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_DIM", "1024")))
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "500")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "80")))
    pdf_header_ratio: float = field(default_factory=lambda: float(os.getenv("PDF_HEADER_RATIO", "0.1")))
    pdf_footer_ratio: float = field(default_factory=lambda: float(os.getenv("PDF_FOOTER_RATIO", "0.08")))
    pdf_repeated_line_threshold: float = field(default_factory=lambda: float(os.getenv("PDF_REPEATED_LINE_THRESHOLD", "0.6")))
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "6")))
    rerank_top_k: int = field(default_factory=lambda: int(os.getenv("RERANK_TOP_K", "3")))
    min_context_score: float = field(default_factory=lambda: float(os.getenv("MIN_CONTEXT_SCORE", "0.2")))
    hybrid_rrf_k: int = field(default_factory=lambda: int(os.getenv("HYBRID_RRF_K", "60")))
    context_doc_char_limit: int = field(default_factory=lambda: int(os.getenv("CONTEXT_DOC_CHAR_LIMIT", "400")))
    short_term_max_len: int = field(default_factory=lambda: int(os.getenv("SHORT_TERM_MAX_LEN", "20")))
    short_term_ttl: int = field(default_factory=lambda: int(os.getenv("SHORT_TERM_TTL", "3600")))
    conversation_max_messages: int = field(default_factory=lambda: int(os.getenv("CONVERSATION_MAX_MESSAGES", "12")))
    conversation_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("CONVERSATION_TTL_SECONDS", "3600")))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "change-this-secret-key"))
    algorithm: str = field(default_factory=lambda: os.getenv("ALGORITHM", "HS256"))
    access_token_expire_minutes: int = field(default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
