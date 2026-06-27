import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from crewai import LLM


load_dotenv()


@dataclass(frozen=True)
class AppSettings:
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    model: str
    model_url: str | None
    model_api_key: str | None

    @classmethod
    def from_env(cls) -> "AppSettings":
        mysql_host = os.getenv("MYSQL_HOST", "").strip()
        mysql_user = os.getenv("MYSQL_USER", "").strip()
        mysql_database = os.getenv("MYSQL_DATABASE", "").strip()

        if not mysql_host or not mysql_user or not mysql_database:
            raise ValueError("MYSQL_HOST、MYSQL_USER、MYSQL_DATABASE 必须在 .env 中配置。")

        return cls(
            mysql_host=mysql_host,
            mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
            mysql_user=mysql_user,
            mysql_password=os.getenv("MYSQL_PASSWORD", ""),
            mysql_database=mysql_database,
            model=os.getenv("MODEL", "gpt-4o-mini").strip(),
            model_url=os.getenv("MODEL_URL", "").strip() or None,
            model_api_key=(
                os.getenv("MODEL_API_KEY", "").strip()
                or os.getenv("MDDEL_API_KEY", "").strip()
                or os.getenv("OPENAI_API_KEY", "").strip()
                or None
            ),
        )

    def build_llm(self) -> "LLM":
        """Build an OpenAI-compatible CrewAI LLM from .env values."""

        from crewai import LLM

        return LLM(
            model=self.model,
            api_key=self.model_api_key,
            base_url=self.model_url,
            provider="openai",
            temperature=0,
        )
