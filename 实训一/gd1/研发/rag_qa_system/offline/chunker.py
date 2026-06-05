"""Text chunking utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TextChunker:
    chunk_size: int = 700
    chunk_overlap: int = 120

    def split(self, text: str) -> List[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            start = max(0, end - self.chunk_overlap)
        return chunks

