"""Project entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    project_parent = Path(__file__).resolve().parent.parent
    if str(project_parent) not in sys.path:
        sys.path.insert(0, str(project_parent))

from rag_qa_system.backend.api.http_api import HttpApi
from rag_qa_system.backend.config import AppConfig
from rag_qa_system.backend.controllers.knowledge_controller import KnowledgeController
from rag_qa_system.backend.controllers.qa_controller import QAController
from rag_qa_system.backend.models.llm_client import EmbeddingClient, LLMClient, RerankerClient
from rag_qa_system.backend.repositories.milvus_repo import MilvusRepository
from rag_qa_system.backend.repositories.mysql_repo import MysqlRepository
from rag_qa_system.backend.repositories.redis_repo import RedisRepository
from rag_qa_system.backend.server import create_server
from rag_qa_system.backend.services.answer_service import AnswerService
from rag_qa_system.backend.services.knowledge_service import KnowledgeService
from rag_qa_system.backend.services.prompt_service import PromptService
from rag_qa_system.backend.services.retrieval_service import RetrievalService
from rag_qa_system.backend.utils.logger import get_logger, setup_logging
from rag_qa_system.offline.chunker import TextChunker
from rag_qa_system.offline.ingest import KnowledgeIngestor
from rag_qa_system.offline.pdf_parser import PdfParser


LOGGER = get_logger("rag.main")


def build_api(config: AppConfig | None = None) -> tuple[HttpApi, AppConfig]:
    config = config or AppConfig()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.pdf_dir.mkdir(parents=True, exist_ok=True)
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(config.app_log_file)

    mysql_repo = MysqlRepository(
        host=config.mysql_host,
        port=config.mysql_port,
        user=config.mysql_user,
        password=config.mysql_password,
        database=config.mysql_database,
    )

    embedding_client = EmbeddingClient(
        model_path=config.embedding_model_path,
        expected_dim=config.embedding_dim,
    )

    milvus_repo = MilvusRepository(
        host=config.milvus_host,
        port=config.milvus_port,
        collection_name=config.milvus_collection_name,
        embedding_dim=embedding_client.dimension,
    )

    redis_repo = RedisRepository(
        host=config.redis_host,
        port=config.redis_port,
        password=config.redis_password,
    )

    reranker_client = RerankerClient(
        model_path=config.reranker_model_path,
        enabled=config.enable_flag_reranker,
    )

    llm_client = LLMClient(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        model=config.llm_model,
        max_tokens=config.llm_max_tokens,
        temperature=config.llm_temperature,
        max_retries=config.llm_max_retries,
        timeout_seconds=config.llm_timeout_seconds,
    )

    retrieval_service = RetrievalService(
        embedding_client=embedding_client,
        reranker_client=reranker_client,
        milvus_repo=milvus_repo,
        redis_repo=redis_repo,
        retrieval_top_k=config.retrieval_top_k,
        rerank_top_k=config.rerank_top_k,
        cache_ttl_seconds=config.short_term_ttl,
    )

    answer_service = AnswerService(
        retrieval_service=retrieval_service,
        prompt_service=PromptService(context_doc_char_limit=config.context_doc_char_limit),
        llm_client=llm_client,
        mysql_repo=mysql_repo,
        top_k=config.rerank_top_k,
    )

    knowledge_service = KnowledgeService(
        project_root=config.project_root,
        pdf_dir=config.pdf_dir,
        uploads_dir=config.uploads_dir,
        mysql_repo=mysql_repo,
        milvus_repo=milvus_repo,
        ingestor=KnowledgeIngestor(
            parser=PdfParser(),
            chunker=TextChunker(chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap),
            embedding_client=embedding_client,
            mysql_repo=mysql_repo,
            milvus_repo=milvus_repo,
        ),
    )

    api = HttpApi(
        qa_controller=QAController(answer_service=answer_service),
        knowledge_controller=KnowledgeController(knowledge_service=knowledge_service),
    )

    return api, config


def run_server(host: str, port: int) -> None:
    api, config = build_api()
    server = create_server(host=host, port=port, api=api, frontend_dir=config.frontend_dir)
    LOGGER.info("server_start | host=%s | port=%s", host, port)
    print(f"Server running at http://{host}:{port}")
    server.serve_forever()


def run_demo(question: str) -> None:
    api, _ = build_api()
    LOGGER.info("demo_question | question=%r", question)
    print(api.post_answer({"question": question}))


def run_ingest(pdf_path: str) -> None:
    api, _ = build_api()
    LOGGER.info("ingest_start | pdf_path=%r", pdf_path)
    print(api.post_ingest_path({"pdf_path": pdf_path}))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runnable RAG PDF QA system")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="start the web server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8000, type=int)

    ingest_parser = subparsers.add_parser("ingest", help="ingest a PDF into the local knowledge base")
    ingest_parser.add_argument("pdf_path")

    demo_parser = subparsers.add_parser("demo", help="ask one question from the command line")
    demo_parser.add_argument("--question", default="武汉兴图新科电子股份有限公司法定代表人是谁？")

    return parser.parse_args()


def main() -> None:
    config = AppConfig()
    setup_logging(config.app_log_file)
    try:
        args = parse_args()
        if args.command == "ingest":
            run_ingest(args.pdf_path)
            return
        if args.command == "demo":
            run_demo(args.question)
            return
        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 8000)
        run_server(host=host, port=port)
    except Exception:
        LOGGER.exception("application_failed")
        raise


if __name__ == "__main__":
    main()
