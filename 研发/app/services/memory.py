"""管理会话短期记忆与 Redis 回退逻辑。"""  # 说明当前模块或代码块的用途。
from __future__ import annotations  # 从 __future__ 中导入所需对象。

import json  # 导入所需的模块或对象：json。
from collections import defaultdict  # 从 collections 中导入所需对象。
from datetime import datetime  # 从 datetime 中导入所需对象。
from typing import Dict, List  # 从 typing 中导入所需对象。

try:  # 开始尝试执行可能出错的代码。
    import redis.asyncio as redis  # 导入所需的模块或对象：redis.asyncio。
except Exception:  # 捕获并处理前面代码抛出的异常。
    redis = None  # 设置 redis 的值，供后续逻辑使用。


def _decode_messages(messages: List[str]) -> List[Dict]:  # 定义函数 _decode_messages，用于封装可复用的逻辑。
    """处理_decode_messages相关逻辑。

    参数：
        messages: 当前函数处理的聊天消息列表。
    """
    # 将json格式的字符串的列表转换对对应的Python字典的对象列表，常用于将存储或传输中的序列化消息数据还原为可操作的结构化数据，便于后续处理。
    return [json.loads(message) for message in messages]


class MemoryService:
    _memory_store: Dict[str, List[str]] = defaultdict(list)  # 声明并创建一个字典 _memory_store，其键是字符串，值是字符串列表；当访问不存在的键时，自动用空列表作为默认值。

    def __init__(self, host: str, port: int, password: str | None = None):
        self.client = None
        if redis is None:
            return
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                password=password,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        except Exception:
            self.client = None

    def get_session_key(self, user_id: int, role_id: int, session_id: str) -> str:  # 定义函数 get_session_key，用于封装可复用的逻辑。

        return f"session:{user_id}:{role_id}:{session_id}"  # 根据传入的 user_id、role_id 和 session_id 生成一个统一的、格式化的字符串键（key），作用是便于缓存（如 Redis）或键值存储中唯一标识某个用户的特定角色所对应的会话

    async def push_message(
        self,
        user_id: int,
        role_id: int,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
        max_len: int = 20,
    ):

        key = self.get_session_key(user_id, role_id, session_id)  # 生成一个统一的、格式化的字符串键
        message_pair = json.dumps(   #  json.dumps是将序列化为 JSON 字符串
            {
                "user": user_msg,
                "assistant": assistant_msg,
                "timestamp": datetime.now().isoformat(),
            },
            ensure_ascii=False,   # ensure_ascii=False 保留非ASCII字符（如中文）。
        )  # 将用户消息和助手消息打包成一个字典，并添加当前时间戳（ISO格式）。
        if self.client is not None:
            try:
                await self.client.rpush(key, message_pair)  # 将 message_pair 追加到键 key 对应的列表右侧。这样会把最新消息添加到列表末尾
                await self.client.ltrim(key, -max_len, -1)  # 只保留列表中索引从 -max_len 到 -1 的元素。这样做是为了只保留最新的 max_len 条消息对，超出部分的旧数据被自动删除
                return
            except Exception:
                self.client = None

        bucket = self._memory_store[key]
        bucket.append(message_pair)
        if len(bucket) > max_len:
            del bucket[:-max_len]

    async def get_recent_messages(
        self,
        user_id: int,
        role_id: int,
        session_id: str,
        n: int = 5,
    ) -> List[Dict]:

        key = self.get_session_key(user_id, role_id, session_id)  # 生成一个统一的、格式化的字符串键
        if self.client is not None:
            try:
                return _decode_messages(await self.client.lrange(key, -n, -1))  # 异步请求 Redis，获取列表 key 中倒数第 n 个到最后一个元素（即最近 n 条消息）
            except Exception:
                self.client = None
        return _decode_messages(self._memory_store.get(key, [])[-n:])  # 在 Redis 不可用时，从本地内存存储中提取该会话的聊天记录，并截取最后 n 条返回。

    async def get_full_conversation(self, user_id: int, role_id: int, session_id: str) -> List[Dict]:  # 定义异步函数 get_full_conversation，用于封装可复用的异步逻辑。
        """获取fullconversation相关逻辑。

        参数：
            user_id: 当前函数使用的用户 ID。
            role_id: 当前函数使用的角色 ID。
            session_id: 当前函数使用的会话 ID。
        """
        key = self.get_session_key(user_id, role_id, session_id)  # # 生成一个统一的、格式化的字符串键
        if self.client is not None:  # 根据条件决定是否执行下面的代码块。
            try:  # 开始尝试执行可能出错的代码。
                return _decode_messages(await self.client.lrange(key, 0, -1))  # 返回当前函数计算出的结果。
            except Exception:  # 捕获并处理前面代码抛出的异常。
                self.client = None  # 设置 self.client 的值，供后续逻辑使用。
        return _decode_messages(self._memory_store.get(key, []))  # 返回当前函数计算出的结果。

    async def clear_session(self, user_id: int, role_id: int, session_id: str):  #

        key = self.get_session_key(user_id, role_id, session_id)  # 生成一个统一的、格式化的字符串键
        if self.client is not None:  #
            try:  #
                await self.client.delete(key)  #
                return  #
            except Exception:  #
                self.client = None  #
        self._memory_store.pop(key, None)  #

    async def set_ttl(self, user_id: int, role_id: int, session_id: str, ttl: int = 3600):

        key = self.get_session_key(user_id, role_id, session_id) # 生成一个统一的、格式化的字符串键
        if self.client is not None:
            try:
                await self.client.expire(key, ttl)  # 调用 Redis 的 EXPIRE 命令，将 key 的生存时间设置为 ttl 秒。过期后，Redis 会自动删除该键。
            except Exception:
                self.client = None
