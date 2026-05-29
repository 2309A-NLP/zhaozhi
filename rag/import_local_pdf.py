"""将本地 PDF 文件导入知识库."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.database.mysql_client import mysql_client
from app.services.offline_import_service import OfflineImportService


def build_parser() -> argparse.ArgumentParser:
    """构建parser相关逻辑。
    """
    parser = argparse.ArgumentParser(description="Import local PDF files into the knowledge base.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=[],
        help="PDF file paths. If empty, import all PDFs in the current directory.",
    )
    parser.add_argument("--user-id", type=int, default=1, help="Target user_id. Defaults to 1.")
    parser.add_argument(
        "--knowledge-domain",
        default="general",
        help="Knowledge domain stored with the document. Defaults to general.",
    )
    return parser


def resolve_paths(raw_paths: list[str]) -> list[Path]:
    """处理resolve_paths相关逻辑。

    参数：
        raw_paths: 调用方传入的原始路径字符串列表。
    """
    if raw_paths:
        paths = [Path(item).resolve() for item in raw_paths]
    else:
        search_roots = [
            Path.cwd(),
            Path.cwd() / "assets" / "reference_docs",
        ]
        paths = []
        for root in search_roots:
            if root.exists():
                paths.extend(sorted(root.glob("*.pdf")))
    pdf_paths = [path for path in paths if path.exists() and path.is_file() and path.suffix.lower() == ".pdf"]
    if not pdf_paths:
        raise SystemExit("No PDF files found to import.")
    return pdf_paths


async def import_files(paths: list[Path], user_id: int, knowledge_domain: str) -> None:
    """导入files相关逻辑。

    参数：
        paths: 当前函数处理的文件路径集合。
        user_id: 当前函数使用的用户 ID。
        knowledge_domain: 用于存储或过滤的知识领域标签。
    """
    await mysql_client.init_db()
    async with mysql_client.async_session_maker() as session:
        service = OfflineImportService(session)
        for path in paths:
            document = await service.import_file(
                file_path=path,
                user_id=user_id,
                knowledge_domain=knowledge_domain,
            )
            print(
                f"Imported: {path.name} | doc_id={document.id} | "
                f"domain={document.knowledge_domain} | chunks={document.chunk_count}"
            )
    await mysql_client.close()


def main() -> None:
    """执行主入口流程。
    """
    parser = build_parser()
    args = parser.parse_args()
    paths = resolve_paths(args.paths)
    asyncio.run(import_files(paths, args.user_id, args.knowledge_domain))


if __name__ == "__main__":
    main()
