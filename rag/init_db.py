"""Initialize database schema."""
import asyncio

from app.database.mysql_client import mysql_client


async def init_database():
    """初始化数据库结构。
    """
    try:
        print("正在初始化数据库...")
        await mysql_client.init_db()
        print("数据库初始化完成")
        print("该脚本只初始化表结构，不会自动创建默认账号。")
    finally:
        await mysql_client.close()


if __name__ == "__main__":
    asyncio.run(init_database())
