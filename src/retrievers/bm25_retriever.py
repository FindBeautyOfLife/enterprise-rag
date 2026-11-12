
import jieba
import numpy as np
from rank_bm25 import BM25Okapi


class BM25Retriever:

    def __init__(self):
        self.chunks = []
        self.bm25 = None

    def tokenize(self, text):
        return [
            word.strip()
            for word in jieba.lcut(text)
            if word.strip()
        ]

    def index(self, chunks):
        """对 Chunk 分词并建立 BM25 索引。"""
        self.chunks = list(chunks)

        if not self.chunks:
            raise ValueError("Chunk 列表不能为空")

        tokenized_chunks = [
            self.tokenize(chunk.page_content)
            for chunk in self.chunks
        ]

        self.bm25 = BM25Okapi(tokenized_chunks)

    def search(self, query, top_k=3):
        """根据 Query 进行 BM25 关键词检索。"""
        if self.bm25 is None:
            raise RuntimeError("请先调用 index() 构建索引")

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_tokens = self.tokenize(query)

        scores = self.bm25.get_scores(query_tokens)

        indices = np.argsort(-scores, kind="stable")[:top_k]

        results = []

        for idx in indices:
            results.append({
                "chunk_id": self.chunks[int(idx)].metadata.get(
                    "chunk_id", int(idx)
                ),
                "document": self.chunks[int(idx)],
                "score": float(scores[idx])
            })

        return results
