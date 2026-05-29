"""共享样式与通用 UI 组件。"""
from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Iterable, Mapping, Sequence

import streamlit as st


def _html(block: str) -> str:
    return dedent(block).strip()


def inject_theme():
    st.markdown(
        _html(
            """
        <style>
        :root {
            --bg-main: #f6f1e8;
            --bg-soft: rgba(255, 251, 245, 0.78);
            --bg-strong: rgba(255, 248, 238, 0.94);
            --line: rgba(38, 71, 75, 0.12);
            --line-strong: rgba(38, 71, 75, 0.22);
            --text-main: #153033;
            --text-soft: #5e6e6f;
            --brand: #0f766e;
            --brand-2: #dd6b4d;
            --brand-3: #f4c95d;
            --ok: #1f8f63;
            --warn: #a86618;
            --danger: #b24444;
            --shadow: 0 24px 60px rgba(35, 39, 47, 0.10);
            --radius-xl: 28px;
            --radius-lg: 22px;
            --radius-md: 16px;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(244, 201, 93, 0.22), transparent 28%),
                radial-gradient(circle at top right, rgba(15, 118, 110, 0.16), transparent 30%),
                linear-gradient(180deg, #f9f4eb 0%, #f3ede2 100%);
            color: var(--text-main);
            font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", "Microsoft YaHei", sans-serif;
        }

        .main .block-container {
            max-width: 1380px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3, .stMarkdown p, .stMarkdown li, label, .stCaption {
            color: var(--text-main);
        }

        h1, h2, h3 {
            font-family: "Georgia", "Times New Roman", "STSong", serif;
            letter-spacing: 0.02em;
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(19, 48, 51, 0.96) 0%, rgba(26, 62, 66, 0.96) 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        [data-testid="stSidebar"] * {
            color: #f7f5f0;
        }

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] .stMarkdown p,
        [data-testid="stSidebar"] .stMarkdown li,
        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] li,
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] *,
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {
            color: #f7f5f0 !important;
            -webkit-text-fill-color: #f7f5f0 !important;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] [data-baseweb="input"] > div,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] input {
            background: rgba(255, 250, 244, 0.96) !important;
            border: 1px solid rgba(255, 255, 255, 0.14) !important;
            color: #153033 !important;
        }

        [data-testid="stSidebar"] [data-baseweb="input"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] [data-baseweb="select"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] span,
        [data-testid="stSidebar"] [data-baseweb="tag"] span,
        [data-testid="stSidebar"] [data-baseweb="select"] * {
            color: #153033 !important;
            -webkit-text-fill-color: #153033 !important;
        }

        [data-testid="stSidebar"] input::placeholder,
        [data-testid="stSidebar"] textarea::placeholder {
            color: rgba(21, 48, 51, 0.52) !important;
            -webkit-text-fill-color: rgba(21, 48, 51, 0.52) !important;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: linear-gradient(135deg, #f4c95d 0%, #dd6b4d 100%);
            color: #203233;
            border: none;
            box-shadow: none;
        }

        .stButton > button {
            border-radius: 999px;
            border: 1px solid rgba(21, 48, 51, 0.10);
            background: linear-gradient(135deg, #0f766e 0%, #1f8f63 100%);
            color: #fffaf3;
            font-weight: 700;
            padding: 0.66rem 1.1rem;
            box-shadow: 0 14px 28px rgba(15, 118, 110, 0.20);
            transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 18px 32px rgba(15, 118, 110, 0.24);
            filter: saturate(1.03);
        }

        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        textarea {
            border-radius: 16px !important;
            border: 1px solid var(--line) !important;
            background: rgba(255, 253, 248, 0.86) !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
        }

        [data-baseweb="tab-list"] {
            gap: 0.55rem;
        }

        button[role="tab"] {
            border-radius: 999px;
            border: 1px solid rgba(21, 48, 51, 0.12);
            background: rgba(255, 251, 245, 0.72);
            padding: 0.45rem 1rem;
        }

        button[role="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, rgba(15, 118, 110, 0.16), rgba(221, 107, 77, 0.18));
            border-color: rgba(15, 118, 110, 0.22);
        }

        [data-testid="stMetric"] {
            background: var(--bg-soft);
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            padding: 1rem 1.1rem;
            box-shadow: var(--shadow);
        }

        [data-testid="stChatMessage"] {
            background: rgba(255, 252, 246, 0.74);
            border: 1px solid rgba(21, 48, 51, 0.08);
            border-radius: 20px;
            padding: 0.8rem 1rem;
            box-shadow: 0 14px 26px rgba(25, 29, 35, 0.05);
            margin-bottom: 0.8rem;
        }

        [data-testid="stExpander"] {
            border-radius: 18px;
            border: 1px solid var(--line);
            background: rgba(255, 251, 245, 0.62);
        }

        [data-testid="stFileUploader"] section {
            border-radius: 18px;
            border: 1px dashed rgba(15, 118, 110, 0.32);
            background: rgba(255, 251, 245, 0.40);
        }

        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] div,
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small,
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] span,
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button,
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button * {
            color: #153033 !important;
            -webkit-text-fill-color: #153033 !important;
        }

        .hero-shell {
            position: relative;
            overflow: hidden;
            border-radius: var(--radius-xl);
            padding: 2rem 2.1rem;
            background:
                radial-gradient(circle at top right, rgba(244, 201, 93, 0.30), transparent 22%),
                linear-gradient(135deg, rgba(16, 49, 53, 0.96) 0%, rgba(15, 118, 110, 0.92) 52%, rgba(221, 107, 77, 0.84) 100%);
            color: #fffaf4;
            box-shadow: 0 34px 70px rgba(23, 35, 43, 0.18);
            margin-bottom: 1.25rem;
        }

        .hero-shell::after {
            content: "";
            position: absolute;
            inset: auto -12% -50% auto;
            width: 300px;
            height: 300px;
            border-radius: 50%;
            background: rgba(255, 250, 244, 0.08);
            filter: blur(8px);
        }

        .hero-eyebrow {
            display: inline-block;
            padding: 0.28rem 0.72rem;
            border-radius: 999px;
            border: 1px solid rgba(255, 250, 244, 0.18);
            background: rgba(255, 250, 244, 0.10);
            font-size: 0.78rem;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }

        .hero-title {
            margin: 0.85rem 0 0.6rem;
            font-size: clamp(2rem, 3vw, 3.2rem);
            line-height: 1.05;
        }

        .hero-subtitle {
            max-width: 840px;
            color: rgba(255, 249, 240, 0.88);
            font-size: 1.02rem;
            line-height: 1.7;
            margin-bottom: 1.1rem;
        }

        .chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
        }

        .hero-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.42rem 0.72rem;
            border-radius: 999px;
            background: rgba(255, 251, 245, 0.14);
            border: 1px solid rgba(255, 251, 245, 0.14);
            font-size: 0.88rem;
        }

        .glass-card {
            border-radius: var(--radius-lg);
            background: var(--bg-soft);
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
            padding: 1.2rem 1.25rem;
            margin-bottom: 1rem;
        }

        .glass-card strong {
            color: var(--text-main);
        }

        .section-kicker {
            color: var(--brand);
            text-transform: uppercase;
            letter-spacing: 0.11em;
            font-size: 0.76rem;
            margin-bottom: 0.4rem;
            font-weight: 800;
        }

        .section-title {
            font-size: 1.7rem;
            margin-bottom: 0.45rem;
        }

        .section-subtitle {
            color: var(--text-soft);
            margin-bottom: 1rem;
        }

        .stat-card {
            border-radius: var(--radius-md);
            padding: 1rem 1.05rem;
            border: 1px solid var(--line);
            background: var(--bg-strong);
            box-shadow: var(--shadow);
            min-height: 132px;
        }

        .stat-label {
            color: var(--text-soft);
            font-size: 0.84rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }

        .stat-value {
            font-family: "Georgia", "Times New Roman", "STSong", serif;
            font-size: 1.9rem;
            line-height: 1.1;
            margin-bottom: 0.35rem;
        }

        .stat-note {
            color: var(--text-soft);
            line-height: 1.55;
            font-size: 0.92rem;
        }

        .role-banner {
            border-radius: 22px;
            padding: 1rem 1.05rem;
            background:
                linear-gradient(135deg, rgba(15, 118, 110, 0.10), rgba(221, 107, 77, 0.10)),
                rgba(255, 252, 247, 0.90);
            border: 1px solid rgba(15, 118, 110, 0.10);
            box-shadow: var(--shadow);
            margin-bottom: 0.8rem;
        }

        .role-banner h3 {
            margin: 0;
            font-size: 1.3rem;
        }

        .role-banner p {
            margin: 0.22rem 0 0;
            color: var(--text-soft);
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.38rem 0.72rem;
            border-radius: 999px;
            background: rgba(255, 251, 245, 0.72);
            border: 1px solid var(--line);
            color: var(--text-main);
            font-size: 0.88rem;
        }

        .status-pill::before {
            content: "";
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--brand);
        }

        .status-pill.ok::before { background: var(--ok); }
        .status-pill.warn::before { background: var(--warn); }
        .status-pill.danger::before { background: var(--danger); }

        .feature-list {
            display: grid;
            gap: 0.8rem;
        }

        .feature-item {
            border-radius: 18px;
            padding: 0.95rem 1rem;
            border: 1px solid var(--line);
            background: rgba(255, 251, 245, 0.70);
        }

        .feature-item strong {
            display: block;
            margin-bottom: 0.3rem;
            font-size: 1rem;
        }

        .workspace-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 0.85rem;
            margin: 1.1rem 0 1.2rem 0;
        }

        .workspace-mini-card {
            border-radius: 20px;
            padding: 0.95rem 1rem;
            border: 1px solid var(--line);
            background: rgba(255, 251, 245, 0.82);
            box-shadow: var(--shadow);
        }

        .workspace-mini-label {
            color: var(--text-soft);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.35rem;
        }

        .workspace-mini-value {
            font-size: 1.15rem;
            font-weight: 700;
            line-height: 1.35;
        }

        .workspace-mini-note {
            color: var(--text-soft);
            font-size: 0.88rem;
            margin-top: 0.3rem;
            line-height: 1.5;
        }

        .tag-cloud {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin: 0.55rem 0 0.2rem 0;
        }

        .tag-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            border-radius: 999px;
            padding: 0.42rem 0.78rem;
            border: 1px solid rgba(15, 118, 110, 0.14);
            background: rgba(255, 251, 245, 0.76);
            color: var(--text-main);
            font-size: 0.88rem;
            line-height: 1;
        }

        .tag-chip::before {
            content: "";
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--brand);
        }

        .role-shell {
            border-radius: 26px;
            border: 1px solid rgba(21, 48, 51, 0.08);
            background: rgba(255, 252, 247, 0.78);
            box-shadow: 0 18px 40px rgba(22, 30, 38, 0.08);
            padding: 1rem;
        }

        .note-panel {
            border-radius: 22px;
            padding: 1rem 1.05rem;
            border: 1px solid var(--line);
            background: linear-gradient(135deg, rgba(255, 251, 245, 0.88), rgba(245, 239, 228, 0.72));
            box-shadow: var(--shadow);
        }

        .note-panel strong {
            display: block;
            font-size: 1rem;
            margin-bottom: 0.32rem;
        }

        .note-panel .muted {
            line-height: 1.55;
        }

        .empty-stage {
            border-radius: 26px;
            padding: 1.8rem 1.4rem;
            border: 1px dashed rgba(15, 118, 110, 0.24);
            background:
                radial-gradient(circle at top right, rgba(244, 201, 93, 0.18), transparent 25%),
                rgba(255, 251, 245, 0.72);
            text-align: center;
            box-shadow: var(--shadow);
        }

        .empty-stage h3 {
            margin: 0 0 0.5rem 0;
        }

        .empty-stage p {
            max-width: 720px;
            margin: 0 auto;
            color: var(--text-soft);
            line-height: 1.7;
        }

        .muted {
            color: var(--text-soft);
        }
        </style>
        """
        ),
        unsafe_allow_html=True,
    )


