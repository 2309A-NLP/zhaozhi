from crewai import Agent, Crew, LLM, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from openai import BadRequestError, OpenAI

from gd.ledger_service import LedgerCrewResponse
from gd.settings import ModelSettings
from gd.tools.custom_tool import (
    AddTransactionTool,
    DeleteTransactionTool,
    QueryTransactionsTool,
)


@CrewBase
class Gd:
    """CrewAI 入口类，负责把 agent、task 和工具组装起来。"""

    agents: list[BaseAgent]
    tasks: list[Task]
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def _validate_model_access(self, model_settings: ModelSettings) -> None:
        # 如果没有自定义 base_url，就直接认为是标准 OpenAI 路径
        if not model_settings.base_url:
            return

        # 先探测模型服务是否真的可用，避免后面 CrewAI 启动时才报错
        client = OpenAI(
            api_key=model_settings.api_key,
            base_url=model_settings.base_url,
        )
        try:
            client.chat.completions.create(
                model=model_settings.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        except BadRequestError as exc:
            raise RuntimeError(
                "模型服务拒绝了当前 .env 配置。"
                f"请检查 MODEL={model_settings.model} 是否是 {model_settings.base_url}/models 返回的真实模型 ID。"
                f" 上游错误：{exc}"
            ) from exc

    def _build_llm(self) -> LLM:
        # 从环境变量读取模型配置并构造 CrewAI 所需的 LLM 实例
        model_settings = ModelSettings.from_env()
        self._validate_model_access(model_settings)
        llm_kwargs = {
            "model": model_settings.crewai_model(),
            "api_key": model_settings.api_key,
        }
        if model_settings.base_url:
            llm_kwargs["base_url"] = model_settings.base_url
        llm = LLM(**llm_kwargs)

        # 某些第三方网关不支持 CrewAI 的原生 function calling，所以强制走 ReAct
        if model_settings.base_url:
            llm.supports_function_calling = lambda: False  # type: ignore[method-assign]

        return llm

    @agent
    def bookkeeper(self) -> Agent:
        # 记账助手 agent，只暴露三个账目工具
        return Agent(
            config=self.agents_config["bookkeeper"],  # type: ignore[index]
            llm=self._build_llm(),
            tools=[
                AddTransactionTool(),
                QueryTransactionsTool(),
                DeleteTransactionTool(),
            ],
            verbose=True,
        )

    @task
    def ledger_task(self) -> Task:
        # 唯一的主任务：处理用户记账请求，并要求输出固定结构
        return Task(
            config=self.tasks_config["ledger_task"],  # type: ignore[index]
            agent=self.bookkeeper(),
            output_pydantic=LedgerCrewResponse,
        )

    @crew
    def crew(self) -> Crew:
        # 按顺序执行任务，当前项目只需要单步顺序处理
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
