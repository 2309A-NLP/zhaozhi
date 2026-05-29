"""登录与注册前端入口页面。"""
import sys
from pathlib import Path
from textwrap import dedent

import streamlit as st


APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from frontend_shared import (  # noqa: E402
    check_backend_health,
    init_state,
    login,
    normalize_api_base,
    register_user,
)


def _html(block: str) -> str:
    return dedent(block).strip()


def inject_login_style():
    st.markdown(
        _html(
            """
        <style>
        :root {
            --bg: #f4ede3;
            --paper: rgba(255, 251, 246, 0.92);
            --paper-strong: rgba(255, 251, 246, 0.98);
            --ink: #183033;
            --muted: #617173;
            --line: rgba(24, 48, 51, 0.10);
            --brand: #0f766e;
            --accent: #d06e47;
            --highlight: #f0c76a;
            --ok: #1f8f63;
            --warn: #a76b1e;
            --shadow: 0 28px 80px rgba(35, 39, 47, 0.12);
            --radius-xl: 32px;
            --radius-lg: 24px;
            --radius-md: 18px;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(240, 199, 106, 0.24), transparent 26%),
                radial-gradient(circle at top right, rgba(15, 118, 110, 0.14), transparent 30%),
                linear-gradient(180deg, #faf5ed 0%, #f2eadf 100%);
            color: var(--ink);
            font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", "Microsoft YaHei", sans-serif;
        }

        [data-testid="stHeader"],
        .stApp > header,
        [data-testid="stSidebar"] {
            display: none;
        }

        .main .block-container {
            max-width: 1460px;
            padding: 0.8rem 1.1rem 1rem 1.1rem;
        }

        .landing-shell {
            padding-top: 0.35rem;
        }

        .landing-hero {
            position: relative;
            overflow: hidden;
            min-height: 100%;
            border-radius: 30px;
            padding: 1.5rem;
            background:
                radial-gradient(circle at 14% 18%, rgba(255, 251, 246, 0.16), transparent 18%),
                radial-gradient(circle at 84% 22%, rgba(240, 199, 106, 0.22), transparent 24%),
                linear-gradient(145deg, rgba(18, 47, 51, 0.98) 0%, rgba(15, 118, 110, 0.94) 52%, rgba(208, 110, 71, 0.88) 100%);
            color: #fff9f2;
            box-shadow: 0 30px 70px rgba(26, 37, 45, 0.18);
        }

        .landing-hero::after {
            content: "";
            position: absolute;
            right: -72px;
            top: -56px;
            width: 280px;
            height: 280px;
            border-radius: 50%;
            background: rgba(255, 251, 246, 0.10);
            filter: blur(4px);
        }

        .hero-kicker {
            display: inline-flex;
            align-items: center;
            padding: 0.34rem 0.78rem;
            border-radius: 999px;
            border: 1px solid rgba(255, 251, 246, 0.16);
            background: rgba(255, 251, 246, 0.08);
            letter-spacing: 0.12em;
            text-transform: uppercase;
            font-size: 0.78rem;
        }

        .hero-title {
            font-family: "Georgia", "Times New Roman", "STSong", serif;
            font-size: clamp(2rem, 3vw, 3rem);
            line-height: 1.06;
            margin: 0.7rem 0 0.55rem 0;
            max-width: 560px;
        }

        .hero-desc {
            max-width: 620px;
            color: rgba(255, 248, 241, 0.88);
            line-height: 1.72;
            font-size: 0.96rem;
        }

        .hero-step-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1rem;
        }

        .hero-step {
            display: inline-flex;
            align-items: center;
            gap: 0.42rem;
            padding: 0.4rem 0.72rem;
            border-radius: 999px;
            background: rgba(255, 251, 246, 0.12);
            border: 1px solid rgba(255, 251, 246, 0.14);
            font-size: 0.82rem;
        }

        .hero-step::before {
            content: "";
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--highlight);
        }

        .hero-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.8rem;
            margin-top: 1.1rem;
        }

        .hero-card {
            border-radius: 22px;
            padding: 0.95rem 1rem;
            background: rgba(255, 251, 246, 0.12);
            border: 1px solid rgba(255, 251, 246, 0.12);
            backdrop-filter: blur(6px);
        }

        .hero-card strong {
            display: block;
            font-size: 0.96rem;
            margin-bottom: 0.26rem;
        }

        .hero-card span {
            display: block;
            color: rgba(255, 248, 241, 0.8);
            line-height: 1.58;
            font-size: 0.84rem;
        }

        .auth-panel {
            border-radius: 30px;
            border: 1px solid var(--line);
            background: var(--paper-strong);
            box-shadow: var(--shadow);
            padding: 1.15rem 1.05rem 0.95rem 1.05rem;
        }

        .auth-kicker {
            color: var(--brand);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.74rem;
            font-weight: 800;
            margin-bottom: 0.4rem;
        }

        .auth-title {
            font-size: 1.56rem;
            font-weight: 800;
            color: var(--ink);
            margin: 0;
        }

        .auth-subtitle {
            color: var(--muted);
            line-height: 1.65;
            font-size: 0.9rem;
            margin: 0.35rem 0 0.7rem 0;
        }

        .status-line {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            border-radius: 15px;
            border: 1px solid var(--line);
            background: rgba(255, 251, 246, 0.86);
            padding: 0.58rem 0.72rem;
            margin-bottom: 0.85rem;
            color: #5c6c6d;
            font-size: 0.82rem;
        }

        .status-line::before {
            content: "";
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: var(--ok);
            flex: 0 0 auto;
        }

        .status-line.warn::before {
            background: var(--warn);
        }

        .meta-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.7rem;
            margin-bottom: 0.8rem;
        }

        .meta-card {
            border-radius: 18px;
            padding: 0.85rem 0.9rem;
            background: rgba(255, 250, 243, 0.9);
            border: 1px solid var(--line);
        }

        .meta-label {
            color: var(--muted);
            font-size: 0.76rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.28rem;
        }

        .meta-value {
            color: var(--ink);
            font-size: 0.96rem;
            font-weight: 700;
            line-height: 1.45;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.45rem;
            margin-bottom: 0.32rem;
        }

        .stTabs button[role="tab"] {
            border-radius: 999px;
            min-height: 32px;
            border: 1px solid rgba(24, 48, 51, 0.10);
            background: rgba(255, 249, 242, 0.94);
            color: #4f6260;
            font-size: 0.82rem;
        }

        .stTabs button[role="tab"][aria-selected="true"] {
            color: #fffaf4;
            border-color: transparent;
            background: linear-gradient(135deg, #0f766e 0%, #d06e47 100%);
        }

        [data-baseweb="input"] > div,
        textarea {
            border-radius: 14px !important;
            border: 1px solid rgba(24, 48, 51, 0.10) !important;
            background: rgba(255, 252, 248, 0.98) !important;
            box-shadow: none !important;
        }

        [data-baseweb="input"] input {
            min-height: 36px;
        }

        .stButton > button {
            width: 100%;
            min-height: 38px;
            border-radius: 14px;
            border: none;
            background: linear-gradient(135deg, #0f766e 0%, #d06e47 100%);
            color: #fffaf4;
            font-weight: 700;
            box-shadow: 0 14px 28px rgba(28, 47, 47, 0.14);
            transition: transform 160ms ease, box-shadow 160ms ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 22px 38px rgba(28, 47, 47, 0.18);
        }

        [data-testid="stExpander"] {
            border-radius: var(--radius-md);
            border: 1px solid var(--line);
            background: var(--paper);
            margin-bottom: 0.6rem;
        }

        .auth-footer {
            text-align: center;
            color: #72807f;
            font-size: 0.78rem;
            line-height: 1.55;
            margin-top: 0.7rem;
        }

        @media (max-width: 960px) {
            .main .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
                padding-bottom: 0.85rem;
            }

            .landing-hero {
                min-height: auto;
                padding: 1.15rem;
            }

            .hero-grid,
            .meta-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """
        ),
        unsafe_allow_html=True,
    )


