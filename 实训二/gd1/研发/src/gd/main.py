#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# 如果直接运行这个文件，就把 src 目录加入 import 路径，保证能正常导入 gd 包。
if __package__ in {None, ""}:
    current_dir = Path(__file__).resolve().parent
    src_root = current_dir.parent
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

from gd.crew import Gd
from gd.ledger_service import LedgerCrewResponse, OPENING_MESSAGE
from gd.time_utils import get_beijing_time_context


def _read_request_from_cli() -> str:
    # 从命令行参数读取用户首次输入
    if len(sys.argv) > 1:  # 检查是否有命令行参数
        return " ".join(sys.argv[1:]).strip()  # 将所有参数拼接到一起并去除首尾空白
    return ""


def _kickoff_crew(user_request: str) -> LedgerCrewResponse:
    # 组装 CrewAI 所需的输入，并启动一次完整的记账处理流程
    beijing_time = get_beijing_time_context()  # 获取北京时间上下文
    result = Gd().crew().kickoff(
        # 把用户输入和当前时间一起传给 CrewAI，让 agent 按规则处理
        inputs={
            "user_request": user_request,
            "current_beijing_datetime": beijing_time.iso_datetime,
            "current_beijing_date": beijing_time.date,
            "current_beijing_time": beijing_time.time,
            "current_timezone": beijing_time.timezone_name,
        }
    )

    # 统一把 CrewAI 返回结果转成 LedgerCrewResponse，方便后续输出
    payload: dict[str, Any] | None = None
    if getattr(result, "pydantic", None) is not None:
        model_output = result.pydantic
        if isinstance(model_output, LedgerCrewResponse):
            return model_output
        payload = model_output.model_dump()
    elif getattr(result, "json_dict", None):
        payload = result.json_dict
    else:
        raw_text = getattr(result, "raw", str(result))
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return LedgerCrewResponse(
                status="success",
                intent="clarify",
                user_message=str(raw_text).strip(),
                data={},
            )

    return LedgerCrewResponse.model_validate(payload or {})


def _print_result(user_request: str) -> None:
    # 执行 CrewAI 处理，并把最终中文回复打印到控制台
    try:
        result = _kickoff_crew(user_request)
        print(result.user_message)
    except Exception as exc:
        print(f"处理账目时出现异常：{exc}")


def run() -> None:
    """运行记账助手的交互入口。"""
    print(OPENING_MESSAGE)

    # 如果命令行已经带了输入，就直接处理一次并退出
    first_request = _read_request_from_cli()
    if first_request:
        _print_result(first_request)
        return

    # 否则进入循环，持续接收用户输入
    while True:
        try:
            user_request = input("> ").strip()
        except EOFError:
            break

        if not user_request:
            continue
        if user_request.lower() in {"exit", "quit", "退出"}:
            print("记账本已退出，欢迎下次再来。")
            break

        _print_result(user_request)


def train() -> None:
    # 预留给 crewAI 训练入口，当前版本未实现
    raise NotImplementedError("当前版本未提供 crew training 入口。")


def replay() -> None:
    # 预留给 crewAI 回放入口，当前版本未实现
    raise NotImplementedError("当前版本未提供 replay 入口。")


def test() -> None:
    # 预留给项目测试入口，直接提示使用 unittest
    raise NotImplementedError("请使用 `python -m unittest discover tests` 运行当前版本测试。")


def run_with_trigger():
    """用 JSON 触发载荷启动一次处理。"""
    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        raise Exception("Invalid JSON payload provided as argument.") from exc

    user_request = str(trigger_payload.get("user_request", "")).strip()
    if not user_request:
        raise Exception("Trigger payload must contain a non-empty `user_request` field.")

    result = _kickoff_crew(user_request)
    return result.model_dump()


if __name__ == "__main__":
    run()
