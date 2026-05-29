"""RAGAS evaluation script for the current FastAPI chat service."""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from datasets import Dataset


DEFAULT_CASES_FILE = Path(__file__).with_name("ragas_cases.json")
DEFAULT_BASE_URL = os.getenv("RAG_API_BASE", "http://127.0.0.1:8000")
DEFAULT_USERNAME = os.getenv("RAG_TEST_USERNAME", "ragas_eval_user")
DEFAULT_PASSWORD = os.getenv("RAG_TEST_PASSWORD", "ChangeMe123")
DEFAULT_EMAIL = os.getenv("RAG_TEST_EMAIL", "ragas_eval_user@example.com")
DEFAULT_ROLE_ID = int(os.getenv("RAG_TEST_ROLE_ID", "0"))
DEFAULT_TIMEOUT = float(os.getenv("RAG_TEST_TIMEOUT", "120"))
DEFAULT_AUTO_REGISTER = os.getenv("RAG_TEST_AUTO_REGISTER", "1").strip() == "1"
DEFAULT_KNOWLEDGE_DOMAINS = [
    item.strip()
    for item in os.getenv("RAG_TEST_KNOWLEDGE_DOMAINS", "general,medical,legal,finance").split(",")
    if item.strip()
]


@dataclass
class EvalCase:
    question: str
    ground_truth: str


@dataclass
class ChatEvalResult:
    question: str
    ground_truth: str
    answer: str
    contexts: list[str]
    session_id: str
    retrieved_docs_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="调用当前项目聊天接口并执行 RAGAS 评测。")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="后端服务地址，例如 http://127.0.0.1:8000")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="测试账号用户名")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="测试账号密码")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="测试账号邮箱")
    parser.add_argument("--role-id", type=int, default=DEFAULT_ROLE_ID, help="聊天接口使用的角色 ID，默认 0")
    parser.add_argument(
        "--knowledge-domains",
        default=",".join(DEFAULT_KNOWLEDGE_DOMAINS),
        help="临时角色覆盖使用的知识域，逗号分隔；留空则不传 knowledge_domains",
    )
    parser.add_argument(
        "--cases-file",
        default=str(DEFAULT_CASES_FILE),
        help="评测样例文件路径，JSON 数组格式，每项包含 question 和 ground_truth",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="单次聊天请求超时时间，单位秒")
    parser.add_argument(
        "--results-file",
        default="",
        help="可选，将评测结果输出为 JSON 文件",
    )
    parser.add_argument(
        "--auto-register",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_AUTO_REGISTER,
        help="登录失败时是否自动注册测试账号",
    )
    return parser.parse_args()


def load_eval_cases(cases_file: str) -> list[EvalCase]:
    path = Path(cases_file)
    if not path.exists():
        raise FileNotFoundError(f"未找到评测样例文件：{path}")

    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("评测样例文件必须是非空 JSON 数组")

    cases: list[EvalCase] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条样例格式错误，必须是对象")
        question = str(item.get("question", "")).strip()
        ground_truth = str(item.get("ground_truth", "")).strip()
        if not question or not ground_truth:
            raise ValueError(f"第 {index} 条样例缺少 question 或 ground_truth")
        cases.append(EvalCase(question=question, ground_truth=ground_truth))
    return cases


def import_evaluation_dependencies():
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "缺少评测依赖，请先在项目环境中安装 requirements.txt，至少需要 datasets 和 ragas。"
        ) from exc
    return Dataset, evaluate, answer_relevancy, context_precision, context_recall, faithfulness


def normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def build_role_override(knowledge_domains_text: str) -> dict[str, Any] | None:
    domains = [item.strip() for item in knowledge_domains_text.split(",") if item.strip()]
    if not domains:
        return None
    return {
        "role_name": "评测助手",
        "role_type": "assistant",
        "knowledge_domains": domains,
        "is_public": False,
    }


def extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text

    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message")
        if isinstance(detail, str) and detail.strip():
            return detail
        return json.dumps(payload, ensure_ascii=False)
    return str(payload)


def login(session: requests.Session, base_url: str, username: str, password: str, timeout: float) -> str:
    response = session.post(
        f"{base_url}/api/auth/token",
        data={"username": username, "password": password},
        timeout=timeout,
    )
    if response.ok:
        data = response.json()
        token = data.get("access_token", "").strip()
        if token:
            return token
    raise RuntimeError(f"登录失败：{extract_error_message(response)}")