def render_connection_box():
    with st.expander("后端连接设置", expanded=False):
        api_base = st.text_input("后端地址", value=st.session_state["api_base"])
        st.session_state["api_base"] = normalize_api_base(api_base)
        if st.button("检测后端连接", use_container_width=True):
            health = check_backend_health()
            if health:
                st.success(f"后端在线：{health['status']}")
            else:
                st.error("后端不可用，请先启动 uvicorn")


def render_auth_tabs():
    login_tab, register_tab = st.tabs(["登录", "注册"])

    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("用户名", value="", placeholder="请输入已注册账号")
            password = st.text_input("密码", value="", type="password", placeholder="请输入密码")
            submitted = st.form_submit_button("进入工作台")
            if submitted and login(username, password):
                st.switch_page("pages/1_Workspace.py")

    with register_tab:
        with st.form("register_form", clear_on_submit=False):
            new_username = st.text_input("新用户名", placeholder="设置登录账号")
            new_password = st.text_input("新密码", type="password", placeholder="至少 6 位")
            confirm_password = st.text_input("确认密码", type="password", placeholder="再次输入密码")
            email = st.text_input("邮箱（可选）", placeholder="用于找回或通知")
            register_submitted = st.form_submit_button("创建账号")
            if register_submitted:
                if new_password != confirm_password:
                    st.error("两次输入的密码不一致")
                elif register_user(new_username, new_password, email):
                    st.success("注册成功，正在自动登录")
                    if login(new_username, new_password):
                        st.switch_page("pages/1_Workspace.py")


