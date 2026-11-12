
from pathlib import Path
import sys

import chromadb
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.embeddings.embedding_model import EmbeddingModel

# 1. 加载当前 Embedding 模型
embedding_model = EmbeddingModel()

print("========== 当前模型结构 ==========")
print(embedding_model.model)

# 2. 加载已经保存的 Chroma 数据库
client = chromadb.PersistentClient(
    path=str(BASE_DIR / "data" / "chroma_db")
)

collection = client.get_collection(
    name="nuist_charter_v1",
    embedding_function=None
)

# 3. 取出建库时保存的 Chunk 30 向量及文本
result = collection.get(
    ids=["chunk_30"],
    include=["embeddings", "documents"]
)

saved_vector = np.asarray(result["embeddings"][0])
saved_text = result["documents"][0]

# 4. 使用当前模型重新编码同一段文本
new_vector = embedding_model.embed_query(saved_text)

# 5. 比较新旧向量
cosine = np.dot(saved_vector, new_vector) / (
    np.linalg.norm(saved_vector)
    * np.linalg.norm(new_vector)
)

print("\n========== 向量一致性检查 ==========")
print("数据库向量维度：", saved_vector.shape)
print("当前模型向量维度：", new_vector.shape)
print("新旧向量相似度：", f"{cosine:.6f}")
print("最大元素差异：", np.max(np.abs(saved_vector - new_vector)))


# ==================================================
# 6. 对 Query 进行向量化
# ==================================================
query = "南京信息工程大学学术委员会有哪些职责？"

query_vector = embedding_model.embed_query(query)

# 使用 NumPy 手动计算与 Chunk 30 的余弦相似度
manual_similarity = np.dot(saved_vector, query_vector) / (
    np.linalg.norm(saved_vector)
    * np.linalg.norm(query_vector)
)

manual_distance = 1 - manual_similarity

print("\n========== NumPy 手动计算 ==========")
print(f"Chunk 30 相似度：{manual_similarity:.6f}")
print(f"Chunk 30 余弦距离：{manual_distance:.6f}")


# ==================================================
# 7. 使用 Chroma 查询同一个 Query
# ==================================================
results = collection.query(
    query_embeddings=[query_vector.tolist()],
    n_results=3
)

print("\n========== Chroma 检索 ==========")

for rank, (chunk_id, distance) in enumerate(
    zip(results["ids"][0], results["distances"][0]),
    start=1
):
    print(
        f"Top {rank} | "
        f"{chunk_id} | "
        f"距离：{distance:.6f}"
    )


# ==================================================
# 8. 查看 Collection 的距离配置
# ==================================================
print("\n========== Collection 配置 ==========")
print("Metadata：", collection.metadata)
print("Configuration：", collection.configuration)
