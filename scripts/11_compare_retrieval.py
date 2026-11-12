
from pathlib import Path
import sys

import numpy as np
from sentence_transformers import SentenceTransformer
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader


# ==================================================
# 1. 加载文档
# ==================================================
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

documents = DocxLoader(file_path).load()

print("原始 Document 数量：", len(documents))


# ==================================================
# 2. 文本切分
# ==================================================
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

original_chunks = splitter.split_documents(documents)

print("原始 Chunk 数量：", len(original_chunks))


# ==================================================
# 3. 构建标题增强 Chunk
# ==================================================
article_titles = {
    (doc.metadata["chapter"], doc.metadata["article"]):
        doc.page_content.split("\n")[0]
    for doc in documents
}

enhanced_chunks = []

for chunk in original_chunks:
    chapter = chunk.metadata["chapter"]
    article = chunk.metadata["article"]

    article_title = article_titles[(chapter, article)]

    if chunk.page_content.startswith(article_title):
        content = chunk.page_content
    else:
        content = (
            f"章节：{chapter}\n"
            f"条款：{article_title}\n\n"
            f"{chunk.page_content}"
        )

    enhanced_chunks.append(
        Document(
            page_content=content,
            metadata=chunk.metadata.copy()
        )
    )

print("增强 Chunk 数量：", len(enhanced_chunks))


# ==================================================
# 4. 加载 Embedding 模型
# ==================================================
model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5",
    device="cpu"
)

original_vectors = model.encode(
    [doc.page_content for doc in original_chunks],
    normalize_embeddings=True
)

enhanced_vectors = model.encode(
    [doc.page_content for doc in enhanced_chunks],
    normalize_embeddings=True
)

print("原始向量矩阵：", original_vectors.shape)
print("增强向量矩阵：", enhanced_vectors.shape)


# ==================================================
# 5. 构建两种 Query
# ==================================================
query = "南京信息工程大学学术委员会有哪些职责？"

instruction = "为这个句子生成表示以用于检索相关文章："

query_with_instruction = instruction + query

# 普通 Query 向量
query_vector_normal = model.encode(
    query,
    normalize_embeddings=True
)

# Instruction Query 向量
query_vector_instruction = model.encode(
    query_with_instruction,
    normalize_embeddings=True
)


# ==================================================
# 6. 定义检索函数
# ==================================================
def search(chunks, vectors, query_vector, top_k=3):
    scores = vectors @ query_vector
    indices = np.argsort(scores)[::-1]

    print(f"\nTop-{top_k} 检索结果：")

    for rank, idx in enumerate(indices[:top_k], start=1):
        print(
            f"Top {rank} | "
            f"{chunks[idx].metadata['article']} | "
            f"相似度：{scores[idx]:.4f}"
        )

    print("\n第三十七条的全部排名：")

    for rank, idx in enumerate(indices, start=1):
        if chunks[idx].metadata["article"] == "第三十七条":
            print(
                f"排名 {rank} | "
                f"相似度：{scores[idx]:.4f} | "
                f"内容开头：{chunks[idx].page_content[:40]}"
            )


# ==================================================
# 7. 三组对照实验
# ==================================================

print("\n========== Baseline：原始 Chunk + 普通 Query ==========")
search(
    original_chunks,
    original_vectors,
    query_vector_normal
)

print("\n========== 实验 A：增强 Chunk + 普通 Query ==========")
search(
    enhanced_chunks,
    enhanced_vectors,
    query_vector_normal
)

print("\n========== 实验 B：原始 Chunk + Instruction Query ==========")
search(
    original_chunks,
    original_vectors,
    query_vector_instruction
)
