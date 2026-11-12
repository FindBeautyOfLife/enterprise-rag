
from pathlib import Path
import sys

import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader


# ==================================================
# 1. 加载与切分文档
# ==================================================
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

documents = DocxLoader(file_path).load()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

chunks = splitter.split_documents(documents)

print("Document 数量：", len(documents))
print("Chunk 数量：", len(chunks))


# ==================================================
# 2. 向量检索
# ==================================================
model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5",
    device="cpu"
)

texts = [chunk.page_content for chunk in chunks]

chunk_vectors = model.encode(
    texts,
    normalize_embeddings=True
)

query = "南京信息工程大学学术委员会有哪些职责？"

query_vector = model.encode(
    query,
    normalize_embeddings=True
)

dense_scores = chunk_vectors @ query_vector

# 返回 Chunk 索引，按相似度降序排列
dense_indices = np.argsort(dense_scores)[::-1]


# ==================================================
# 3. BM25 关键词检索
# ==================================================
def tokenize(text):
    return [
        word.strip()
        for word in jieba.lcut(text)
        if word.strip()
    ]


tokenized_chunks = [
    tokenize(text) for text in texts
]

bm25 = BM25Okapi(tokenized_chunks)

bm25_scores = bm25.get_scores(
    tokenize(query)
)

bm25_indices = np.argsort(bm25_scores)[::-1]


# ==================================================
# 4. RRF 排名融合
# ==================================================
def rrf_fusion(rank_lists, k=60):
    scores = {}

    for rank_list in rank_lists:
        for rank, idx in enumerate(rank_list, start=1):
            idx = int(idx)

            scores[idx] = (
                scores.get(idx, 0)
                + 1 / (k + rank)
            )

    return sorted(
        scores.items(),
        key=lambda item: (-item[1], item[0])
    )


# 使用两组完整排名进行融合
hybrid_results = rrf_fusion(
    [dense_indices, bm25_indices],
    k=60
)


# ==================================================
# 5. 输出不同检索器的 Top-3
# ==================================================
def print_top3(name, indices, scores):
    print(f"\n========== {name} Top-3 ==========")

    for rank, idx in enumerate(indices[:3], start=1):
        print(
            f"Top {rank} | "
            f"Chunk ID：{idx} | "
            f"{chunks[idx].metadata['article']} | "
            f"分数：{scores[idx]:.4f}"
        )


print_top3("Dense", dense_indices, dense_scores)
print_top3("BM25", bm25_indices, bm25_scores)


# ==================================================
# 6. 输出 Hybrid Top-5
# ==================================================
print("\n========== Hybrid Search Top-5 ==========")

for rank, (idx, score) in enumerate(
    hybrid_results[:5],
    start=1
):
    chunk = chunks[idx]

    print(
        f"Top {rank} | "
        f"Chunk ID：{idx} | "
        f"{chunk.metadata['article']} | "
        f"RRF分数：{score:.6f}"
    )


# ==================================================
# 7. 第三十七条排名诊断
# ==================================================
print("\n========== 第三十七条排名对比 ==========")

dense_ranks = {
    int(idx): rank
    for rank, idx in enumerate(dense_indices, start=1)
}

bm25_ranks = {
    int(idx): rank
    for rank, idx in enumerate(bm25_indices, start=1)
}

for hybrid_rank, (idx, score) in enumerate(
    hybrid_results,
    start=1
):
    if chunks[idx].metadata["article"] == "第三十七条":
        print(f"\nChunk ID：{idx}")
        print(f"Dense 排名：{dense_ranks[idx]}")
        print(f"BM25 排名：{bm25_ranks[idx]}")
        print(f"Hybrid 排名：{hybrid_rank}")
        print(f"RRF 分数：{score:.6f}")
        print(f"内容开头：{chunks[idx].page_content[:50]}")


# ==================================================
# 8. 建立 Parent Store
# ==================================================
parent_store = {}

for doc in documents:
    parent_id = (
        doc.metadata["source"],
        doc.metadata["chapter"],
        doc.metadata["article"]
    )
    parent_store[parent_id] = doc


def get_parent_id(chunk):
    return (
        chunk.metadata["source"],
        chunk.metadata["chapter"],
        chunk.metadata["article"]
    )


# ==================================================
# 9. Hybrid 检索结果 → 父文档恢复
# ==================================================
top_k = 10

retrieved_results = hybrid_results[:top_k]

retrieved_parents = []
seen_parent_ids = set()

for chunk_idx, rrf_score in retrieved_results:

    chunk = chunks[chunk_idx]
    parent_id = get_parent_id(chunk)

    # 同一父文档只保留第一次出现的结果
    if parent_id in seen_parent_ids:
        continue

    seen_parent_ids.add(parent_id)

    parent_doc = parent_store[parent_id]

    retrieved_parents.append({
        "parent": parent_doc,
        "chunk_id": chunk_idx,
        "rrf_score": rrf_score
    })


print("\n========== Hybrid Top-10 父文档恢复 ==========")
print("召回子 Chunk 数量：", len(retrieved_results))
print("去重后父 Document 数量：", len(retrieved_parents))

for rank, item in enumerate(retrieved_parents, start=1):

    parent = item["parent"]

    print(f"\nParent {rank}")
    print(f"命中 Chunk ID：{item['chunk_id']}")
    print(f"所属条款：{parent.metadata['article']}")
    print(f"RRF 分数：{item['rrf_score']:.6f}")
    print(f"父文档字符数：{len(parent.page_content)}")

    if parent.metadata["article"] == "第三十七条":
        print("\n第三十七条完整内容：")
        print(parent.page_content)


# ==================================================
# 10. 对完整父文档进行 Rerank
# ==================================================
from sentence_transformers import CrossEncoder

reranker = CrossEncoder(
    "BAAI/bge-reranker-base",
    device="cpu"
)

# 使用之前实验过的两种 Query
queries = [
    "南京信息工程大学学术委员会有哪些职责？",
    "学术委员会有哪些职责？"
]

for rerank_query in queries:

    # 构造 Query-Parent Document 对
    pairs = [
        (rerank_query, item["parent"].page_content)
        for item in retrieved_parents
    ]

    # 计算 Rerank 分数
    rerank_scores = reranker.predict(pairs)

    # 按相关性分数重新排序
    ranked_indices = np.argsort(rerank_scores)[::-1]

    print(f"\n========== Rerank Query：{rerank_query} ==========")

    # 输出重排序后的 Top-5
    for rank, idx in enumerate(ranked_indices[:5], start=1):
        item = retrieved_parents[idx]
        parent = item["parent"]

        print(
            f"Top {rank} | "
            f"{parent.metadata['article']} | "
            f"Rerank分数：{float(rerank_scores[idx]):.4f}"
        )

    # 检查第三十七条的最终排名
    for rank, idx in enumerate(ranked_indices, start=1):
        parent = retrieved_parents[idx]["parent"]

        if parent.metadata["article"] == "第三十七条":
            print(
                f"\n第三十七条最终排名：{rank}"
                f" | 分数：{float(rerank_scores[idx]):.4f}"
            )
