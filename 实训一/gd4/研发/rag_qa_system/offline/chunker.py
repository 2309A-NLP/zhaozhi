"""Text chunking utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


PAGE_MARKER_PATTERN = re.compile(r"^页码[:：]\s*\d+\s*$", re.MULTILINE)


@dataclass
class TextChunker:
    chunk_size: int = 700
    chunk_overlap: int = 120
    boundary_window: int = 120

    def split(self, text: str) -> List[str]:
        if not text:
            return []
        page_chunks = self._split_by_page_markers(text)
        if page_chunks is not None:
            return page_chunks
        return self._split_plain_text(text)

    def _split_by_page_markers(self, text: str) -> List[str] | None:
        matches = list(PAGE_MARKER_PATTERN.finditer(text))
        if not matches:
            return None

        chunks: List[str] = []
        for index, match in enumerate(matches):
            section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            header = match.group(0).strip()
            body = text[match.end() : section_end].strip()
            if not body:
                chunks.append(header)
                continue

            body_chunk_size = max(100, self.chunk_size - len(header) - 1)
            for body_chunk in self._split_plain_text(body, chunk_size=body_chunk_size):
                combined = f"{header}\n{body_chunk}".strip()
                if combined:
                    chunks.append(combined)
        return chunks

    def _split_plain_text(self, text: str, chunk_size: int | None = None) -> List[str]:
        effective_chunk_size = chunk_size or self.chunk_size
        if len(text) <= effective_chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + effective_chunk_size)
            if end < len(text):
                end = self._find_natural_boundary(text, start, end, chunk_size=effective_chunk_size)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            next_start = max(0, end - self.chunk_overlap)
            if next_start <= start:
                next_start = end
            start = next_start
        return chunks

    def _find_natural_boundary(self, text: str, start: int, fallback_end: int, chunk_size: int | None = None) -> int:
        effective_chunk_size = chunk_size or self.chunk_size
        min_end = min(len(text), start + max(1, effective_chunk_size // 2))
        search_start = max(start, fallback_end - self.boundary_window)
        candidates = [
            text.rfind(separator, search_start, fallback_end)
            for separator in ("\n\n", "\n", "。", "！", "？", "；", ";", ". ")
        ]
        boundary = max(candidates)
        if boundary >= min_end:
            matched = text[boundary : boundary + 2]
            return boundary + (2 if matched in {"\n\n", ". "} else 1)
        return fallback_end
