"""异步数据库客户端、模式初始化与会话工厂."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import config
from .models import Base


class MySQLClient:
    def __init__(self):
        """初始化对象，准备后续逻辑所需的依赖。
        """
        self.engine = create_async_engine(config.SQLALCHEMY_URL, **self._build_engine_kwargs())
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @staticmethod
    def _build_engine_kwargs():
        """处理_build_engine_kwargs相关逻辑。
        """
        if config.SQLALCHEMY_URL.startswith("sqlite+aiosqlite"):
            return {"echo": False, "connect_args": {"check_same_thread": False}}
        return {"echo": False, "pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}

    async def _migrate_roles_schema(self, conn) -> None:
        """处理_migrate_roles_schema相关逻辑。

        参数：
            conn: 当前函数使用的数据库连接。
        """
        if self.engine.url.get_backend_name().startswith("sqlite"):
            columns = await conn.execute(text("PRAGMA table_info(roles)"))
            role_columns = {row[1]: row[2] for row in columns.fetchall()}
            role_type_type = str(role_columns.get("role_type", "")).upper()
            if role_type_type != "VARCHAR(100)":
                await conn.execute(text("DROP INDEX IF EXISTS idx_role_user_id"))
                await conn.execute(text("DROP INDEX IF EXISTS idx_role_type"))
                await conn.execute(text("ALTER TABLE roles RENAME TO roles_old"))
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(
                    text(
                        """
                        INSERT INTO roles (
                            id, user_id, role_name, role_type, personality,
                            language_style, constraints, system_prompt,
                            knowledge_domains, is_public, created_at, updated_at
                        )
                        SELECT
                            id, user_id, role_name, role_type, personality,
                            language_style, constraints, system_prompt,
                            knowledge_domains, is_public, created_at, updated_at
                        FROM roles_old
                        """
                    )
                )
                await conn.execute(text("DROP TABLE roles_old"))

    async def init_db(self):
        """初始化数据库结构和相关配置。
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if self.engine.url.get_backend_name().startswith("mysql"):
                await conn.execute(text("ALTER TABLE documents MODIFY COLUMN content LONGTEXT NOT NULL"))
            await self._migrate_roles_schema(conn)

    async def close(self):
        """处理close相关逻辑。
        """
        await self.engine.dispose()


mysql_client = MySQLClient()


async def get_db():
    """获取db相关逻辑。
    """
    async with mysql_client.async_session_maker() as session:   # 先执行这一步，创建一个 AsyncSession（异步会话）
        # 这个异步会话的作用是为你提供一个安全的、能执行 SQL 的临时工作空间，你可以在里面做任何数据库查询和修改，不需要关心连接是怎么来的、用完怎么还，
        # 这一切都由 async with 和 FastAPI 的依赖机制自动保证了
        yield session    # 让 FastAPI 可以把数据库会话交给接口函数（也就是[app/api/chat.py] `chat(...)` 中的 db: AsyncSession = Depends(get_db)）
        # 使用，并确保请求结束后自动关闭会话。
