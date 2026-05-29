"""封装兼容 OpenAI 接口的大模型调用逻辑。"""  # 说明当前模块或代码块的用途。
from __future__ import annotations  # 从 __future__ 中导入所需对象。

import re  # 导入所需的模块或对象：re。
import time  # 导入所需的模块或对象：time。
from typing import List  # 从 typing 中导入所需对象。
from urllib.parse import urlparse  # 从 urllib.parse 中导入所需对象。

try:  # 开始尝试执行可能出错的代码。
    from openai import OpenAI  # 从 openai 中导入所需对象。
except Exception:  # 捕获并处理前面代码抛出的异常。
    OpenAI = None  # 设置 OpenAI 的值，供后续逻辑使用。


class LLMClient:  # 定义类 LLMClient，用于组织相关数据和行为。
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 45):  # 定义函数 __init__，用于封装可复用的逻辑。
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            base_url: 当前函数使用的基础 URL。
            api_key: 当前函数使用的 API Key。
            model: 当前函数使用的模型名或模型标识。
            timeout: 当前函数使用的超时时间。
        """
        self.model = model  # 设置 self.model 的值，供后续逻辑使用。
        self.timeout = timeout  # 设置 self.timeout 的值，供后续逻辑使用。
        self.base_url = (base_url or "").strip()  # 设置 self.base_url 的值，供后续逻辑使用。
        self.client = self._build_client(api_key)  # 调用 self._build_client 并把结果保存到 self.client 中。

    def _build_client(self, api_key: str):  # 定义函数 _build_client，用于封装可复用的逻辑。
        """处理_build_client相关逻辑。

        参数：
            api_key: 当前函数使用的 API Key。
        """
        if self._looks_like_local_backend_loop(self.base_url) or OpenAI is None:  # 根据条件决定是否执行下面的代码块。
            return None  # 返回当前函数计算出的结果。
        try:  # 开始尝试执行可能出错的代码。
            client_kwargs = {"api_key": api_key, "timeout": self.timeout, "max_retries": 0}  # 设置 client_kwargs 的值，供后续逻辑使用。
            if self.base_url:  # 根据条件决定是否执行下面的代码块。
                client_kwargs["base_url"] = self.base_url  # 执行这一行代码，完成当前逻辑。
            return OpenAI(**client_kwargs)  # 返回当前函数计算出的结果。
        except Exception:  # 捕获并处理前面代码抛出的异常。
            return None  # 返回当前函数计算出的结果。

    @staticmethod  # 为下面的函数或类添加装饰器。
    def _looks_like_local_backend_loop(base_url: str) -> bool:  # 定义函数 _looks_like_local_backend_loop，用于封装可复用的逻辑。
        """处理_looks_like_local_backend_loop相关逻辑。

        参数：
            base_url: 当前函数使用的基础 URL。
        """
        parsed = urlparse(base_url)  # 调用 urlparse 并把结果保存到 parsed 中。
        return (  # 返回当前函数计算出的结果。
            (parsed.hostname or "").lower() in {"127.0.0.1", "localhost"}  # 执行这一行代码，完成当前逻辑。
            and parsed.port == 8000  # 执行这一行代码，完成当前逻辑。
            and parsed.path.rstrip("/") == "/v1"  # 执行这一行代码，完成当前逻辑。
        )  # 结束当前列表、字典、元组、调用或代码块。

    def _is_deepseek(self) -> bool:  # 定义函数 _is_deepseek，用于封装可复用的逻辑。
        """处理_is_deepseek相关逻辑。
        """
        return "api.deepseek.com" in self.base_url.lower()  # 返回当前函数计算出的结果。

    @staticmethod  # 为下面的函数或类添加装饰器。
    def _extract_context(user_content: str) -> str:  # 定义函数 _extract_context，用于封装可复用的逻辑。
        """处理_extract_context相关逻辑。

        参数：
            user_content: 当前函数使用的输入参数。
        """
        knowledge_match = re.search(r"【相关知识】(.*?)(【对话历史】|$)", user_content, re.S)  # 调用 re.search 并把结果保存到 knowledge_match 中。
        return knowledge_match.group(1).strip() if knowledge_match else ""  # 返回当前函数计算出的结果。

    @staticmethod  # 为下面的函数或类添加装饰器。
    def _extract_latest_question(user_content: str) -> str:  # 定义函数 _extract_latest_question，用于封装可复用的逻辑。
        """处理_extract_latest_question相关逻辑。

        参数：
            user_content: 当前函数使用的输入参数。
        """
        marker = "用户最新消息："  # 设置 marker 的值，供后续逻辑使用。
        return user_content.split(marker, 1)[1].strip() if marker in user_content else user_content.strip()  # 返回当前函数计算出的结果。

    def _fallback_answer(self, messages: List[dict]) -> str:  # 定义函数 _fallback_answer，用于封装可复用的逻辑。
        """处理_fallback_answer相关逻辑。

        参数：
            messages: 当前函数处理的聊天消息列表。
        """
        user_content = messages[-1]["content"] if messages else ""  # 设置 user_content 的值，供后续逻辑使用。
        context = self._extract_context(user_content)  # 调用 self._extract_context 并把结果保存到 context 中。
        latest_question = self._extract_latest_question(user_content)  # 调用 self._extract_latest_question 并把结果保存到 latest_question 中。

        if context:  # 根据条件决定是否执行下面的代码块。
            snippets = [line.strip() for line in context.splitlines() if line.strip()]  # 设置 snippets 的值，供后续逻辑使用。
            summary = "；".join(snippets[:3])  # 设置 summary 的值，供后续逻辑使用。
            return f"基于当前检索到的知识，我的回答是：{summary}\n\n如果你希望我进一步展开，我可以继续围绕“{latest_question}”详细说明。"  # 返回当前函数计算出的结果。

        return f"我暂时无法连接到大模型服务，但可以先基于现有上下文继续协助你。你刚才的问题是：{latest_question}"  # 返回当前函数计算出的结果。

    def chat(self, messages, temperature=0.5, max_tokens=768, stream=False):  # 定义函数 chat，用于封装可复用的逻辑。
        """处理一次聊天相关操作。

        参数：
            messages: 当前函数处理的聊天消息列表。
            temperature: 生成时使用的采样温度。
            max_tokens: 生成时允许的最大 token 数。
            stream: 当前调用是否启用流式模式。
        """
        if self.client is None:  # 根据条件决定是否执行下面的代码块。
            return self._fallback_answer(messages)  # 返回当前函数计算出的结果。

        try:  # 开始尝试执行可能出错的代码。
            extra_kwargs = {}  # 设置 extra_kwargs 的值，供后续逻辑使用。
            if self._is_deepseek() and "reasoner" not in self.model.lower():  # 根据条件决定是否执行下面的代码块。
                extra_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}  # 执行这一行代码，完成当前逻辑。

            response = self.client.chat.completions.create(  # 调用 self.client.chat.completions.create 并把结果保存到 response 中。
                model=self.model,  # 设置 model 的值，供后续逻辑使用。
                messages=messages,  # 设置 messages 的值，供后续逻辑使用。
                temperature=temperature,  # 设置 temperature 的值，供后续逻辑使用。
                max_tokens=max_tokens,  # 设置 max_tokens 的值，供后续逻辑使用。
                stream=stream,  # 设置 stream 的值，供后续逻辑使用。
                **extra_kwargs,  # 执行这一行代码，完成当前逻辑。
            )  # 结束当前列表、字典、元组、调用或代码块。
            return response if stream else (response.choices[0].message.content or "")  # 返回当前函数计算出的结果。
        except Exception:  # 捕获并处理前面代码抛出的异常。
            return self._fallback_answer(messages)  # 返回当前函数计算出的结果。

    def chat_with_retry(self, messages, max_retries=1, temperature=0.5, max_tokens=768):  # 定义函数 chat_with_retry，用于封装可复用的逻辑。
        """处理chat_with_retry相关逻辑。

        参数：
            messages: 当前函数处理的聊天消息列表。
            max_retries: 当前函数使用的输入参数。
            temperature: 生成时使用的采样温度。
            max_tokens: 生成时允许的最大 token 数。
        """
        for retry in range(max_retries):  # 遍历目标数据中的每一项。
            result = self.chat(messages, temperature=temperature, max_tokens=max_tokens)  # 调用 self.chat 并把结果保存到 result 中。
            if result:  # 根据条件决定是否执行下面的代码块。
                return result  # 返回当前函数计算出的结果。
            if retry < max_retries - 1:  # 根据条件决定是否执行下面的代码块。
                time.sleep(2 ** retry)  # 调用 time.sleep 处理当前这一步逻辑。
        return self._fallback_answer(messages)  # 返回当前函数计算出的结果。
