from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, before_kickoff, crew, task

from gd2.schemas import ScheduleSqlPlan
from gd2.settings import AppSettings
from gd2.time_utils import get_beijing_now_text


@CrewBase
class Gd2:
    """Chinese secretary crew for schedule SQL planning."""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @before_kickoff
    def prepare_inputs(self, inputs: dict) -> dict:
        prepared_inputs = dict(inputs)
        prepared_inputs["current_beijing_time"] = (
            prepared_inputs.get("current_beijing_time") or get_beijing_now_text()
        )
        return prepared_inputs

    @agent
    def secretary_sql_planner(self) -> Agent:
        return Agent(
            config=self.agents_config["secretary_sql_planner"],  # type: ignore[index]
            llm=AppSettings.from_env().build_llm(),
            verbose=False,
            inject_date=True,
            date_format="%Y-%m-%d %H:%M:%S",
            max_iter=12,
            allow_delegation=False,
        )

    @task
    def schedule_sql_task(self) -> Task:
        return Task(
            config=self.tasks_config["schedule_sql_task"],  # type: ignore[index]
            markdown=False,
        )

    @crew
    def crew(self) -> Crew:
        """Create the secretary crew."""

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=False,
        )
