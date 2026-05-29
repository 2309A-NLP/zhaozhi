"""Provide text chunking and embedding services."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np

try:
    from FlagEmbedding import BGEM3FlagModel
except Exception:
    BGEM3FlagModel = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

from ..config import config


class BGEEmbeddingService:
    QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

    def __init__(self, model_name: str = "BAAI/bge-m3", dim: int | None = None):
        self.model_name = model_name
        self.dim = dim or config.EMBEDDING_DIM
        self.model = None
        self.model_backend = "fallback"

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text.lower())

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vector)  # 计算向量vector的L2范数（欧几里得长度），结果复制norm
        return vector if norm == 0 else vector / norm
    # 判断如果 norm == 0（即向量全为零向量），则直接返回原向量（除零会导致错误）。
    # 否则，将向量的每个分量除以 norm，得到与原向量同方向的单位向量（长度为 1）。
    #

    @staticmethod
    def _looks_like_sentence_transformer_model(model_name: str) -> bool:
        lowered = model_name.lower()
        if "m3e" in lowered:
            return True
        model_path = Path(model_name)
        return model_path.exists() and (model_path / "modules.json").exists()
# 10.223.11.92
    @classmethod
    def _prepare_texts(cls, texts: List[str], is_query: bool) -> List[str]:
        if not is_query: # 判断当前文本需不需要查询，不许要则直接返回原文本
            return texts
        return [f"{cls.QUERY_INSTRUCTION}{text}" for text in texts]  # 原始 text 拼接起来，形成新的字符串

    def _fit_dense_dim(self, vectors: np.ndarray) -> np.ndarray:
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        current_dim = vectors.shape[1] if vectors.size else 0 # 获取当前向量的维度
        if current_dim == self.dim:
            return vectors.astype(np.float32)
        if current_dim > self.dim:
            return vectors[:, : self.dim].astype(np.float32) # 裁剪多余的列
        padded = np.zeros((vectors.shape[0], self.dim), dtype=np.float32)
        if current_dim:
            padded[:, :current_dim] = vectors  # 将原 vectors 的所有数据复制到 padded 的前 current_dim 列中（左侧对齐），剩余列保持为零
        return padded

    def _ensure_model(self):
        if not config.ENABLE_FLAGEMBEDDING or self.model is not None:
            return

        if self._looks_like_sentence_transformer_model(self.model_name) and SentenceTransformer is not None:
            try:
                self.model = SentenceTransformer(self.model_name)
                self.model_backend = "sentence_transformer"
                return
            except Exception:
                self.model = None

        if BGEM3FlagModel is not None:
            try:
                self.model = BGEM3FlagModel(self.model_name, use_fp16=False)
                self.model_backend = "bgem3"
                return
            except Exception:
                self.model = None

        if SentenceTransformer is not None:
            try:
                self.model = SentenceTransformer(self.model_name)
                self.model_backend = "sentence_transformer"
                return
            except Exception:
                self.model = None

        self.model_backend = "fallback"

    def _fallback_dense(self, texts: Iterable[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            vector = np.zeros(self.dim, dtype=np.float32) # 定义一个长度为dim的全零向量
            for token in self._tokenize(text):
                vector[hash(token) % self.dim] += 1.0
                # 计算每个token的哈希值，并对dim取模，得到vector中的一个索引，接着对这个索引对应的值+1.0
            vectors.append(self._normalize(vector))
            # 在完成当前文本所有 token 的哈希计数后，调用 self._normalize(vector) 对得到的计数向量进行归一化（通常为 L2 归一化，
            # 使向量长度为 1）。然后将归一化后的向量添加到 vectors 列表中。
        return np.array(vectors) # 转数组

    def _fallback_sparse(self, texts: Iterable[str]) -> List[Dict[int, float]]:
        # 将一批文本（字符串列表）转换成稀疏的向量表示
        results = []
        for text in texts:
            token_weights: Dict[int, float] = {}
            for token in self._tokenize(text):
                token_id = hash(token) % 50000
                # hash(token)，为 token 生成一个整数哈希值
                token_weights[token_id] = token_weights.get(token_id, 0.0) + 1.0
            results.append(token_weights)
        return results

    def encode_dense(self, texts: List[str], is_query: bool = True) -> np.ndarray:
        self._ensure_model()  # 确认模型对象正确初始化
        if self.model is None:
            return self._fallback_dense(self._prepare_texts(texts, is_query))

        if self.model_backend == "sentence_transformer":
            # 判断当前配置的模型后端名称是否为 "sentence_transformer"
            vectors = self.model.encode(
                self._prepare_texts(texts, is_query),
                convert_to_numpy=True, # 要求 encode 方法返回 NumPy 数组
                normalize_embeddings=True, # 向量归一化，将生成的稠密向量归一化为单位长度
                show_progress_bar=False, # 隐藏进度条
            )
            return self._fit_dense_dim(np.array(vectors, dtype=np.float32)) # 调整维度并返回

        output = self.model.encode(  # 其他后端
            texts,
            return_dense=True, # 要求模型输出稠密向量
            return_sparse=False, # 不返回稀疏向量
            return_colbert_vecs=False, # 不返回 ColBERT 向量
            is_query=is_query, # 传递查询标志
        )
        return self._fit_dense_dim(np.array(output["dense_vecs"], dtype=np.float32))

    def encode_sparse(self, texts: List[str]) -> List[Dict[int, float]]:
        self._ensure_model()
        if self.model is None or self.model_backend != "bgem3":
            return self._fallback_sparse(texts)
        output = self.model.encode(
            texts,
            return_dense=False,# 不返回稠密向量
            return_sparse=True,# 要求模型输出稀疏向量
            return_colbert_vecs=False,# 不返回 ColBERT 向量
        )
        return output["lexical_weights"]  # 每个文本的稀疏向量表示。返回给调用方

    def encode_full(self, texts: List[str]):
        self._ensure_model()
        if self.model is None:
            return self._fallback_dense(texts), self._fallback_sparse(texts)
        if self.model_backend == "sentence_transformer":
            return self.encode_dense(texts, is_query=False), self._fallback_sparse(texts)
        output = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        return self._fit_dense_dim(np.array(output["dense_vecs"], dtype=np.float32)), output["lexical_weights"]

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]: # 文本分块
        normalized = re.sub(r"\r\n?", "\n", text).strip()
        if not normalized: # 如果列表为空，则直接返回空列表
            return []

        paragraphs = [paragraph.strip() for paragraph in normalized.split("\n") if paragraph.strip()]
        # 按换行符 '\n' 分割标准化文本得到若干行，对每行去除首尾空白，并过滤掉空行，
        # 最终得到一个段落列表 paragraphs。
        chunks: List[str] = [] # 初始话一个空列表，用于存储最终生成的所有文本块
        current = "" # 初始化当前正在构建的块，初始为空
        step = max(chunk_size - overlap, 1)
        # 计算分块时在长段落内移动的步长。
        # 通常步长 = 块大小 - 重叠量，但至少为1，避免死循环。

        for paragraph in paragraphs:
            candidate = f"{current}\n{paragraph}".strip() if current else paragraph
            # 如果 current 非空，则尝试将当前段落与已有内容拼接，中间加换行符，然后去除首尾空白；
            # 如果 current 为空，则候选块直接就是当前段落。
            # 这个 candidate 是尝试合并后的结果。
            if len(candidate) <= chunk_size:
                current = candidate
                continue
            # 如果尝试合并后的长度不超过 chunk_size，则将 candidate 设为新的 current，并继续处理下一个段落。
            if current:
                chunks.append(current)
            # 执行到这里说明合并 candidate 会超过 chunk_size，且当前已有 current，
            # 因此将 current 作为一个完整的块加入到 chunks 列表中。
            if len(paragraph) <= chunk_size:
                current = paragraph
                continue
            # 如果当前段落本身的长度不超过 chunk_size，则将其作为新的 current，并继续下一个段落。
            for start in range(0, len(paragraph), step):
                piece = paragraph[start:start + chunk_size].strip()
                if piece:
                    chunks.append(piece)
            # 如果段落长度超过 chunk_size，则需要将该段落进一步切分成多个小块。
            # 从索引 0 开始，以步长 step 移动起始位置，每次取 chunk_size 长度的子串，
            # 去除该子串首尾空白后，若非空则作为一个独立的块加入 chunks。
            current = ""
            # 完成对长段落的切分后，将 current 重置为空，因为该段落已经被完全处理完毕，
            # 新的块应该从下一个段落的开头重新累积。
        if current:
            chunks.append(current)
        # 循环结束后，如果 current 中还有剩余内容，则将其作为一个块加入 chunks。
        return chunks
        # 返回最终生成的所有文本块列表。
