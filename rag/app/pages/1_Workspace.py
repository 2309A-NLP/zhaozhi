"""登录后的主工作台页面。"""
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List

import streamlit as st


APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from frontend_shared import (  # noqa: E402
    DOCUMENT_DOMAIN_OPTIONS,
    EXCLUSIVE_ROLE_KEY,
    ROLE_OPTIONS,
    check_backend_health,
    ensure_role_thread,
    get_default_role_payload,
    get_knowledge_domain_label,
    get_role_label,
    init_state,
    logout,
    normalize_api_base,
    refresh_documents,
    reset_chat,
    send_multi_role_chat,
    set_active_role_keys,
    upload_document,
)
from ui_components import (  # noqa: E402
    inject_theme,
    render_empty_stage,
    render_note_panel,
    render_status_pill,
    render_tag_cloud,
    render_workspace_strip,
)


def _html(block: str) -> str:
    return dedent(block).strip()


def inject_workspace_style():
    st.markdown(
        _html(
            """
        <style>
        .main .block-container {
            max-width: 1280px;
            padding-top: 1.1rem;
            padding-bottom: 6.5rem;
        }

        [data-testid="stSidebar"] {
            min-width: 320px;
            max-width: 320px;
        }

        .workspace-hero {
            border-radius: 30px;
            padding: 1.25rem 1.25rem 1.35rem 1.25rem;
            background:
                radial-gradient(circle at top right, rgba(244, 201, 93, 0.24), transparent 22%),
                linear-gradient(135deg, rgba(255, 252, 247, 0.96), rgba(248, 242, 233, 0.90));
            border: 1px solid rgba(21, 48, 51, 0.08);
            box-shadow: 0 18px 46px rgba(18, 32, 38, 0.08);
            margin-bottom: 1rem;
        }

        .workspace-hero-top {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.95rem;
        }

        .workspace-kicker {
            color: #0f766e;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            font-size: 0.76rem;
            font-weight: 800;
            margin-bottom: 0.34rem;
        }

        .workspace-title {
            font-size: 1.5rem;
            font-weight: 800;
            color: #163133;
            margin: 0;
        }

        .workspace-subtitle {
            color: #677576;
            font-size: 0.95rem;
            margin-top: 0.28rem;
            line-height: 1.75;
            max-width: 760px;
        }

        .workspace-meta {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.45rem;
            min-width: 220px;
        }

        .workspace-meta small {
            color: #6c7b7c;
            text-align: right;
            line-height: 1.55;
        }

        .workspace-panel {
            border-radius: 24px;
            padding: 1rem 1rem 0.6rem 1rem;
            border: 1px solid rgba(21, 48, 51, 0.08);
            background: rgba(255, 252, 247, 0.86);
            box-shadow: 0 14px 34px rgba(18, 32, 38, 0.05);
            margin-bottom: 1rem;
        }

        .panel-kicker {
            color: #5f6e70;
            font-size: 0.84rem;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            margin-bottom: 0.25rem;
        }

        .panel-title {
            color: #163133;
            font-size: 1.08rem;
            font-weight: 800;
            margin-bottom: 0.18rem;
        }

        .panel-desc {
            color: #6d7b7c;
            font-size: 0.9rem;
            line-height: 1.6;
            margin-bottom: 0.7rem;
        }

        .chat-shell {
            border-radius: 30px;
            background: rgba(255, 252, 247, 0.92);
            border: 1px solid rgba(21, 48, 51, 0.08);
            box-shadow: 0 24px 58px rgba(18, 32, 38, 0.08);
            overflow: hidden;
        }

        .chat-shell-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 1rem 1.1rem;
            border-bottom: 1px solid rgba(21, 48, 51, 0.06);
            background: linear-gradient(180deg, rgba(252, 250, 245, 0.98), rgba(249, 245, 238, 0.90));
        }

        .chat-role-name {
            font-size: 1.14rem;
            font-weight: 800;
            color: #163133;
            margin: 0;
        }

        .chat-role-meta {
            color: #748284;
            font-size: 0.88rem;
            margin-top: 0.22rem;
            line-height: 1.6;
        }

        .chat-body {
            padding: 1rem 1rem 1.2rem 1rem;
            min-height: 520px;
        }

        [data-testid="stChatMessage"] {
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.76);
            border: 1px solid rgba(21, 48, 51, 0.06);
            padding: 0.8rem 0.95rem;
            box-shadow: 0 12px 24px rgba(21, 34, 40, 0.04);
        }

        [data-testid="stChatMessageContent"] p {
            line-height: 1.75;
        }

        .sidebar-title {
            font-size: 0.84rem;
            color: rgba(255, 250, 244, 0.72);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.35rem;
        }

        .sidebar-user-card {
            border-radius: 18px;
            padding: 0.95rem 1rem;
            background: rgba(255, 250, 244, 0.10);
            border: 1px solid rgba(255, 250, 244, 0.10);
            margin-bottom: 0.85rem;
        }

        .sidebar-user-card strong {
            display: block;
            color: #fff9f0;
            font-size: 1rem;
            margin-bottom: 0.25rem;
        }

        .sidebar-user-card span {
            color: rgba(255, 250, 244, 0.78);
            font-size: 0.88rem;
            line-height: 1.6;
        }

        @media (max-width: 960px) {
            .workspace-hero-top,
            .chat-shell-head {
                display: block;
            }

            .workspace-meta {
                align-items: flex-start;
                margin-top: 0.8rem;
            }
        }
        </style>
        """
        ),
        unsafe_allow_html=True,
    )


