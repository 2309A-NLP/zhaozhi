from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录，用来定位 .env 文件
ROOT_DIR = Path(__file__).resolve().parents[2]


def load_project_env() -> None:
    # 把项目根目录下的 .env 加载到当前进程环境变量中
    load_dotenv(ROOT_DIR / ".env")


def read_env(name: str, *aliases: str) -> str:
    # 读取必填环境变量，也支持多个备选名字
    load_project_env()
    for key in (name, *aliases):
        value = os.getenv(key)
        if value:
            return value
    raise RuntimeError(f"Missing required environment variable: {name}")


def read_optional_env(name: str, *aliases: str) -> str | None:
    # 读取可选环境变量，如果都没有就返回 None
    load_project_env()
    for key in (name, *aliases):
        value = os.getenv(key)
        if value:
            return value
    return None


@dataclass(frozen=True)
class ModelSettings:
    # 保存模型调用所需配置
    model: str
    api_key: str
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> "ModelSettings":
        # 从环境变量中读取模型相关配置
        return cls(
            model=read_env("MODEL"),
            api_key=read_env("MODEL_API_KEY", "MDDEL_API_KEY", "OPENAI_API_KEY"),
            base_url=read_optional_env("MODEL_URL", "OPENAI_BASE_URL"),
        )

    def crewai_model(self) -> str:
        # 当前项目直接把环境变量里的模型 ID 原样传给 CrewAI
        return self.model
