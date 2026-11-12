
from sentence_transformers import CrossEncoder


class Reranker:

    def __init__(
        self,
        model_name="BAAI/bge-reranker-base",
        device="cpu"
    ):
        self.model = CrossEncoder(
            model_name,
            device=device
        )

    def rerank(self, query, documents, top_k=3):
        """对候选文档进行相关性重排序。"""

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        if not documents:
            return []

        # 1. 构造 Query-Document 对
        pairs = [
            (query, item["document"].page_content)
            for item in documents
        ]

        # 2. 批量计算相关性分数
        scores = self.model.predict(pairs)

        # 3. 保留原始信息，并添加 Rerank 分数
        results = []

        for item, score in zip(documents, scores):
            results.append({
                **item,
                "rerank_score": float(score)
            })

        # 4. 按 Rerank 分数降序排列
        results.sort(
            key=lambda item: item["rerank_score"],
            reverse=True
        )

        return results[:top_k]
