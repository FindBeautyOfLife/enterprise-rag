
class ParentRetriever:

    def __init__(self, child_retriever, parent_documents):
        self.child_retriever = child_retriever
        parent_documents = list(parent_documents)
        # 旧脚本仅给子片段分配结构化 ID，因此根据父段的元数据选择定位方式，
        # 兼容旧脚本使用的“文件名、章节、条款”三元组定位。
        self.structured_ids = bool(parent_documents) and all(
            "parent_id" in doc.metadata for doc in parent_documents
        )

        # 建立父文档索引
        self.parent_store = {}

        for doc in parent_documents:
            parent_id = self._get_parent_id(doc)
            self.parent_store[parent_id] = doc

    def _get_parent_id(self, doc):
        if self.structured_ids:
            return doc.metadata["parent_id"]
        return (
            doc.metadata["source"],
            doc.metadata["chapter"],
            doc.metadata["article"]
        )

    def search(
        self,
        query,
        top_k=3,
        child_top_k=10,
        candidate_k=None
    ):
        """检索子 Chunk，恢复并去重父文档。"""

        if top_k <= 0 or child_top_k <= 0:
            raise ValueError("top_k 和 child_top_k 必须大于 0")

        # 1. 调用子检索器
        child_results = self.child_retriever.search(
            query,
            top_k=child_top_k,
            candidate_k=candidate_k
        )

        # 2. 根据 Metadata 恢复父文档
        results = []
        seen_parent_ids = set()

        for item in child_results:
            child_doc = item["document"]
            parent_id = self._get_parent_id(child_doc)

            if parent_id in seen_parent_ids:
                continue

            parent_doc = self.parent_store.get(parent_id)

            if parent_doc is None:
                raise KeyError(f"找不到父文档：{parent_id}")

            seen_parent_ids.add(parent_id)

            results.append({
                "parent_id": parent_id,
                "document": parent_doc,
                "score": item["score"],
                "chunk_id": item["chunk_id"]
            })

            if len(results) >= top_k:
                break

        return results
