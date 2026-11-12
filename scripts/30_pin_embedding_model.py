
from pathlib import Path
import sys

import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer, models

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
LOCAL_PATH = BASE_DIR / "data" / "models" / "bge-small-zh-v1.5"

# 1. 加载已有模型文件
model = SentenceTransformer(
    MODEL_NAME,
    device="cpu"
)

pooling = model[1]

# 2. 如果加载成 Mean Pooling，显式重建正确架构
if not pooling.pooling_mode_cls_token or pooling.pooling_mode_mean_tokens:
    print("检测到错误的 Pooling，正在构建 CLS Pooling...")

    transformer = model[0]

    model = SentenceTransformer(
        modules=[
            transformer,
            models.Pooling(
                transformer.get_word_embedding_dimension(),
                pooling_mode="cls"
            ),
            models.Normalize()
        ],
        device="cpu"
    )

print("\n当前模型结构：")
print(model)

# 3. 从旧数据库获取真实参考向量
client = chromadb.PersistentClient(
    path=str(BASE_DIR / "data" / "chroma_db")
)

collection = client.get_collection(
    name="nuist_charter_v1",
    embedding_function=None
)

record = collection.get(
    ids=["chunk_30"],
    include=["documents", "embeddings"]
)

saved_vector = np.asarray(record["embeddings"][0])
saved_text = record["documents"][0]

# 4. 使用修复后的模型重新计算
new_vector = model.encode(
    saved_text,
    normalize_embeddings=True
)

similarity = float(
    np.dot(saved_vector, new_vector)
    / (
        np.linalg.norm(saved_vector)
        * np.linalg.norm(new_vector)
    )
)

max_diff = float(np.max(np.abs(saved_vector - new_vector)))

print("\n向量一致性检查：")
print("余弦相似度：", f"{similarity:.8f}")
print("最大元素差异：", f"{max_diff:.8f}")

# 5. 不符合预期时禁止保存
if similarity < 0.99999 or max_diff > 1e-4:
    raise RuntimeError(
        "修复后模型与原数据库向量不一致，"
        "请检查模型权重和本地缓存。"
    )

# 6. 保存可复现的本地模型
LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)

model.save_pretrained(str(LOCAL_PATH))

print("\n本地模型保存成功：")
print(LOCAL_PATH)
