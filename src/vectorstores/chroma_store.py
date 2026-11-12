
import chromadb
from langchain_core.documents import Document


class ChromaStore:

    def __init__(
        self,
        persist_directory,
        collection_name,
        embedding_model
    ):
        self.embedding_model = embedding_model

        # 防止意外使用不同的 Pooling 策略
        pooling = embedding_model.model[1]
        if not pooling.pooling_mode_cls_token or pooling.pooling_mode_mean_tokens:
            raise ValueError("当前 Collection 要求 BGE CLS Pooling")

        self.client = chromadb.PersistentClient(
            path=str(persist_directory)
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={
                "embedding_model": "BAAI/bge-small-zh-v1.5",
                "schema_version": "2",
                "embedding_dim": 512
            }
        )

        metadata = self.collection.metadata or {}
        if (
            metadata.get("embedding_model") != "BAAI/bge-small-zh-v1.5"
            or metadata.get("schema_version") != "2"
            or metadata.get("embedding_dim") != 512
            or self.collection.configuration["hnsw"]["space"] != "cosine"
        ):
            raise ValueError("Collection 配置与当前索引版本不一致")

    def count(self):
        return self.collection.count()

    def sync_document(self, document_id, chunks):
        """
        同步一份文档的全部 Chunk。
        新增/修改时写入，已消失的旧 Chunk 删除。
        """
        chunks = list(chunks)

        if any(
            chunk.metadata.get("document_id") != document_id
            for chunk in chunks
        ):
            raise ValueError("Chunk 的 document_id 不一致")

        ids = [c.metadata["chunk_id"] for c in chunks]

        if len(ids) != len(set(ids)):
            raise ValueError("存在重复 chunk_id")

        # 取出该文档在数据库中的旧记录
        existing = self.collection.get(
            where={"document_id": document_id},
            include=["metadatas"]
        )

        old_records = {
            chunk_id: metadata
            for chunk_id, metadata in zip(
                existing["ids"],
                existing["metadatas"]
            )
        }

        # 仅重新编码新增或内容发生变化的 Chunk
        changed = [
            chunk for chunk in chunks
            if chunk.metadata["chunk_id"] not in old_records
            or old_records[chunk.metadata["chunk_id"]].get(
                "content_hash"
            ) != chunk.metadata["content_hash"]
        ]

        # 分批生成向量并写入，限制内存占用，避免超过 Chroma 单次请求的批量上限。
        for offset in range(0, len(changed), 128):
            batch = changed[offset:offset + 128]
            texts = [c.page_content for c in batch]
            vectors = self.embedding_model.embed_documents(texts)

            self.collection.upsert(
                ids=[c.metadata["chunk_id"] for c in batch],
                documents=texts,
                metadatas=[c.metadata for c in batch],
                embeddings=vectors.tolist()
            )

        # 删除当前版本已经不包含的旧 Chunk
        stale_ids = set(old_records) - set(ids)

        if stale_ids:
            self.collection.delete(ids=list(stale_ids))

        return {
            "updated": len(changed),
            "deleted": len(stale_ids),
            "total": len(chunks)
        }

    def delete_document(self, document_id):
        """删除指定文档的全部 Chunk。"""
        old = self.collection.get(
            where={"document_id": document_id},
            include=[]
        )

        if old["ids"]:
            self.collection.delete(ids=old["ids"])

        return len(old["ids"])

    def search(self, query, top_k=3):
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        if self.count() == 0:
            return []

        query_vector = self.embedding_model.embed_query(query)

        result = self.collection.query(
            query_embeddings=[query_vector.tolist()],
            n_results=min(top_k, self.count()),
            include=["documents", "metadatas", "distances"]
        )

        return [
            {
                "chunk_id": chunk_id,
                "document": Document(
                    page_content=content,
                    metadata=metadata
                ),
                "score": 1 - float(distance)
            }
            for chunk_id, content, metadata, distance in zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0]
            )
        ]
