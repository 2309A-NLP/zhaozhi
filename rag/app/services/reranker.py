"""Rerank retrieved documents by relevance."""
from __future__ import annotations

import re
from typing import List

import torch

try:
    from FlagEmbedding import FlagReranker
except Exception:
    FlagReranker = None

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
except Exception:
    AutoModelForSequenceClassification = None
    AutoTokenizer = None

from ..config import config


def _tokenize(text: str) -> set[str]: # 查询字符串切分成token 集合
    # 将给定文本切分成token集合，用于简单的词重叠计算
    return set(re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text.lower()))


class BGERerankerService:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self.reranker = None
        self.hf_tokenizer = None
        self.hf_model = None
        self.backend = "fallback"

    def _ensure_model(self):
        # 按优先级尝试加载可用的重排序模型后端
        if not config.ENABLE_FLAGRERANKER:
            return
        if self.reranker is not None or self.hf_model is not None:
            return

        if FlagReranker is not None:
            try:
                self.reranker = FlagReranker(self.model_name, use_fp16=False)
                self.backend = "flagembedding"
                return
            except Exception:
                self.reranker = None

        if AutoTokenizer is not None and AutoModelForSequenceClassification is not None:
            try:
                self.hf_tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.hf_model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
                self.hf_model.eval()
                self.backend = "huggingface"
                return
            except Exception:
                self.hf_tokenizer = None
                self.hf_model = None

    def _fallback_score(self, query: str, document: str) -> float:
        query_tokens = _tokenize(query) # 将query查询字符串切分成token 集合
        doc_tokens = _tokenize(document)  # 同上
        if not query_tokens or not doc_tokens:
            return 0.0
        return len(query_tokens & doc_tokens) / len(query_tokens) # 查询词覆盖率

    def _hf_scores(self, query: str, documents: List[str]) -> List[float]:
        pairs = [[query, doc] for doc in documents] # 将查询与每个文档配对
        encoded = self.hf_tokenizer(
            pairs,
            padding=True, # 将批次内所有样本填充到相同长度
            truncation=True, # 超过 max_length 时截断
            max_length=512, # 模型允许的最大输入长度
            return_tensors="pt", # 返回 PyTorch 张量格式
        )
        with torch.inference_mode(): # 上下文管理器，禁用梯度计算和反向传播，降低内存消耗并加速推理。
            logits = self.hf_model(**encoded).logits
            # 将编码后的输入解包传递给预训练模型
            # .logits 是取模型的原始输出 logits
        return logits.view(-1). float().     tolist()
        # 将 logits 张量展平为一维.取浮点转换为数.普通 Python 列表，作为函数返回值

    def rerank(self, query: str, documents: List[str], top_k: int = 5):
        self._ensure_model()
        if self.reranker is not None: # 判断是否有高级重排序器
            scores = self.reranker.compute_score([[query, doc] for doc in documents], normalize=True)
            # compute_score 是重排序模型的核心方法，它接收一组 (query, document) 对，并返回每个对的相似度/相关性分数。
        elif self.hf_model is not None and self.hf_tokenizer is not None:
            scores = self._hf_scores(query, documents)
        else:
            scores = [self._fallback_score(query, doc) for doc in documents]
        return sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]

    def rerank_with_docs(self, query, docs_with_text, top_k=5):
        # docs_with_text  候选文档列表，每个元素是一个字典，至少包含键 "text"（文档内容），可能还有其他元数据（如 doc_id、score 等）
        if not docs_with_text:
            return []
        reranked = self.rerank(query, [doc["text"] for doc in docs_with_text], top_k)
        results = []
        for idx, score in reranked:
            doc = docs_with_text[idx].copy() # docs_with_text 是一个列表，每个元素是字典，所以doc也是一个字典
            doc["rerank_score"] = float(score) # 在doc这个字典中添加分数
            results.append(doc)
        return results
