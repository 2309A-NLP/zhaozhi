"""Text normalization, scoring, and excerpt helpers."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, List


STOPWORDS = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "与",
    "及",
    "有",
    "吗",
    "呢",
    "啊",
    "请",
    "问",
    "根据",
    "多少",
    "哪些",
    "什么",
    "哪个",
    "公司",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", text)
    return text.strip()


def split_tokens(text: str) -> List[str]:
    normalized = normalize_text(text).lower()
    latin_tokens = re.findall(r"[a-z0-9]+", normalized)
    chinese_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    chinese_ngrams: List[str] = []
    for sequence in chinese_sequences:
        chinese_ngrams.extend(_sequence_ngrams(sequence))
    return latin_tokens + chinese_ngrams


def _sequence_ngrams(sequence: str) -> List[str]:
    tokens: List[str] = []
    for size in (2, 3, 4):
        if len(sequence) < size:
            continue
        tokens.extend(sequence[index : index + size] for index in range(0, len(sequence) - size + 1))
    if len(sequence) <= 4:
        tokens.append(sequence)
    return tokens


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
    parts = re.split(r"(?:[。！？；.!?;]+|\n{2,})", normalized)
    return [part.strip(" ，,") for part in parts if part.strip()]


def overlap_score(query: str, candidate: str) -> float:
    query_counts = Counter(keyword_tokens(query))
    candidate_counts = Counter(keyword_tokens(candidate))
    if not query_counts or not candidate_counts:
        return 0.0
    common = sum(min(query_counts[token], candidate_counts[token]) for token in query_counts)
    return common / max(1, sum(query_counts.values()))


def best_matching_excerpt(query: str, text: str, max_chars: int, max_sentences: int = 3) -> str:
    if max_chars <= 0:
        return ""

    normalized = normalize_text(text)
    if len(normalized) <= max_chars:
        return normalized

    sentences = extract_sentences(normalized)
    if not sentences:
        return normalized[:max_chars]

    scores = [overlap_score(query, sentence) for sentence in sentences]
    best_index, best_score = max(enumerate(scores), key=lambda item: (item[1], -item[0]))
    if best_score <= 0:
        return normalized[:max_chars]

    left = right = best_index
    selected = [sentences[best_index]]
    total_chars = len(sentences[best_index])

    while len(selected) < max_sentences:
        candidate_indexes = [index for index in (left - 1, right + 1) if 0 <= index < len(sentences)]
        if not candidate_indexes:
            break
        next_index = max(candidate_indexes, key=lambda index: (scores[index], -abs(index - best_index)))
        sentence = sentences[next_index]
        projected_chars = total_chars + len(sentence) + 1
        if projected_chars > max_chars:
            break
        if next_index < left:
            left = next_index
            selected.insert(0, sentence)
        else:
            right = next_index
            selected.append(sentence)
        total_chars = projected_chars

    return "。".join(selected)[:max_chars]
