"""PDF parsing with layout-based cleanup for headers, footers, and watermarks."""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from rag_qa_system.backend.utils.text_utils import normalize_text


_MIN_REPEAT_LENGTH = 6


@dataclass
class PdfParser:
    header_ratio: float = 0.1
    footer_ratio: float = 0.08
    repeated_line_threshold: float = 0.6
    remove_page_number_lines: bool = True

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
        page_texts = [self._extract_page_text(page) for page in reader.pages]
        text = self._remove_repeated_page_lines(page_texts)
        text = normalize_text(text)
        if not text:
            raise ValueError(f"No text extracted from PDF: {path.name}")
        return text

    def _extract_page_text(self, page) -> str:
        page_height = float(page.mediabox.height or 0.0)
        header_limit = page_height * (1.0 - self.header_ratio)
        footer_limit = page_height * self.footer_ratio
        fragments: List[tuple[float, str]] = []

        def visitor_text(text: str, cm, tm, font_dict, font_size) -> None:
            candidate = normalize_text(text)
            if not candidate:
                return

            y = self._resolve_y_position(cm, tm)
            if page_height > 0:
                if y >= header_limit or y <= footer_limit:
                    return

            if self.remove_page_number_lines and self._looks_like_page_number(candidate):
                return
            fragments.append((y, candidate))

        page.extract_text(visitor_text=visitor_text, extraction_mode="layout")
        if not fragments:
            fallback = normalize_text(page.extract_text() or "")
            return self._remove_inline_page_noise(fallback)

        fragments.sort(key=lambda item: item[0], reverse=True)
        lines = [text for _, text in fragments]
        return self._remove_inline_page_noise("\n".join(lines))

    def _remove_repeated_page_lines(self, page_texts: List[str]) -> str:
        pages_lines: List[List[str]] = []
        counter: Counter[str] = Counter()

        for page_text in page_texts:
            unique_lines: List[str] = []
            seen: set[str] = set()
            for raw_line in page_text.splitlines():
                line = normalize_text(raw_line)
                if not line:
                    continue
                unique_lines.append(line)
                if len(line) >= _MIN_REPEAT_LENGTH and line not in seen:
                    counter[line] += 1
                    seen.add(line)
            pages_lines.append(unique_lines)

        page_count = max(len(pages_lines), 1)
        repeated_lines = {
            line
            for line, count in counter.items()
            if count / page_count >= self.repeated_line_threshold and not self._looks_like_meaningful_heading(line)
        }

        cleaned_pages: List[str] = []
        for lines in pages_lines:
            filtered = [line for line in lines if line not in repeated_lines]
            cleaned_pages.append("\n".join(filtered))
        return "\n\n".join(page for page in cleaned_pages if page.strip())

    def _remove_inline_page_noise(self, text: str) -> str:
        cleaned_lines: List[str] = []
        for raw_line in text.splitlines():
            line = normalize_text(raw_line)
            if not line:
                continue
            if self.remove_page_number_lines and self._looks_like_page_number(line):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    def _resolve_y_position(self, cm, tm) -> float:
        try:
            if tm and len(tm) > 5 and tm[5] is not None:
                return float(tm[5])
        except (TypeError, ValueError):
            pass
        try:
            if cm and len(cm) > 5 and cm[5] is not None:
                return float(cm[5])
        except (TypeError, ValueError):
            pass
        return 0.0

    def _looks_like_page_number(self, text: str) -> bool:
        compact = text.strip()
        if re.fullmatch(r"\d+\s*[-/]\s*\d+\s*[-/]\s*\d+", compact):
            return True
        if re.fullmatch(r"第?\s*\d+\s*页", compact):
            return True
        return bool(re.fullmatch(r"[0-9A-Za-z.\-_/]{1,12}", compact))

    def _looks_like_meaningful_heading(self, text: str) -> bool:
        compact = text.strip()
        if len(compact) <= 4:
            return True
        if re.search(r"[一二三四五六七八九十][、.]", compact):
            return True
        if "章" in compact or "节" in compact:
            return True
        return False
