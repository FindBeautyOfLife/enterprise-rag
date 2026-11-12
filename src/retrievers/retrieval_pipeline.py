
class RetrievalPipeline:

    def __init__(self, parent_retriever, reranker):
        self.parent_retriever = parent_retriever
        self.reranker = reranker

    def search(
        self,
        query,
        top_k=3,
        child_top_k=10,
        candidate_k=None,
        rerank_query=None
    ):
        """
        执行完整检索流水线。

        query：用于向量与关键词混合检索的问题
        rerank_query：用于重排序的问题，不传时使用原始问题
        top_k：最终返回的父文档数量
        child_top_k：混合检索阶段召回的子片段数量
        candidate_k：向量检索和 BM25 各自召回的候选数量
        """

        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        # 1. 执行混合检索，根据命中的子片段恢复并去重父段。
        parent_results = self.parent_retriever.search(
            query=query,
            top_k=child_top_k,
            child_top_k=child_top_k,
            candidate_k=candidate_k
        )

        # 2. 选择重排序使用的问题；未提供优化后的问题时使用原始问题。
        if rerank_query is None:
            rerank_query = query

        # 3. 对候选父段进行重排序，保留最相关的前 top_k 段。
        results = self.reranker.rerank(
            query=rerank_query,
            documents=parent_results,
            top_k=top_k
        )

        return results
