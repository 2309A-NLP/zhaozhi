from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "project_architecture_flow.pdf"
WINDOWS_FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


def get_font(size: float, weight: str = "regular"):
    if WINDOWS_FONT.exists():
        return font_manager.FontProperties(fname=str(WINDOWS_FONT), size=size, weight=weight)
    return font_manager.FontProperties(size=size, weight=weight)


TITLE_FONT = get_font(22, "bold")
SUBTITLE_FONT = get_font(11)
SECTION_FONT = get_font(15, "bold")
BOX_TITLE_FONT = get_font(11, "bold")
BOX_BODY_FONT = get_font(9)
SMALL_FONT = get_font(8)


PALETTE = {
    "bg": "#f7f4ee",
    "ink": "#183033",
    "muted": "#516062",
    "line": "#325a5e",
    "accent": "#d06e47",
    "teal": "#0f766e",
    "gold": "#e6bc62",
    "panel": "#fffdf8",
    "panel_alt": "#eef7f5",
    "panel_warm": "#fff3e8",
    "panel_data": "#f4efe6",
}


def new_page():
    fig = plt.figure(figsize=(16.54, 11.69), facecolor=PALETTE["bg"])
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def add_title(ax, title: str, subtitle: str):
    ax.text(
        0.04,
        0.955,
        title,
        fontproperties=TITLE_FONT,
        color=PALETTE["ink"],
        va="top",
    )
    ax.text(
        0.04,
        0.922,
        subtitle,
        fontproperties=SUBTITLE_FONT,
        color=PALETTE["muted"],
        va="top",
    )
    ax.plot([0.04, 0.96], [0.895, 0.895], color="#d8d1c6", lw=1.3)


