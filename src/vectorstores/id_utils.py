
import hashlib
from collections import defaultdict
from langchain_core.documents import Document


def make_hash(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()[:16]


def prepare_chunks(chunks, document_key):
    """
    给 Chunk 分配结构化 ID。
    document_key 是文档的长期逻辑标识。
    """
    document_id = make_hash(document_key)
    counters = defaultdict(int)
    prepared = []

    for chunk in chunks:
        chapter = chunk.metadata["chapter"]
        article = chunk.metadata["article"]

        parent_id = make_hash(
            f"{document_id}|{chapter}|{article}"
        )

        chunk_index = counters[parent_id]
        counters[parent_id] += 1

        chunk_id = make_hash(
            f"{parent_id}|{chunk_index}"
        )

        metadata = {
            **chunk.metadata,
            "document_id": document_id,
            "parent_id": parent_id,
            "chunk_id": chunk_id,
            "chunk_index": chunk_index,
            "content_hash": make_hash(chunk.page_content)
        }

        prepared.append(
            Document(
                page_content=chunk.page_content,
                metadata=metadata
            )
        )

    return prepared
