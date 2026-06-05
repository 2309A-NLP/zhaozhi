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


def load_int(name: str, default: int, minimum: int | None = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    if minimum is not None:
        return max(minimum, value)
    return value


def load_float(name: str, default: float, minimum: float | None = None) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    if minimum is not None:
        return max(minimum, value)
    return value


def load_optional_bool(name: str) -> bool | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return None
    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def load_first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


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
    mysql_port: int = field(default_factory=lambda: load_int("MYSQL_PORT", 3306, minimum=1))
    mysql_user: str = field(default_factory=lambda: os.getenv("MYSQL_USER", "root"))
    mysql_password: str = field(default_factory=lambda: os.getenv("MYSQL_PASSWORD", ""))
    mysql_database: str = field(default_factory=lambda: os.getenv("MYSQL_DATABASE", "rag_qa_system"))
    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "127.0.0.1"))
    redis_port: int = field(default_factory=lambda: load_int("REDIS_PORT", 6379, minimum=1))
    redis_password: str = field(default_factory=lambda: os.getenv("REDIS_PASSWORD", ""))
    milvus_host: str = field(default_factory=lambda: os.getenv("MILVUS_HOST", "127.0.0.1"))
    milvus_port: int = field(default_factory=lambda: load_int("MILVUS_PORT", 19530, minimum=1))
    milvus_database: str = field(default_factory=lambda: os.getenv("MILVUS_DATABASE", "gd"))
    milvus_collection_name: str = field(default_factory=lambda: os.getenv("MILVUS_COLLECTION_NAME", "rag_chunks"))
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1/chat/completions")
    )
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "Pro/zai-org/GLM-4.7"))
    llm_max_tokens: int = field(default_factory=lambda: load_int("LLM_MAX_TOKENS", 512, minimum=1))
    llm_temperature: float = field(default_factory=lambda: load_float("LLM_TEMPERATURE", 0.5, minimum=0.0))
    llm_max_retries: int = field(default_factory=lambda: load_int("LLM_MAX_RETRIES", 1, minimum=1))
    llm_timeout_seconds: int = field(default_factory=lambda: load_int("LLM_TIMEOUT_SECONDS", 12, minimum=1))
    llm_hard_timeout_seconds: int = field(default_factory=lambda: load_int("LLM_HARD_TIMEOUT_SECONDS", 15, minimum=1))
    llm_enable_thinking: bool | None = field(default_factory=lambda: load_optional_bool("LLM_ENABLE_THINKING"))
    pdf_parser_mode: str = field(default_factory=lambda: os.getenv("PDF_PARSER_MODE", "local"))
    pdf_llm_base_url: str = field(
        default_factory=lambda: os.getenv("PDF_LLM_BASE_URL", "https://api.siliconflow.cn/v1/chat/completions")
    )
    pdf_llm_api_key: str = field(default_factory=lambda: os.getenv("PDF_LLM_API_KEY", os.getenv("SILICONFLOW_API_KEY", "")))
    pdf_llm_model: str = field(default_factory=lambda: os.getenv("PDF_LLM_MODEL", "Pro/zai-org/GLM-4.7"))
    pdf_llm_max_tokens: int = field(default_factory=lambda: load_int("PDF_LLM_MAX_TOKENS", 768, minimum=1))
    pdf_llm_temperature: float = field(default_factory=lambda: load_float("PDF_LLM_TEMPERATURE", 0.2, minimum=0.0))
    pdf_llm_max_retries: int = field(default_factory=lambda: load_int("PDF_LLM_MAX_RETRIES", 2, minimum=1))
    pdf_llm_timeout_seconds: int = field(default_factory=lambda: load_int("PDF_LLM_TIMEOUT_SECONDS", 90, minimum=1))
    pdf_llm_chunk_chars: int = field(default_factory=lambda: load_int("PDF_LLM_CHUNK_CHARS", 6000, minimum=100))
    pdf_llm_chunk_overlap: int = field(default_factory=lambda: load_int("PDF_LLM_CHUNK_OVERLAP", 600, minimum=0))
    pdf_vision_base_url: str = field(
        default_factory=lambda: load_first_env(
            "PDF_VISION_BASE_URL",
            "PDF_LLM_BASE_URL",
            default="https://api.siliconflow.cn/v1/chat/completions",
        )
    )
    pdf_vision_api_key: str = field(
        default_factory=lambda: load_first_env("PDF_VISION_API_KEY", "PDF_LLM_API_KEY", "SILICONFLOW_API_KEY")
    )
    pdf_vision_model: str = field(default_factory=lambda: os.getenv("PDF_VISION_MODEL", "Qwen/Qwen3-VL-8B-Instruct"))
    pdf_vision_max_tokens: int = field(default_factory=lambda: load_int("PDF_VISION_MAX_TOKENS", 2048, minimum=1))
    pdf_vision_temperature: float = field(default_factory=lambda: load_float("PDF_VISION_TEMPERATURE", 0.1, minimum=0.0))
    pdf_vision_max_retries: int = field(default_factory=lambda: load_int("PDF_VISION_MAX_RETRIES", 1, minimum=1))
    pdf_vision_timeout_seconds: int = field(default_factory=lambda: load_int("PDF_VISION_TIMEOUT_SECONDS", 60, minimum=1))
    pdf_vision_max_pages: int = field(default_factory=lambda: load_int("PDF_VISION_MAX_PAGES", 12, minimum=0))
    pdf_vision_render_scale: float = field(default_factory=lambda: load_float("PDF_VISION_RENDER_SCALE", 3.0, minimum=1.0))
    pdf_vision_target_pages: str = field(default_factory=lambda: os.getenv("PDF_VISION_TARGET_PAGES", ""))
    pdf_auto_hybrid_max_pages: int = field(default_factory=lambda: load_int("PDF_AUTO_HYBRID_MAX_PAGES", 80, minimum=1))
    pdf_auto_hybrid_max_chars: int = field(default_factory=lambda: load_int("PDF_AUTO_HYBRID_MAX_CHARS", 120000, minimum=1000))
    embedding_model_path: str = field(default_factory=lambda: os.getenv("BGE_EMBEDDING_MODEL", ""))
    reranker_model_path: str = field(default_factory=lambda: os.getenv("BGE_RERANKER_MODEL", ""))
    enable_flag_embedding: bool = field(default_factory=lambda: os.getenv("ENABLE_FLAGEMBEDDING", "1") == "1")
    enable_flag_reranker: bool = field(default_factory=lambda: os.getenv("ENABLE_FLAGRERANKER", "1") == "1")
    embedding_dim: int = field(default_factory=lambda: load_int("EMBEDDING_DIM", 1024, minimum=1))
    chunk_size: int = field(default_factory=lambda: load_int("CHUNK_SIZE", 500, minimum=100))
    chunk_overlap: int = field(default_factory=lambda: load_int("CHUNK_OVERLAP", 80, minimum=0))
    retrieval_top_k: int = field(default_factory=lambda: load_int("RETRIEVAL_TOP_K", 6, minimum=1))
    rerank_top_k: int = field(default_factory=lambda: load_int("RERANK_TOP_K", 3, minimum=1))
    hybrid_rrf_k: int = field(default_factory=lambda: load_int("HYBRID_RRF_K", 60, minimum=1))
    context_doc_char_limit: int = field(default_factory=lambda: load_int("CONTEXT_DOC_CHAR_LIMIT", 1200, minimum=100))
    short_term_max_len: int = field(default_factory=lambda: load_int("SHORT_TERM_MAX_LEN", 20, minimum=1))
    short_term_ttl: int = field(default_factory=lambda: load_int("SHORT_TERM_TTL", 3600, minimum=1))
    max_upload_bytes: int = field(default_factory=lambda: load_int("MAX_UPLOAD_BYTES", 50 * 1024 * 1024, minimum=1024))
    max_request_body_bytes: int = field(default_factory=lambda: load_int("MAX_REQUEST_BODY_BYTES", 80 * 1024 * 1024, minimum=1024))
    log_max_bytes: int = field(default_factory=lambda: load_int("LOG_MAX_BYTES", 5 * 1024 * 1024, minimum=1024))
    log_backup_count: int = field(default_factory=lambda: load_int("LOG_BACKUP_COUNT", 5, minimum=1))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "change-this-secret-key"))
    algorithm: str = field(default_factory=lambda: os.getenv("ALGORITHM", "HS256"))
    access_token_expire_minutes: int = field(default_factory=lambda: load_int("ACCESS_TOKEN_EXPIRE_MINUTES", 30, minimum=1))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: load_int("PORT", 8000, minimum=1))