def render_hero(title: str, subtitle: str, eyebrow: str, chips: Sequence[str] | None = None):
    chip_html = ""
    if chips:
        chip_html = "<div class='chip-row'>" + "".join(
            f"<span class='hero-chip'>{escape(chip)}</span>" for chip in chips
        ) + "</div>"
    st.markdown(
        _html(
            f"""
        <section class="hero-shell">
            <span class="hero-eyebrow">{escape(eyebrow)}</span>
            <h1 class="hero-title">{escape(title)}</h1>
            <p class="hero-subtitle">{escape(subtitle)}</p>
            {chip_html}
        </section>
        """
        ),
        unsafe_allow_html=True,
    )


def render_section_intro(kicker: str, title: str, subtitle: str):
    st.markdown(
        _html(
            f"""
        <div class="section-kicker">{escape(kicker)}</div>
        <div class="section-title">{escape(title)}</div>
        <div class="section-subtitle">{escape(subtitle)}</div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_stat_cards(items: Sequence[Mapping[str, str]]):
    for column, item in zip(st.columns(len(items)), items):
        with column:
            st.markdown(
                _html(
                    f"""
                <div class="stat-card">
                    <div class="stat-label">{escape(item["label"])}</div>
                    <div class="stat-value">{escape(item["value"])}</div>
                    <div class="stat-note">{escape(item["note"])}</div>
                </div>
                """
                ),
                unsafe_allow_html=True,
            )


def render_glass_card(title: str, body: str):
    st.markdown(
        _html(
            f"""
        <div class="glass-card">
            <strong>{escape(title)}</strong>
            <div class="muted" style="margin-top: 0.45rem;">{escape(body)}</div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_feature_list(items: Iterable[tuple[str, str]]):
    html = ["<div class='feature-list'>"]
    for title, body in items:
        html.append(
            _html(
                f"""
            <div class="feature-item">
                <strong>{escape(title)}</strong>
                <div class="muted">{escape(body)}</div>
            </div>
            """
            )
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_status_pill(text: str, tone: str = "ok"):
    st.markdown(
        f"<div class='status-pill {escape(tone)}'>{escape(text)}</div>",
        unsafe_allow_html=True,
    )


def render_role_banner(title: str, subtitle: str):
    st.markdown(
        _html(
            f"""
        <div class="role-banner">
            <h3>{escape(title)}</h3>
            <p>{escape(subtitle)}</p>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_workspace_strip(items: Sequence[Mapping[str, str]]):
    html = ["<div class='workspace-strip'>"]
    for item in items:
        html.append(
            _html(
                f"""
            <div class="workspace-mini-card">
                <div class="workspace-mini-label">{escape(item["label"])}</div>
                <div class="workspace-mini-value">{escape(item["value"])}</div>
                <div class="workspace-mini-note">{escape(item["note"])}</div>
            </div>
            """
            )
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_tag_cloud(tags: Sequence[str]):
    html = ["<div class='tag-cloud'>"]
    html.extend(f"<span class='tag-chip'>{escape(tag)}</span>" for tag in tags)
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_note_panel(title: str, body: str):
    st.markdown(
        _html(
            f"""
        <div class="note-panel">
            <strong>{escape(title)}</strong>
            <div class="muted">{escape(body)}</div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_empty_stage(title: str, body: str):
    st.markdown(
        _html(
            f"""
        <div class="empty-stage">
            <h3>{escape(title)}</h3>
            <p>{escape(body)}</p>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )
