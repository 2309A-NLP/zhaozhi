"""Text normalization, tokenization, and scoring helpers."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, List

try:
    import jieba
except ImportError:  # pragma: no cover - optional dependency fallback
    jieba = None


STOPWORDS = {
    "的",
    "了",
    "是",
    "在",
    "和",
    "与",
    "及",
    "或",
    "为",
    "对",
    "中",
    "由",
    "于",
    "根据",
    "多少",
    "哪些",
    "什么",
    "哪个",
    "公司",
    "发行人",
    "本公司",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", text)
    return text.strip()


def split_tokens(text: str) -> List[str]:
    normalized = normalize_text(text).lower()
    latin_tokens = re.findall(r"[a-z0-9]+", normalized)
    chinese_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    chinese_tokens: List[str] = []

    for sequence in chinese_sequences:
        chinese_tokens.extend(_segment_chinese(sequence))
        chinese_tokens.extend(_sequence_ngrams(sequence))

    return latin_tokens + chinese_tokens


def _segment_chinese(sequence: str) -> List[str]:
    if jieba is None:
        return []
    try:
        return [
            token.strip()
            for token in jieba.cut(sequence, cut_all=False)
            if len(token.strip()) >= 2 and token.strip() not in STOPWORDS
        ]
    except Exception:
        return []


def _sequence_ngrams(sequence: str) -> List[str]:
    tokens: List[str] = []
    for size in (2, 3, 4):
        if len(sequence) < size:
            continue
        tokens.extend(sequence[index : index + size] for index in range(0, len(sequence) - size + 1))
    if len(sequence) <= 4:
        tokens.append(sequence)
    return tokens


def _deduplicate_preserve_order(tokens: List[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def keyword_tokens(text: str) -> List[str]:
    return [token for token in split_tokens(text) if token not in STOPWORDS]


def hashed_vector(tokens: Iterable[str], size: int = 64) -> List[float]:
    buckets = [0.0] * size
    for token in tokens:
        buckets[hash(token) % size] += 1.0
    length = math.sqrt(sum(value * value for value in buckets)) or 1.0
    return [value / length for value in buckets]


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def extract_sentences(text: str) -> List[str]:
    normalized = normalize_text(text)
    parts = re.split(r"[。！？；\n]", normalized)
    return [part.strip() for part in parts if part.strip()]


def overlap_score(query: str, candidate: str) -> float:
    query_counts = Counter(keyword_tokens(query))
    candidate_counts = Counter(keyword_tokens(candidate))
    if not query_counts or not candidate_counts:
        return 0.0
    common = sum(min(query_counts[token], candidate_counts[token]) for token in query_counts)
    return common / max(1, sum(query_counts.values()))
