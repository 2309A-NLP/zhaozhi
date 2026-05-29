"""项目环境变量与运行配置。"""  # 说明当前模块或代码块的用途。

import os  # 导入所需的模块或对象：os。
from pathlib import Path  # 从 pathlib 中导入所需对象。
from urllib.parse import quote_plus  # 从 urllib.parse 中导入所需对象。

from dotenv import load_dotenv  # 从 dotenv 中导入所需对象。


BASE_DIR = Path(__file__).resolve().parent.parent  # 调用 Path 并把结果保存到 BASE_DIR 中。
load_dotenv(BASE_DIR / ".env")  # 调用 load_dotenv 处理当前这一步逻辑。


def _env_int(name: str, default: int) -> int:  # 定义函数 _env_int，用于封装可复用的逻辑。
    """处理_env_int相关逻辑。

    参数：
        name: 当前函数处理的名称键或环境变量名。
        default: 没有明确值时使用的默认回退值。
    """
    return int(os.getenv(name, default))  # 返回当前函数计算出的结果。


def _env_float(name: str, default: float) -> float:  # 定义函数 _env_float，用于封装可复用的逻辑。
    """处理_env_float相关逻辑。

    参数：
        name: 当前函数处理的名称键或环境变量名。
        default: 没有明确值时使用的默认回退值。
    """
    return float(os.getenv(name, default))  # 返回当前函数计算出的结果。


def _env_flag(name: str, default: str = "0") -> bool:  # 定义函数 _env_flag，用于封装可复用的逻辑。
    """处理_env_flag相关逻辑。

    参数：
        name: 当前函数处理的名称键或环境变量名。
        default: 没有明确值时使用的默认回退值。
    """
    return os.getenv(name, default).strip() == "1"  # 返回当前函数计算出的结果。


class Config:  # 定义类 Config，用于组织相关数据和行为。
    APP_NAME = os.getenv("APP_NAME", "角色扮演系统")  # 调用 os.getenv("APP_NAME", "角色扮演系统") 从环境变量中读取 APP_NAME 的值；如果该环境变量不存在，则使用默认值 "角色扮演系统"。结果保存在类属性中，供整个应用使用
    APP_VERSION = os.getenv("APP_VERSION", "1.1.0")  #os.getenv("APP_VERSION", "1.1.0") 从环境变量中读取 APP_VERSION 的值；如果该环境变量不存在，则使用默认值 "1.1.0"。结果保存在类属性中，供整个应用使用

    DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))  # 同上，然后用 Path(...) 将字符串或路径对象包装成 Path 对象
    DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", DATA_DIR / "documents"))  # 同上，然后用 Path(...) 将字符串或路径对象包装成 Path 对象。

    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()  # 同上，调用 .strip() 去除首尾空白字符（防止环境变量中误带空格）。若后续逻辑发现该值非空，会优先使用它。
    MYSQL_HOST = os.getenv("MYSQL_HOST", os.getenv("DOCKER_MYSQL_HOST", "mysql"))  # 同上
    MYSQL_PORT = _env_int("MYSQL_PORT", 3306)  # 同上
    MYSQL_USER = os.getenv("MYSQL_USER", "root")  # 同上
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", os.getenv("MYSQL_ROOT_PASSWORD", "root"))  # 同上
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", os.getenv("MYSQL_DB", "rag_chatbot"))  # 同上

    @property  # 为下面的函数或类添加装饰器。
    def SQLALCHEMY_URL(self) -> str:  # 定义函数 SQLALCHEMY_URL，用于封装可复用的逻辑。
        """处理SQLALCHEMY_URL相关逻辑。
        SQLALCHEMY_URL 是一个存储数据库连接字符串的配置变量
        """
        if self.DATABASE_URL:  # 判断如果用户通过环境变量直接提供了完整的 DATABASE_URL，则直接返回它
            return self.DATABASE_URL
        password = quote_plus(self.MYSQL_PASSWORD)  # 使用 urllib.parse 中的 quote_plus 对密码进行 URL 编码，确保特殊字符（如 @、: 等）不会破坏连接字符串格式
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{password}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    REDIS_HOST = os.getenv("REDIS_HOST", os.getenv("DOCKER_REDIS_HOST", "redis"))
    REDIS_PORT = _env_int("REDIS_PORT", 6379)
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

    MILVUS_HOST = os.getenv("MILVUS_HOST", "192.168.157.129")
    MILVUS_PORT = _env_int("MILVUS_PORT", 19530)
    MILVUS_COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "rag_knowledge")
    MILVUS_CONVERSATION_COLLECTION_NAME = os.getenv("MILVUS_CONVERSATION_COLLECTION_NAME", "rag_conversations")

    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
    LLM_API_KEY = os.getenv("LLM_API_KEY", "EMPTY")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

    BGE_EMBEDDING_MODEL = os.getenv("BGE_EMBEDDING_MODEL", "BAAI/bge-m3")
    BGE_RERANKER_MODEL = os.getenv("BGE_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    ENABLE_FLAGEMBEDDING = _env_flag("ENABLE_FLAGEMBEDDING")
    ENABLE_FLAGRERANKER = _env_flag("ENABLE_FLAGRERANKER")
    EMBEDDING_DIM = _env_int("EMBEDDING_DIM", 1024)
    CHUNK_SIZE = _env_int("CHUNK_SIZE", 500)
    CHUNK_OVERLAP = _env_int("CHUNK_OVERLAP", 80)

    RETRIEVAL_TOP_K = _env_int("RETRIEVAL_TOP_K", 12)
    RERANK_TOP_K = _env_int("RERANK_TOP_K", 5)
    HYBRID_RRF_K = _env_int("HYBRID_RRF_K", 60)  # 重排分数阈值，在混合检索（如同时使用向量召回 + BM25 关键词召回）进行 RRF（Reciprocal Rank Fusion，倒数排名融合） 时，用来计算融合分数的平滑参数 k
    LLM_MAX_TOKENS = _env_int("LLM_MAX_TOKENS", 512)
    LLM_TEMPERATURE = _env_float("LLM_TEMPERATURE", 0.5)
    LLM_MAX_RETRIES = _env_int("LLM_MAX_RETRIES", 1)
    LLM_TIMEOUT_SECONDS = _env_float("LLM_TIMEOUT_SECONDS", 12)
    LLM_HARD_TIMEOUT_SECONDS = _env_float("LLM_HARD_TIMEOUT_SECONDS", 15)
    CONTEXT_DOC_CHAR_LIMIT = _env_int("CONTEXT_DOC_CHAR_LIMIT", 400)

    SHORT_TERM_MAX_LEN = _env_int("SHORT_TERM_MAX_LEN", 20)
    SHORT_TERM_TTL = _env_int("SHORT_TERM_TTL", 3600)

    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 30)

    DEFAULT_ROLE_NAME = os.getenv("DEFAULT_ROLE_NAME", "社交NPC")
    DEFAULT_ROLE_TYPE = os.getenv("DEFAULT_ROLE_TYPE", "friend")

    def ensure_directories(self) -> None:
        """确保directories相关逻辑。  组织和存储文件
        这个函数作用确保DATA_DIR和 DOCUMENTS_DIR这两个目录存在
        """
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
config.ensure_directories()
