
from pathlib import Path
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader

file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

# 1. 文档加载
documents = DocxLoader(file_path).load()

# 2. 文本切分
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

chunks = splitter.split_documents(documents)

print("Document 数量：", len(documents))
print("Chunk 数量：", len(chunks))

# 3. 加载 Embedding 模型
model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5",
    device="cpu"
)

# 4. 获取 Chunk 的文本
chunk_texts = [
    chunk.page_content
    for chunk in chunks
]

# 5. 批量生成 Embedding
chunk_vectors = model.encode(
    chunk_texts,
    normalize_embeddings=True,
    show_progress_bar=True
)

print("Chunk 向量矩阵形状：", chunk_vectors.shape)

import numpy as np

# 6. 输入查询
query = "南京信息工程大学学术委员会有哪些职责？"

# 7. 查询向量化
query_vector = model.encode(
    query,
    normalize_embeddings=True
)

# 8. 计算相似度
scores = chunk_vectors @ query_vector

# 9. 选出相似度最高的3个 Chunk
top_k = 3
top_indices = np.argsort(scores)[::-1][:top_k]

print("\n========== 检索结果 ==========")

for rank, idx in enumerate(top_indices, start=1):
    chunk = chunks[idx]

    print(f"\nTop {rank}")
    print(f"相似度：{scores[idx]:.4f}")
    print(f"章节：{chunk.metadata['chapter']}")
    print(f"条款：{chunk.metadata['article']}")
    print(f"内容：\n{chunk.page_content}")


# 查询第三十七条在所有检索结果中的排名

target_article = "第三十七条"

print("\n========== 第三十七条排名诊断 ==========")

for rank, idx in enumerate(np.argsort(scores)[::-1], start=1):
    chunk = chunks[idx]

    if chunk.metadata["article"] == target_article:
        print(f"全局排名：{rank}")
        print(f"相似度：{scores[idx]:.4f}")
        print(f"内容：{chunk.page_content[:100]}")
        print("-" * 40)
