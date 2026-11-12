
from pathlib import Path
import sys

import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader


# ==================================================
# 1. 加载文档
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
# 2. 定义中文分词函数
# ==================================================
def tokenize(text):
    return [
        word.strip()
        for word in jieba.lcut(text)
        if word.strip()
    ]


# ==================================================
# 3. 定义 BM25 检索函数
# ==================================================
def search_bm25(chunks, query, top_k=3):

    # 文档分词
    tokenized_chunks = [
        tokenize(chunk.page_content)
        for chunk in chunks
    ]

    # 构建 BM25 索引
    bm25 = BM25Okapi(tokenized_chunks)

    # 查询分词
    query_tokens = tokenize(query)

    print("查询分词结果：", query_tokens)

    # 计算 BM25 分数
    scores = bm25.get_scores(query_tokens)

    # 按分数降序排列
    indices = np.argsort(scores)[::-1]

    # 输出 Top-K
    print(f"\nTop-{top_k} 检索结果：")

    for rank, idx in enumerate(indices[:top_k], start=1):
        print(
            f"Top {rank} | "
            f"{chunks[idx].metadata['article']} | "
            f"BM25分数：{scores[idx]:.4f}"
        )

    # 输出第三十七条全部排名
    print("\n第三十七条的全部排名：")

    for rank, idx in enumerate(indices, start=1):

        if chunks[idx].metadata["article"] == "第三十七条":
            print(
                f"排名 {rank} | "
                f"BM25分数：{scores[idx]:.4f} | "
                f"内容开头：{chunks[idx].page_content[:40]}"
            )


# ==================================================
# 4. 准备查询问题
# ==================================================
query = "南京信息工程大学学术委员会有哪些职责？"


# ==================================================
# 5. 实验一：默认 jieba 分词
# ==================================================
print("\n========== Baseline：默认 BM25 ==========")

search_bm25(
    chunks=chunks,
    query=query
)


# ==================================================
# 6. 添加领域专有词汇
# ==================================================
jieba.add_word("学术委员会")
jieba.add_word("学校党委")
jieba.add_word("学位评定委员会")


# ==================================================
# 7. 实验二：自定义词典 BM25
# ==================================================
print("\n========== 实验 A：自定义词典 BM25 ==========")

search_bm25(
    chunks=chunks,
    query=query
)

from langchain_core.documents import Document

# 创建实验用 Chunk 列表，不修改原始数据
test_chunks = [
    Document(
        page_content=chunk.page_content,
        metadata=chunk.metadata.copy()
    )
    for chunk in chunks
]

# 只增强第三十七条的职责 Chunk
for chunk in test_chunks:
    if (
        chunk.metadata["article"] == "第三十七条"
        and not chunk.page_content.startswith("第三十七条")
    ):
        chunk.page_content = (
            "学术委员会：\n" + chunk.page_content
        )

print("\n========== 实验 B：主体增强 BM25 ==========")

search_bm25(
    chunks=test_chunks,
    query=query
)
