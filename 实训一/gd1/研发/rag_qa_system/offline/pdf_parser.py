"""PDF parsing with pypdf fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from rag_qa_system.backend.utils.text_utils import normalize_text


@dataclass
class PdfParser:
    def parse(self, pdf_path: str) -> str:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required to parse PDF files") from exc

        logging.getLogger("pypdf").setLevel(logging.ERROR)
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages)
        text = normalize_text(text)
        if not text:
            raise ValueError(f"No text extracted from PDF: {path.name}")
        return text
