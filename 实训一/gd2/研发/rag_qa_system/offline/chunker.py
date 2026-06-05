"""Text chunking utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from rag_qa_system.backend.utils.text_utils import extract_sentences, normalize_text


@dataclass
class TextChunker:
    chunk_size: int = 700
    chunk_overlap: int = 120

    def split(self, text: str) -> List[str]:
        normalized = normalize_text(text)
        if not normalized:
            return []
        if len(normalized) <= self.chunk_size:
            return [normalized]

        sentences = extract_sentences(normalized)
        if not sentences or self._should_use_window_strategy(sentences):
            return self._split_by_window(normalized)

        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            sentence_len = len(sentence)
            projected = current_len + sentence_len + (1 if current else 0)
            if current and projected > self.chunk_size:
                chunks.append("。".join(current))
                current = self._overlap_tail(current)
                current_len = sum(len(item) for item in current) + max(0, len(current) - 1)
            if sentence_len > self.chunk_size:
                oversized = self._split_by_window(sentence)
                if current:
                    chunks.append("。".join(current))
                    current = []
                    current_len = 0
                chunks.extend(oversized[:-1])
                current = [oversized[-1]] if oversized else []
                current_len = len(current[0]) if current else 0
                continue
            current.append(sentence)
            current_len += sentence_len + (1 if len(current) > 1 else 0)

        if current:
            chunks.append("。".join(current))
        return [chunk for chunk in chunks if chunk.strip()]

    def _split_by_window(self, text: str) -> List[str]:
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

    def _overlap_tail(self, sentences: List[str]) -> List[str]:
        if not sentences or self.chunk_overlap <= 0:
            return []
        carried: List[str] = []
        carried_len = 0
        for sentence in reversed(sentences):
            projected = carried_len + len(sentence) + (1 if carried else 0)
            if projected > self.chunk_overlap and carried:
                break
            carried.append(sentence)
            carried_len = projected
            if carried_len >= self.chunk_overlap:
                break
        carried.reverse()
        return carried

    def _should_use_window_strategy(self, sentences: List[str]) -> bool:
        if len(sentences) < 4:
            return False
        average_len = sum(len(sentence) for sentence in sentences) / len(sentences)
        short_ratio = sum(1 for sentence in sentences if len(sentence) <= 18) / len(sentences)
        return average_len < max(24, self.chunk_size / 8) or short_ratio >= 0.45
