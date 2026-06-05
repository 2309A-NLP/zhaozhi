"""Text chunking utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TextChunker:
    chunk_size: int = 700
    chunk_overlap: int = 120
    boundary_window: int = 120

    def split(self, text: str) -> List[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            if end < len(text):
                end = self._find_natural_boundary(text, start, end)
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

    def _find_natural_boundary(self, text: str, start: int, fallback_end: int) -> int:
        min_end = min(len(text), start + max(1, self.chunk_size // 2))
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