def render_role_editor(role_key: str) -> Dict[str, Any]:
    thread = ensure_role_thread(role_key)
    role_payload = get_default_role_payload(role_key)
    thread["role_payload"] = role_payload
    domains = role_payload.get("knowledge_domains") or ["general"]
    domain_text = "、".join(get_knowledge_domain_label(domain) for domain in domains)

    st.caption(f"session_id: {thread['session_id']}")
    st.markdown(
        _html(
            f"""
        <div class="sidebar-user-card">
            <strong>{role_payload["role_name"]}</strong>
            <span>角色类型：{get_role_label(role_key)}<br/>知识领域：{domain_text}</span>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )
    st.caption(f"人格特征：{role_payload['personality']}")
    st.caption(f"语言风格：{role_payload['language_style']}")
    st.caption(f"角色约束：{role_payload['constraints']}")
    return role_payload


def render_sidebar(selected_role_key: str) -> Dict[str, Any]:
    with st.sidebar:
        user = st.session_state.get("current_user")
        st.markdown("<div class='sidebar-title'>Account</div>", unsafe_allow_html=True)
        st.markdown(
            _html(
                f"""
            <div class="sidebar-user-card">
                <strong>{user["username"]}</strong>
                <span>账号 ID：{user["id"]}<br/>当前角色：{get_role_label(selected_role_key)}</span>
            </div>
            """
            ),
            unsafe_allow_html=True,
        )

        if st.button("退出登录", use_container_width=True):
            logout()
            st.switch_page("streamlit_app.py")

        st.divider()
        st.markdown("<div class='sidebar-title'>Profile</div>", unsafe_allow_html=True)
        role_payload = render_role_editor(selected_role_key)
        if st.button("重置当前会话", use_container_width=True):
            reset_chat(selected_role_key)
            st.rerun()

        st.divider()
        st.markdown("<div class='sidebar-title'>Knowledge</div>", unsafe_allow_html=True)
        if st.button("刷新文档列表", use_container_width=True):
            refresh_documents()

        selected_domain = st.selectbox(
            "文档知识域",
            options=list(DOCUMENT_DOMAIN_OPTIONS.keys()),
            format_func=get_knowledge_domain_label,
            index=0,
        )
        upload_file = st.file_uploader("上传知识文档", type=["txt", "md", "pdf", "docx"])
        if st.button("上传文档", use_container_width=True, disabled=upload_file is None) and upload_file is not None:
            upload_document(upload_file, selected_domain)

        documents: List[Dict[str, Any]] = st.session_state.get("documents_cache", [])
        if documents:
            with st.expander("已上传文档", expanded=False):
                for doc in documents[:20]:
                    st.caption(
                        f"{doc['title']} | {doc.get('knowledge_domain') or 'general'} | "
                        f"chunks={doc.get('chunk_count', 0)}"
                    )

        return role_payload


def render_header(selected_role_key: str, health: Dict[str, Any] | None):
    thread = ensure_role_thread(selected_role_key)
    role_payload = thread.get("role_payload") or {}
    role_name = role_payload.get("role_name") or get_role_label(selected_role_key)
    role_domains = role_payload.get("knowledge_domains") or ["general"]
    documents = st.session_state.get("documents_cache", [])

    st.markdown("<section class='workspace-hero'>", unsafe_allow_html=True)
    st.markdown(
        _html(
            """
        <div class="workspace-hero-top">
            <div>
                <div class="workspace-kicker">Roleplay Workspace</div>
                <h1 class="workspace-title">角色扮演知识工作台</h1>
                <div class="workspace-subtitle">
                    当前工作台支持多用户、多角色、多轮对话。每个角色会结合知识库、短期记忆与上下文历史持续输出，
                    适用于咨询、教学、陪伴与专业问答场景。
                </div>
            </div>
        """
        ),
        unsafe_allow_html=True,
    )
    st.markdown("<div class='workspace-meta'>", unsafe_allow_html=True)
    render_status_pill("后端在线" if health else "后端离线", tone="ok" if health else "warn")
    st.markdown(
        f"<small>{normalize_api_base(st.session_state['api_base'])}<br/>当前主视角：{role_name}</small>",
        unsafe_allow_html=True,
    )
    st.markdown("</div></div>", unsafe_allow_html=True)

    render_workspace_strip(
        [
            {"label": "当前角色", "value": role_name, "note": "当前聚焦的角色身份"},
            {
                "label": "启用角色",
                "value": str(len(st.session_state.get("active_role_keys", []))),
                "note": "支持多角色切换与并行回复",
            },
            {"label": "检索链路", "value": "Milvus + BGE", "note": "异常时自动降级为本地检索"},
            {"label": "记忆策略", "value": "Redis + Fallback", "note": "Redis 不可用时退回进程内记忆"},
            {"label": "文档缓存", "value": str(len(documents)), "note": "知识文档可动态刷新"},
        ]
    )
    render_tag_cloud([get_knowledge_domain_label(domain) for domain in role_domains])
    st.markdown("</section>", unsafe_allow_html=True)


def render_role_selector(selected_role_key: str) -> str:
    all_role_keys = list(ROLE_OPTIONS.keys())
    active_role_keys = st.session_state.get("active_role_keys", [EXCLUSIVE_ROLE_KEY])
    previous_mode = st.session_state.get("delivery_mode", "single")

    st.markdown(
        _html(
            """
        <section class="workspace-panel">
            <div class="panel-kicker">Delivery</div>
            <div class="panel-title">多角色配置</div>
            <div class="panel-desc">可以选择单角色回复，也可以同时启用多个角色并分别查看各自回应。</div>
        """
        ),
        unsafe_allow_html=True,
    )

    delivery_mode = st.radio(
        "回复模式",
        options=["single", "multi"],
        index=0 if previous_mode == "single" else 1,
        format_func=lambda mode: "单角色" if mode == "single" else "多角色",
        horizontal=True,
        help="单角色模式只由当前角色回复；多角色模式会向所有已启用角色同时发起请求。",
    )
    st.session_state["delivery_mode"] = delivery_mode

    if delivery_mode == "single":
        single_default_role = (
            active_role_keys[-1]
            if previous_mode != "single" and active_role_keys
            else selected_role_key
        )
        selected_role_key = st.selectbox(
            "当前会话角色",
            options=all_role_keys,
            index=all_role_keys.index(single_default_role) if single_default_role in all_role_keys else 0,
            format_func=get_role_label,
            help="单角色模式下，只显示并保留当前选中的这个角色。",
        )
        set_active_role_keys([selected_role_key])
        active_role_keys = [selected_role_key]
    else:
        selected_role_keys = st.multiselect(
            "启用角色",
            options=all_role_keys,
            default=active_role_keys,
            format_func=get_role_label,
            help="多角色模式下，可以同时启用多个角色并分别查看各自回复。",
        )
        if not selected_role_keys:
            selected_role_keys = [EXCLUSIVE_ROLE_KEY]
        set_active_role_keys(selected_role_keys)
        active_role_keys = st.session_state["active_role_keys"]
        selected_role_key = st.selectbox(
            "当前查看角色",
            options=active_role_keys,
            index=active_role_keys.index(selected_role_key) if selected_role_key in active_role_keys else 0,
            format_func=get_role_label,
        )

    st.session_state["selected_delivery_role"] = selected_role_key
    st.markdown(
        _html(
            f"""
        <div class="chat-role-name">{get_role_label(selected_role_key)}</div>
        <div class="chat-role-meta">{"当前由该角色独立回复。" if delivery_mode == "single" else "当前显示该角色视角；发送消息时所有已启用角色都会分别回复。"}</div>
        </section>
        """
        ),
        unsafe_allow_html=True,
    )
    return selected_role_key


def render_docs(docs: List[Dict[str, Any]]):
    if not docs:
        return

    with st.expander(f"参考知识片段（{len(docs)}）", expanded=False):
        for index, doc in enumerate(docs, start=1):
            score = doc.get("rerank_score", doc.get("score", 0.0))
            st.caption(f"[{index}] score={score:.3f}")
            st.write(doc["text"][:400] + ("..." if len(doc["text"]) > 400 else ""))


def render_conversation(selected_role_key: str):
    thread = ensure_role_thread(selected_role_key)
    role_payload = thread.get("role_payload") or {}
    role_name = role_payload.get("role_name") or get_role_label(selected_role_key)
    role_domains = role_payload.get("knowledge_domains") or ["general"]
    delivery_mode = st.session_state.get("delivery_mode", "single")

    st.markdown("<section class='chat-shell'>", unsafe_allow_html=True)
    st.markdown(
        _html(
            f"""
        <div class="chat-shell-head">
            <div>
                <div class="chat-role-name">{role_name}</div>
                <div class="chat-role-meta">{"单角色对话" if delivery_mode == "single" else "多角色对话"} · session {thread['session_id'][-8:]} · 领域：{", ".join(role_domains)}</div>
            </div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )
    st.markdown("<div class='chat-body'>", unsafe_allow_html=True)

    if not thread["messages"]:
        render_empty_stage(
            f"开始和 {role_name} 对话",
            "上传对应领域知识后，在底部输入框发起问题。系统会结合角色设定、知识库检索结果和对话历史持续回答。",
        )
        st.markdown("</div></section>", unsafe_allow_html=True)
        return

    for message in thread["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            render_docs(message.get("docs") or [])

    st.markdown("</div></section>", unsafe_allow_html=True)


def process_prompt(prompt: str, role_payload: Dict[str, Any], selected_role_key: str):
    delivery_mode = st.session_state.get("delivery_mode", "single")
    active_role_keys = st.session_state.get("active_role_keys", [selected_role_key])
    target_role_keys = [selected_role_key] if delivery_mode == "single" else active_role_keys
    role_requests = []

    for role_key in target_role_keys:
        thread = ensure_role_thread(role_key)
        thread_payload = role_payload if role_key == selected_role_key else (
            thread.get("role_payload") or get_default_role_payload(role_key)
        )
        thread["role_payload"] = thread_payload
        thread["messages"].append({"role": "user", "content": prompt})
        role_requests.append(
            {
                "role_key": role_key,
                "message": prompt,
                "session_id": thread["session_id"],
                "role_payload": thread_payload,
                "role_id": 0,
            }
        )

    spinner_text = (
        f"正在等待 {get_role_label(selected_role_key)} 回复..."
        if delivery_mode == "single"
        else f"正在等待 {len(target_role_keys)} 个角色回复..."
    )
    with st.spinner(spinner_text):
        results = send_multi_role_chat(role_requests)

    for role_key in target_role_keys:
        thread = ensure_role_thread(role_key)
        result = results.get(role_key)
        if result and result.get("ok"):
            data = result["data"]
            thread["session_id"] = data.get("session_id", thread["session_id"])
            thread["messages"].append(
                {
                    "role": "assistant",
                    "content": data["response"],
                    "docs": data.get("retrieved_docs", []),
                }
            )
            continue

        error_message = result.get("error", "未知错误") if result else "未知错误"
        thread["messages"].append(
            {"role": "assistant", "content": f"请求失败：{error_message}", "docs": []}
        )


def main():
    st.set_page_config(page_title="角色扮演系统", page_icon="AI", layout="wide")
    init_state()
    inject_theme()
    inject_workspace_style()

    if not st.session_state.get("workspace_access") or not st.session_state.get("current_user"):
        st.switch_page("streamlit_app.py")

    set_active_role_keys(st.session_state.get("active_role_keys", [EXCLUSIVE_ROLE_KEY]))
    selected_role_key = st.session_state.get(
        "selected_delivery_role",
        st.session_state["active_role_keys"][0],
    )

    health = check_backend_health()
    if health and not st.session_state.get("documents_cache"):
        refresh_documents()

    render_header(selected_role_key, health)
    selected_role_key = render_role_selector(selected_role_key)
    role_payload = render_sidebar(selected_role_key)

    if not health:
        render_note_panel(
            "后端当前不可用",
            "页面仍然可以查看当前会话，但发送消息前请先确认 FastAPI 服务已经启动，并且 api_base 配置正确。",
        )

    render_conversation(selected_role_key)

    delivery_mode = st.session_state.get("delivery_mode", "single")
    prompt = st.chat_input(
        f"向 {get_role_label(selected_role_key)} 发送消息"
        if delivery_mode == "single"
        else "向已启用角色发送群组消息"
    )
    if prompt:
        process_prompt(prompt, role_payload, selected_role_key)
        st.rerun()


if __name__ == "__main__":
    main()
