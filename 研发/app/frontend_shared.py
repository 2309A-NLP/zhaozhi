"""共享的 Streamlit 前端辅助函数与状态工具."""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any, Dict, List, Optional

import requests
import streamlit as st


API_BASE_DEFAULT = os.getenv("BACKEND_API_BASE", "http://127.0.0.1:8000/api")
REQUEST_TIMEOUT = 120
MAX_PARALLEL_ROLE_CHATS = 4
EXCLUSIVE_ROLE_KEY = "friend"

ROLE_OPTIONS = {
    "friend": "虚拟朋友",
    "doctor": "医生",
    "assistant": "通用助手",
}

ROLE_DEFAULTS = {
    "friend": {
        "role_name": "虚拟朋友",
        "personality": "温和、真诚、善于倾听",
        "language_style": "自然、轻松、有陪伴感",
        "constraints": "保持虚拟朋友的陪伴感，先理解用户情绪，再结合知识和上下文回应，不编造事实。",
        "knowledge_domains": ["general"],
    },
    "doctor": {
        "role_name": "医生",
        "personality": "严谨、耐心、专业",
        "language_style": "清晰、审慎、易理解",
        "constraints": "优先基于医疗知识库回答，不能替代线下诊疗；遇到危险信号时要明确建议及时就医。",
        "knowledge_domains": ["medical"],
    },
    "assistant": {
        "role_name": "通用助手",
        "personality": "专业、可靠、清晰",
        "language_style": "简洁、礼貌、自然",
        "constraints": "回答必须基于知识和上下文，不编造事实。",
        "knowledge_domains": ["general"],
    },
}

DOCUMENT_DOMAIN_OPTIONS = {
    "general": "通用知识",
    "medical": "医疗",
    "legal": "法律",
    "finance": "金融",
    "education": "教育",
    "psychology": "心理",
    "science": "科学",
    "english": "英语",
}


def _new_session_id() -> str:
    return str(uuid.uuid4())


