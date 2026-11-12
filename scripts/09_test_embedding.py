
from sentence_transformers import SentenceTransformer

# 1. 加载中文 Embedding 模型
model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5",
    device="cpu"
)

# 2. 准备测试文本
sentences = [
    "南京信息工程大学学术委员会有哪些职责？",
    "学术委员会负责审议学科建设和专业设置。",
    "学校的校庆日是哪一天？"
]

# 3. 将文本转换为向量
embeddings = model.encode(
    sentences,
    normalize_embeddings=True
)

# 4. 输出结果
print("向量类型：", type(embeddings))
print("向量矩阵形状：", embeddings.shape)
print("第一句话的前10个向量值：")
print(embeddings[0][:10])


import numpy as np

# 获取三个文本向量
v1 = embeddings[0]
v2 = embeddings[1]
v3 = embeddings[2]

# 手动实现余弦相似度
def cosine_similarity(a, b):
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    return dot_product / (norm_a * norm_b)


sim_12 = cosine_similarity(v1, v2)
sim_13 = cosine_similarity(v1, v3)

print("\n余弦相似度计算结果：")
print(f"问题1 与 文本2：{sim_12:.4f}")
print(f"问题1 与 文本3：{sim_13:.4f}")


# 查询向量
query_vector = embeddings[0]

# 两个候选文档向量
document_vectors = embeddings[1:]

# 批量计算相似度
scores = document_vectors @ query_vector

# 按相似度降序排列
ranked_indices = np.argsort(scores)[::-1]

print("\n检索结果排序：")

for rank, idx in enumerate(ranked_indices, start=1):
    print(
        f"Top {rank} | "
        f"相似度：{scores[idx]:.4f} | "
        f"文本：{sentences[idx + 1]}"
    )