def register(session: requests.Session, base_url: str, username: str, password: str, email: str, timeout: float) -> None:
    response = session.post(
        f"{base_url}/api/auth/register",
        json={"username": username, "password": password, "email": email},
        timeout=timeout,
    )
    if response.ok or response.status_code == 201:
        return
    raise RuntimeError(f"注册失败：{extract_error_message(response)}")


def ensure_token(
    session: requests.Session,
    *,
    base_url: str,
    username: str,
    password: str,
    email: str,
    timeout: float,
    auto_register: bool,
) -> str:
    try:
        return login(session, base_url, username, password, timeout)
    except RuntimeError as login_error:
        if not auto_register:
            raise
        register(session, base_url, username, password, email, timeout)
        try:
            return login(session, base_url, username, password, timeout)
        except RuntimeError as retry_error:
            raise RuntimeError(f"{login_error}；自动注册后再次登录仍失败：{retry_error}") from retry_error


def call_chat_api(
    session: requests.Session,
    *,
    base_url: str,
    token: str,
    question: str,
    role_id: int,
    timeout: float,
    role_config_override: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role_id": role_id,
        "message": question,
    }
    if role_config_override:
        payload["role_config_override"] = role_config_override

    response = session.post(
        f"{base_url}/api/chat/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(f"聊天接口调用失败：{extract_error_message(response)}")
    return response.json()


def prepare_test_dataset(
    session: requests.Session,
    *,
    base_url: str,
    token: str,
    cases: list[EvalCase],
    role_id: int,
    timeout: float,
    role_config_override: dict[str, Any] | None,
) -> tuple[Dataset, list[ChatEvalResult]]:
    Dataset, _, _, _, _, _ = import_evaluation_dependencies()
    results: list[ChatEvalResult] = []
    for case in cases:
        response_data = call_chat_api(
            session,
            base_url=base_url,
            token=token,
            question=case.question,
            role_id=role_id,
            timeout=timeout,
            role_config_override=role_config_override,
        )
        docs = response_data.get("retrieved_docs", []) or []
        contexts = [str(doc.get("text", "")).strip() for doc in docs if str(doc.get("text", "")).strip()]
        results.append(
            ChatEvalResult(
                question=case.question,
                ground_truth=case.ground_truth,
                answer=str(response_data.get("response", "")).strip(),
                contexts=contexts,
                session_id=str(response_data.get("session_id", "")).strip(),
                retrieved_docs_count=int(response_data.get("retrieved_docs_count", len(docs)) or 0),
            )
        )

    dataset = Dataset.from_dict(
        {
            "question": [item.question for item in results],
            "answer": [item.answer for item in results],
            "contexts": [item.contexts for item in results],
            "ground_truth": [item.ground_truth for item in results],
        }
    )
    return dataset, results


def summarize_metrics(result: Any) -> dict[str, float]:
    summary: dict[str, float] = {}
    for metric_name in ("context_precision", "context_recall", "faithfulness", "answer_relevancy"):
        metric_values = result[metric_name]
        summary[metric_name] = float(metric_values.mean())
    return summary


def save_results(
    results_file: str,
    *,
    metrics_summary: dict[str, float],
    eval_results: list[ChatEvalResult],
) -> None:
    path = Path(results_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metrics": metrics_summary,
        "cases": [asdict(item) for item in eval_results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_ragas_evaluation(args: argparse.Namespace) -> dict[str, float]:
    _, evaluate, answer_relevancy, context_precision, context_recall, faithfulness = (
        import_evaluation_dependencies()
    )
    base_url = normalize_base_url(args.base_url)
    cases = load_eval_cases(args.cases_file)
    role_config_override = build_role_override(args.knowledge_domains)

    with requests.Session() as session:
        token = ensure_token(
            session,
            base_url=base_url,
            username=args.username,
            password=args.password,
            email=args.email,
            timeout=args.timeout,
            auto_register=args.auto_register,
        )
        dataset, eval_results = prepare_test_dataset(
            session,
            base_url=base_url,
            token=token,
            cases=cases,
            role_id=args.role_id,
            timeout=args.timeout,
            role_config_override=role_config_override,
        )

    result = evaluate(
        dataset,
        metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
    )
    metrics_summary = summarize_metrics(result)

    print("=" * 60)
    print("RAGAS 评测结果")
    print("=" * 60)
    for metric_name, metric_value in metrics_summary.items():
        print(f"{metric_name}: {metric_value:.4f}")

    if args.results_file:
        save_results(
            args.results_file,
            metrics_summary=metrics_summary,
            eval_results=eval_results,
        )
        print(f"结果已写入：{Path(args.results_file).resolve()}")

    return metrics_summary


if __name__ == "__main__":
    run_ragas_evaluation(parse_args())