def _request_error_detail(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    return getattr(response, "text", str(exc)) or str(exc)


def _reset_workspace_state() -> None:
    st.session_state["documents_cache"] = []
    st.session_state["messages"] = []
    st.session_state["session_id"] = _new_session_id()
    st.session_state["workspace_access"] = False
    st.session_state["chat_threads"] = {}
    st.session_state["active_role_keys"] = [EXCLUSIVE_ROLE_KEY]
    st.session_state["delivery_mode"] = "single"
    st.session_state["selected_delivery_role"] = EXCLUSIVE_ROLE_KEY


def _get_thread_payload(role_key: str, thread: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = thread.get("role_payload") if thread else None
    return deepcopy(source or get_default_role_payload(role_key))


def _run_role_chat(
    request_data: Dict[str, Any],
    *,
    api_base: str,
    token: Optional[str],
) -> Dict[str, Any]:
    return send_chat(
        request_data["message"],
        request_data["role_payload"],
        request_data["session_id"],
        role_id=request_data.get("role_id", 0),
        api_base=api_base,
        token=token,
    )


def _format_role_result(role_key: str, *, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
    if error is not None:
        return {role_key: {"ok": False, "error": error}}
    return {role_key: {"ok": True, "data": data}}


def get_role_label(role_key: str) -> str:
    return ROLE_OPTIONS.get(role_key, role_key)


def get_knowledge_domain_label(domain_key: str) -> str:
    return DOCUMENT_DOMAIN_OPTIONS.get(domain_key, domain_key)


def normalize_api_base(value: str) -> str:
    return value.strip().rstrip("/")


def parse_knowledge_domains(value: str) -> List[str]:
    normalized = value.replace("，", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def get_default_role_payload(role_key: str) -> Dict[str, Any]:
    defaults = deepcopy(ROLE_DEFAULTS.get(role_key, ROLE_DEFAULTS[EXCLUSIVE_ROLE_KEY]))
    defaults["role_type"] = role_key
    defaults["is_public"] = False
    return defaults


def _build_thread(role_key: str, role_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "session_id": _new_session_id(),
        "messages": [],
        "role_payload": deepcopy(role_payload or get_default_role_payload(role_key)),
    }


def ensure_role_thread(role_key: str) -> Dict[str, Any]:
    threads = st.session_state.setdefault("chat_threads", {})
    thread = threads.setdefault(role_key, _build_thread(role_key))
    thread.setdefault("messages", [])
    thread.setdefault("session_id", _new_session_id())
    thread.setdefault("role_payload", get_default_role_payload(role_key))
    return thread


def set_active_role_keys(role_keys: List[str]) -> None:
    unique_role_keys: List[str] = []
    for role_key in role_keys:
        if role_key in unique_role_keys:
            continue
        unique_role_keys.append(role_key)
        ensure_role_thread(role_key)

    if not unique_role_keys:
        unique_role_keys = [EXCLUSIVE_ROLE_KEY]
        ensure_role_thread(EXCLUSIVE_ROLE_KEY)

    st.session_state["active_role_keys"] = unique_role_keys
    if st.session_state.get("selected_delivery_role") not in unique_role_keys:
        st.session_state["selected_delivery_role"] = unique_role_keys[0]


def init_state():
    defaults = {
        "api_base": API_BASE_DEFAULT,
        "session_id": _new_session_id(),
        "messages": [],
        "token": None,
        "current_user": None,
        "user_id": None,
        "documents_cache": [],
        "workspace_access": False,
        "chat_threads": {},
        "active_role_keys": [EXCLUSIVE_ROLE_KEY],
        "delivery_mode": "single",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("selected_delivery_role", st.session_state["active_role_keys"][0])
    set_active_role_keys(st.session_state["active_role_keys"])


def get_headers(include_auth: bool = False, token: Optional[str] = None) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    resolved_token = st.session_state.get("token") if token is None else token
    if include_auth and resolved_token:
        headers["Authorization"] = f"Bearer {resolved_token}"
    return headers


def api_request(
    method: str,
    path: str,
    *,
    include_auth: bool = False,
    api_base: Optional[str] = None,
    token: Optional[str] = None,
    **kwargs,
) -> requests.Response:
    url = f"{normalize_api_base(api_base or st.session_state['api_base'])}{path}"
    headers = kwargs.pop("headers", {})
    return requests.request(
        method=method,
        url=url,
        headers={**get_headers(include_auth=include_auth, token=token), **headers},
        timeout=kwargs.pop("timeout", REQUEST_TIMEOUT),
        **kwargs,
    )


def check_backend_health() -> Optional[Dict[str, Any]]:
    health_url = normalize_api_base(st.session_state["api_base"]).removesuffix("/api") + "/health"
    try:
        response = requests.get(health_url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def login(username: str, password: str) -> bool:
    try:
        response = api_request("POST", "/auth/token", data={"username": username, "password": password})
        response.raise_for_status()
        st.session_state["token"] = response.json()["access_token"]

        me_response = api_request("GET", "/auth/me", include_auth=True)
        me_response.raise_for_status()
        current_user = me_response.json()
        st.session_state["current_user"] = current_user
        st.session_state["user_id"] = current_user["id"]
        st.session_state["workspace_access"] = True
        return True
    except requests.RequestException as exc:
        st.session_state["token"] = None
        st.session_state["current_user"] = None
        st.error(f"登录失败：{exc}")
        return False


def register_user(username: str, password: str, email: str = "") -> bool:
    payload = {"username": username.strip(), "password": password, "email": email.strip() or None}
    try:
        response = api_request("POST", "/auth/register", json=payload)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        st.error(f"注册失败：{_request_error_detail(exc)}")
        return False


def logout():
    st.session_state["token"] = None
    st.session_state["current_user"] = None
    _reset_workspace_state()


def refresh_documents():
    try:
        response = api_request("GET", "/documents/", include_auth=True)
        response.raise_for_status()
        st.session_state["documents_cache"] = response.json()
    except requests.RequestException as exc:
        st.warning(f"文档列表刷新失败：{exc}")


def upload_document(file, knowledge_domain: str):
    try:
        response = api_request(
            "POST",
            "/documents/upload",
            files={"file": (file.name, file.getvalue(), file.type or "application/octet-stream")},
            data={"knowledge_domain": knowledge_domain},
            include_auth=True,
        )
        response.raise_for_status()
        refresh_documents()
        st.success(f"文档上传成功：{response.json()['title']}")
    except requests.RequestException as exc:
        st.error(f"文档上传失败：{_request_error_detail(exc)}")


def send_chat(
    message: str,
    role_payload: Dict[str, Any],
    session_id: str,
    *,
    role_id: int = 0,
    api_base: Optional[str] = None,
    token: Optional[str] = None,
):
    response = api_request(
        "POST",
        "/chat/",
        json={
            "role_id": role_id,
            "session_id": session_id,
            "message": message,
            "role_config_override": role_payload,
        },
        include_auth=True,
        api_base=api_base,
        token=token,
    )
    response.raise_for_status()
    return response.json()


def send_multi_role_chat(role_requests: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not role_requests:
        return {}

    api_base = normalize_api_base(st.session_state["api_base"])
    token = st.session_state.get("token")

    if len(role_requests) == 1:
        request_data = role_requests[0]
        try:
            data = _run_role_chat(request_data, api_base=api_base, token=token)
            return _format_role_result(request_data["role_key"], data=data)
        except Exception as exc:
            return _format_role_result(request_data["role_key"], error=str(exc))

    results: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_ROLE_CHATS, len(role_requests))) as executor:
        future_map = {
            executor.submit(_run_role_chat, request_data, api_base=api_base, token=token): request_data["role_key"]
            for request_data in role_requests
        }
        for future in as_completed(future_map):
            role_key = future_map[future]
            try:
                results[role_key] = {"ok": True, "data": future.result()}
            except Exception as exc:
                results[role_key] = {"ok": False, "error": str(exc)}
    return results


def reset_chat(role_key: Optional[str] = None):
    if role_key is None:
        for current_role_key, thread in list(st.session_state.get("chat_threads", {}).items()):
            st.session_state["chat_threads"][current_role_key] = _build_thread(
                current_role_key,
                _get_thread_payload(current_role_key, thread),
            )
        st.session_state["session_id"] = _new_session_id()
        st.session_state["messages"] = []
        return

    thread = ensure_role_thread(role_key)
    st.session_state["chat_threads"][role_key] = _build_thread(
        role_key,
        _get_thread_payload(role_key, thread),
    )
