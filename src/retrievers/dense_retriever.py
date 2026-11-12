
import numpy as np


class DenseRetriever:

    def __init__(self, embedding_model):
        self.embedding_model = embedding_model
        self.chunks = []
        self.vectors = None

    def index(self, chunks):
        """将 Chunk 转换为向量并建立内存索引。"""
        self.chunks = list(chunks)

        if not self.chunks:
            raise ValueError("Chunk 列表不能为空")

        texts = [chunk.page_content for chunk in self.chunks]

        self.vectors = self.embedding_model.embed_documents(texts)

    def search(self, query, top_k=3):
        """根据 Query 检索最相关的 Chunk。"""
        if self.vectors is None:
            raise RuntimeError("请先调用 index() 构建索引")

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_vector = self.embedding_model.embed_query(query)

        scores = self.vectors @ query_vector
        indices = np.argsort(-scores, kind="stable")[:top_k]

        results = []

        for idx in indices:
            results.append({
                "chunk_id": int(idx),
                "document": self.chunks[int(idx)],
                "score": float(scores[idx])
            })

        return results