def box(ax, x: float, y: float, w: float, h: float, title: str, lines: list[str], fc: str, ec: str = "#c8c2b7"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.02",
        linewidth=1.2,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(x + 0.012, y + h - 0.018, title, fontproperties=BOX_TITLE_FONT, color=PALETTE["ink"], va="top")
    body = "\n".join(lines)
    ax.text(
        x + 0.012,
        y + h - 0.05,
        body,
        fontproperties=BOX_BODY_FONT,
        color=PALETTE["ink"],
        va="top",
        linespacing=1.45,
    )


def label(ax, x: float, y: float, text: str):
    ax.text(x, y, text, fontproperties=SECTION_FONT, color=PALETTE["ink"], va="bottom")


def arrow(ax, start: tuple[float, float], end: tuple[float, float], text: str = "", color: str | None = None, rad: float = 0.0):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=16,
        linewidth=1.5,
        color=color or PALETTE["line"],
        connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(patch)
    if text:
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2 + (0.014 if rad == 0 else 0.02)
        ax.text(mx, my, text, fontproperties=SMALL_FONT, color=PALETTE["muted"], ha="center", va="bottom")


def footer(ax, page_no: int):
    ax.text(
        0.04,
        0.03,
        "代码依据: app/main.py, app/streamlit_app.py, app/pages/1_Workspace.py, app/services/*, app/repositories/*",
        fontproperties=SMALL_FONT,
        color=PALETTE["muted"],
        va="bottom",
    )
    ax.text(0.96, 0.03, f"第 {page_no} 页", fontproperties=SMALL_FONT, color=PALETTE["muted"], ha="right", va="bottom")


def draw_page_overview(pdf: PdfPages):
    fig, ax = new_page()
    add_title(ax, "项目整体流程架构图", "覆盖前端入口、FastAPI 接口层、服务编排、RAG 核心链路、存储与降级路径。")

    label(ax, 0.05, 0.84, "1. 总体分层")

    box(ax, 0.05, 0.60, 0.18, 0.18, "用户入口", [
        "浏览器用户",
        "登录 / 注册",
        "角色切换",
        "上传资料 / 发起对话",
    ], PALETTE["panel_warm"])

    box(ax, 0.28, 0.52, 0.20, 0.32, "前端层", [
        "Streamlit 登录页",
        "app/streamlit_app.py",
        "",
        "Streamlit 工作台",
        "app/pages/1_Workspace.py",
        "",
        "静态前端",
        "frontend/index.html + app.js",
        "",
        "frontend_shared.py 负责 API 调用",
    ], PALETTE["panel"])

    box(ax, 0.53, 0.52, 0.19, 0.32, "应用入口层", [
        "FastAPI",
        "app/main.py",
        "",
        "路由注册",
        "/api/auth",
        "/api/chat",
        "/api/documents",
        "/api/roles",
        "",
        "auth 依赖负责 Bearer 鉴权",
    ], PALETTE["panel_alt"])

    box(ax, 0.76, 0.52, 0.19, 0.32, "业务服务层", [
        "AuthService",
        "RoleService",
        "DocumentService",
        "ChatService",
        "OfflineImportService",
        "",
        "ChatService 编排角色、文档范围、",
        "RAG 调用与会话持久化",
    ], PALETTE["panel"])

    box(ax, 0.18, 0.15, 0.24, 0.24, "RAG 核心", [
        "RAGEngine",
        "1) 读取短期记忆",
        "2) 组装 search query",
        "3) Milvus hybrid search",
        "4) Reranker 重排",
        "5) Prompt 组装",
        "6) LLM 生成回复",
    ], PALETTE["panel_alt"])

    box(ax, 0.45, 0.15, 0.23, 0.24, "文档入库链路", [
        "document_ingestion.py",
        "document_parser.py",
        "embedding.py",
        "",
        "保存原文件 -> 抽取文本 -> 切块",
        "向量化 -> 写入 Milvus",
        "同时写回本地 chunk 表",
    ], PALETTE["panel_warm"])

    box(ax, 0.71, 0.15, 0.24, 0.24, "存储与基础设施", [
        "MySQL / SQLite",
        "users, roles, documents, conversations",
        "milvus_index",
        "",
        "Milvus: 向量检索",
        "Redis: 短期记忆",
        "data/documents: 原始文件",
    ], PALETTE["panel_data"])

    arrow(ax, (0.23, 0.69), (0.28, 0.69), "访问 UI")
    arrow(ax, (0.48, 0.68), (0.53, 0.68), "HTTP / JSON")
    arrow(ax, (0.72, 0.68), (0.76, 0.68), "路由分发")
    arrow(ax, (0.82, 0.52), (0.82, 0.40), "聊天 / 上传 / 角色管理")
    arrow(ax, (0.65, 0.52), (0.58, 0.40), "文档上传")
    arrow(ax, (0.60, 0.52), (0.30, 0.40), "聊天请求")
    arrow(ax, (0.42, 0.27), (0.45, 0.27), "入库后供检索使用")
    arrow(ax, (0.68, 0.27), (0.71, 0.27), "持久化 / 缓存")

    ax.text(0.05, 0.46, "主设计特征", fontproperties=SECTION_FONT, color=PALETTE["ink"], va="bottom")
    ax.text(
        0.05,
        0.43,
        "单体应用 + 明确分层 + RAG 服务编排 + 本地降级机制。前端通过 Streamlit 驱动，后端通过 FastAPI 对外提供统一接口。",
        fontproperties=BOX_BODY_FONT,
        color=PALETTE["muted"],
        va="top",
    )

    footer(ax, 1)
    pdf.savefig(fig)
    plt.close(fig)


def draw_page_chat(pdf: PdfPages):
    fig, ax = new_page()
    add_title(ax, "在线问答流程", "对应用户在工作台发送消息后的实际处理路径，包含检索、重排、生成、记忆和会话落库。")

    label(ax, 0.05, 0.84, "2. 在线对话主链路")

    steps = [
        ("用户与前端", ["用户在 Workspace 输入消息", "process_prompt() 组织 role_requests", "frontend_shared.send_multi_role_chat()"]),
        ("FastAPI 接口", ["POST /api/chat/", "chat.py 懒加载 RAGEngine", "鉴权后交给 ChatService"]),
        ("ChatService 编排", ["解析 role_id / session_id", "计算有效 knowledge_domains", "查询当前用户可访问文档 doc_ids"]),
        ("RAGEngine 检索", ["读取最近短期记忆", "构建 search query", "Embedding 生成 dense + sparse 向量"]),
        ("召回与重排", ["Milvus hybrid_search", "失败时回退 _local_search", "reranker 选出 top-k 片段"]),
        ("Prompt 与生成", ["拼接角色 prompt + 历史 + 文档上下文", "LLMClient.chat_with_retry()", "失败时返回 timeout fallback"]),
        ("结果写回", ["MemoryService.push_message + TTL", "ConversationRepository.create()", "conversation_ingestion 异步入向量记忆"]),
    ]

    x = 0.05
    y = 0.62
    w = 0.12
    h = 0.16
    gap = 0.014
    colors = [
        PALETTE["panel_warm"],
        PALETTE["panel"],
        PALETTE["panel_alt"],
        PALETTE["panel"],
        PALETTE["panel_data"],
        PALETTE["panel_warm"],
        PALETTE["panel_alt"],
    ]

    centers = []
    for index, (title, lines) in enumerate(steps):
        current_x = x + index * (w + gap)
        box(ax, current_x, y, w, h, title, lines, colors[index])
        centers.append((current_x + w / 2, y + h / 2))
        if index < len(steps) - 1:
            arrow(ax, (current_x + w, y + h / 2), (current_x + w + gap, y + h / 2))

    box(ax, 0.08, 0.25, 0.25, 0.20, "短期记忆子系统", [
        "MemoryService 优先使用 Redis",
        "键格式: session:{user_id}:{role_id}:{session_id}",
        "Redis 不可用时退回进程内 _memory_store",
    ], PALETTE["panel_alt"])

    box(ax, 0.39, 0.25, 0.25, 0.20, "检索子系统", [
        "EmbeddingService 支持 dense / sparse",
        "MilvusClient 支持 hybrid_search",
        "Milvus 不可用时回退本地 chunk 表检索",
    ], PALETTE["panel_data"])

    box(ax, 0.70, 0.25, 0.22, 0.20, "持久化子系统", [
        "Conversation 表保存完整轮次",
        "retrieved_docs 一并落库",
        "后续可扩展长期记忆与历史检索",
    ], PALETTE["panel"])

    arrow(ax, centers[3], (0.205, 0.45), "读写会话", rad=0.15)
    arrow(ax, centers[4], (0.515, 0.45), "向量召回", rad=0.12)
    arrow(ax, centers[6], (0.81, 0.45), "保存结果", rad=-0.12)

    ax.text(0.05, 0.17, "降级路径", fontproperties=SECTION_FONT, color=PALETTE["ink"], va="bottom")
    ax.text(
        0.05,
        0.14,
        "Redis 故障时短期记忆退回内存；Milvus 故障时退回 SQL chunk 检索；LLM 超时或失败时返回基于已检索文档的兜底答案。",
        fontproperties=BOX_BODY_FONT,
        color=PALETTE["muted"],
        va="top",
    )

    footer(ax, 2)
    pdf.savefig(fig)
    plt.close(fig)


def draw_page_ingestion(pdf: PdfPages):
    fig, ax = new_page()
    add_title(ax, "文档入库与离线导入流程", "对应上传文档和本地导入文件时的处理路径，决定后续知识库检索效果。")

    label(ax, 0.05, 0.84, "3. 文档处理主链路")

    flow = [
        ("入口", ["上传文件", "或 OfflineImportService", "调用 upsert_local_file"]),
        ("DocumentService", ["校验当前用户", "读取 UploadFile", "传给 save_document"]),
        ("文本解析", ["document_parser.extract_text", "支持 txt / md / pdf / docx", "解析失败则报错"]),
        ("原件保存", ["保存到 data/documents", "文件名带 user_id + time_ns", "写入 Document 表"]),
        ("向量索引", ["chunk_text 切块", "encode_full 生成向量", "Milvus upsert"]),
        ("本地回写", ["replace_local_chunks", "写入 MilvusIndex chunk 表", "记录 milvus_ids 与 chunk_count"]),
        ("供在线检索", ["聊天时按 knowledge_domain 过滤", "Milvus 优先", "本地 chunk 作为回退"]),
    ]

    start_x = 0.06
    y = 0.56
    w = 0.12
    h = 0.18
    gap = 0.014

    for index, (title, lines) in enumerate(flow):
        current_x = start_x + index * (w + gap)
        fc = PALETTE["panel_warm"] if index in (0, 3) else PALETTE["panel"] if index in (1, 6) else PALETTE["panel_alt"] if index in (2, 5) else PALETTE["panel_data"]
        box(ax, current_x, y, w, h, title, lines, fc)
        if index < len(flow) - 1:
            arrow(ax, (current_x + w, y + h / 2), (current_x + w + gap, y + h / 2))

    box(ax, 0.08, 0.23, 0.23, 0.19, "结构化数据", [
        "Document",
        "title / content / file_path",
        "knowledge_domain / milvus_ids / chunk_count",
    ], PALETTE["panel_data"])

    box(ax, 0.39, 0.23, 0.23, 0.19, "向量与回退数据", [
        "Milvus 保存正式向量索引",
        "MilvusIndex 保存本地 chunk 文本",
        "支持本地检索降级",
    ], PALETTE["panel_alt"])

    box(ax, 0.70, 0.23, 0.22, 0.19, "影响后续问答", [
        "角色配置中的 knowledge_domains",
        "决定可检索文档范围",
        "文档质量直接影响最终回复",
    ], PALETTE["panel_warm"])

    arrow(ax, (0.53, 0.56), (0.195, 0.42), "元数据落库", rad=0.15)
    arrow(ax, (0.67, 0.56), (0.505, 0.42), "向量 + chunk", rad=0.12)
    arrow(ax, (0.90, 0.56), (0.81, 0.42), "供问答使用", rad=-0.1)

    ax.text(0.05, 0.15, "结论", fontproperties=SECTION_FONT, color=PALETTE["ink"], va="bottom")
    ax.text(
        0.05,
        0.12,
        "这个项目的核心闭环是: 用户上传文档形成知识库，角色对话按权限和领域过滤知识，再通过 RAG 生成答案，并把会话结果继续沉淀到短期记忆和会话库。",
        fontproperties=BOX_BODY_FONT,
        color=PALETTE["muted"],
        va="top",
    )

    footer(ax, 3)
    pdf.savefig(fig)
    plt.close(fig)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUTPUT) as pdf:
        draw_page_overview(pdf)
        draw_page_chat(pdf)
        draw_page_ingestion(pdf)
    print(f"generated: {OUTPUT}")


if __name__ == "__main__":
    main()
