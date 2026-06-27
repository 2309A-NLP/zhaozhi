#!/usr/bin/env python
import json
import os
import sys
import warnings

if __package__ in {None, ""}:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gd2.crew import Gd2
from gd2.database import ExecutionResult, MySQLScheduleRepository
from gd2.planner import extract_plan
from gd2.presenter import format_result
from gd2.session import SessionState
from gd2.settings import AppSettings
from gd2.time_utils import get_beijing_now_text

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

OPENING_MESSAGE = (
    '您好，我是您的私人秘书，请按照“ 添加/删除日程，x 年 x 月 x 日 x 时要做什么事 ”的格式来输入。'
)
EXIT_COMMANDS = {"退出", "exit", "quit", "q"}

def process_user_request(user_request: str, state: SessionState | None = None) -> ExecutionResult:
    state = state or SessionState()
    beijing_now = get_beijing_now_text()
    repository = MySQLScheduleRepository(AppSettings.from_env())

    manual_plan = state.build_delete_by_index_plan(user_request)
    if manual_plan is not None:
        execution = repository.execute_plan(manual_plan, user_request)
        print(format_result(manual_plan, execution, beijing_now))
        print("请继续输入下一条命令，输入 退出 可结束程序。")
        return execution

    inputs = {
        "user_request": user_request.strip(),
        "current_beijing_time": beijing_now,
    }
    result = Gd2().crew().kickoff(inputs=inputs)
    plan = extract_plan(result)
    execution = repository.execute_plan(plan, user_request)
    if plan.action == "query":
        state.remember_query_rows(execution.rows)
    print(format_result(plan, execution, beijing_now))
    print("请继续输入下一条命令，输入 退出 可结束程序。")
    return execution


def run():
    state = SessionState()
    print(OPENING_MESSAGE)
    while True:
        try:
            user_request = input().strip()
            if not user_request:
                print("请输入有效的日程指令。")
                continue
            if user_request.lower() in EXIT_COMMANDS or user_request in EXIT_COMMANDS:
                print("程序已退出。")
                break
            process_user_request(user_request, state)
        except KeyboardInterrupt:
            print("\n程序已退出。")
            break
        except EOFError:
            print("\n程序已退出。")
            break
        except Exception as e:
            print(f"处理失败：{e}")
            print("请继续输入下一条命令，输入 退出 可结束程序。")


def train():
    inputs = {
        "user_request": "取消日程 1",
        "current_beijing_time": get_beijing_now_text(),
    }
    try:
        Gd2().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    try:
        Gd2().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    inputs = {
        "user_request": "查询今天的日程",
        "current_beijing_time": get_beijing_now_text(),
    }
    try:
        Gd2().crew().test(
            n_iterations=int(sys.argv[1]),
            eval_llm=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def run_with_trigger():
    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        raise Exception("Invalid JSON payload provided as argument") from exc

    try:
        user_request = str(trigger_payload.get("user_request", "")).strip()
        if not user_request:
            raise ValueError("Trigger payload 必须包含 user_request。")
        return process_user_request(user_request, SessionState())
    except Exception as e:
        raise Exception(f"An error occurred while running the crew with trigger: {e}")


if __name__ == "__main__":
    run()