def render_showcase_panel():
    st.markdown(
        _html(
            """
        <section class="landing-hero">
            <span class="hero-kicker">Roleplay Workspace</span>
            <h1 class="hero-title">角色扮演知识助手</h1>
            <p class="hero-desc">
                这是一个基于 Streamlit + FastAPI 的多角色对话工作台。登录后可以切换不同角色、
                上传知识文档，并结合检索结果与上下文生成连续对话。
            </p>

            <div class="hero-step-row">
                <span class="hero-step">注册账号</span>
                <span class="hero-step">选择角色</span>
                <span class="hero-step">上传资料</span>
                <span class="hero-step">开始对话</span>
            </div>

            <div class="hero-grid">
                <article class="hero-card">
                    <strong>多角色工作台</strong>
                    <span>支持社交 NPC、医生、心理咨询、法律、金融、教师等多种角色配置。</span>
                </article>
                <article class="hero-card">
                    <strong>知识检索增强</strong>
                    <span>文档上传后会进入知识库，在回答时优先结合检索结果与会话上下文。</span>
                </article>
                <article class="hero-card">
                    <strong>连续会话</strong>
                    <span>每个角色拥有独立会话线程，适合持续咨询、教学辅导和陪伴式互动。</span>
                </article>
                <article class="hero-card">
                    <strong>本地可运行</strong>
                    <span>已调整为更适合本地开发的结构，前后端能在轻依赖模式下先跑起来。</span>
                </article>
            </div>
        </section>
        """
        ),
        unsafe_allow_html=True,
    )


def render_auth_panel(health):
    status_class = "status-line" if health else "status-line warn"
    status_text = (
        f"后端在线 · {normalize_api_base(st.session_state['api_base'])}"
        if health
        else "后端离线 · 请先启动 uvicorn"
    )

    st.markdown(
        _html(
            f"""
        <section class="auth-panel">
            <div class="auth-kicker">Account Access</div>
            <h2 class="auth-title">登录并进入工作台</h2>
            <p class="auth-subtitle">
                当前入口只保留注册和登录流程。建议先确认后端健康状态，再进行账号创建和对话操作。
            </p>
            <div class="{status_class}">{status_text}</div>
            <div class="meta-grid">
                <div class="meta-card">
                    <div class="meta-label">默认前端</div>
                    <div class="meta-value">Streamlit 单页入口</div>
                </div>
                <div class="meta-card">
                    <div class="meta-label">默认后端</div>
                    <div class="meta-value">FastAPI /api 接口</div>
                </div>
            </div>
        </section>
        """
        ),
        unsafe_allow_html=True,
    )
    render_connection_box()
    render_auth_tabs()
    st.markdown(
        "<div class='auth-footer'>已关闭游客模式，请使用注册后的账号登录系统。</div>",
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="角色扮演系统", page_icon="AI", layout="wide")
    init_state()
    inject_login_style()

    if st.session_state.get("workspace_access"):
        st.switch_page("pages/1_Workspace.py")

    health = check_backend_health()

    st.markdown("<div class='landing-shell'>", unsafe_allow_html=True)
    left, right = st.columns([1.24, 0.86], gap="large")
    with left:
        render_showcase_panel()
    with right:
        render_auth_panel(health)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
