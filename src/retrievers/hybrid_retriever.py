
class HybridRetriever:

    def __init__(self, dense_retriever, bm25_retriever, rrf_k=60):
        self.dense_retriever = dense_retriever
        self.bm25_retriever = bm25_retriever
        self.rrf_k = rrf_k

    def search(self, query, top_k=3, candidate_k=None):
        """
        执行 Dense + BM25 + RRF 混合检索。

        top_k：最终返回数量
        candidate_k：每个检索器的候选数量
        """

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        if candidate_k is None:
            candidate_k = top_k

        if candidate_k <= 0:
            raise ValueError("candidate_k 必须大于 0")

        # 1. 分别执行检索
        dense_results = self.dense_retriever.search(
            query, top_k=candidate_k
        )

        bm25_results = self.bm25_retriever.search(
            query, top_k=candidate_k
        )

        # 2. RRF 融合
        rrf_scores = {}
        documents = {}

        for results in [dense_results, bm25_results]:
            for rank, result in enumerate(results, start=1):
                chunk_id = result["chunk_id"]

                rrf_scores[chunk_id] = (
                    rrf_scores.get(chunk_id, 0)
                    + 1 / (self.rrf_k + rank)
                )

                documents[chunk_id] = result["document"]

        # 3. 按融合分数排序
        sorted_ids = sorted(
            rrf_scores,
            key=lambda idx: (-rrf_scores[idx], str(idx))
        )

        # 4. 统一返回
        return [
            {
                "chunk_id": chunk_id,
                "document": documents[chunk_id],
                "score": rrf_scores[chunk_id]
            }
            for chunk_id in sorted_ids[:top_k]
        ]
