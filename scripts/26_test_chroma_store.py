
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.embeddings.embedding_model import EmbeddingModel
from src.vectorstores.chroma_store import ChromaStore


# 1. 初始化 Embedding 模型
embedding_model = EmbeddingModel()

# 2. 连接已有数据库
store = ChromaStore(
    persist_directory=BASE_DIR / "data" / "chroma_db",
    collection_name="nuist_charter_v1",
    embedding_model=embedding_model
)

print("Chroma 记录数：", store.count())

# 3. 执行检索
query = "南京信息工程大学学术委员会有哪些职责？"

results = store.search(query, top_k=3)

print("\n========== ChromaStore Top-3 ==========")

for rank, result in enumerate(results, start=1):
    chunk = result["document"]

    print(
        f"Top {rank} | "
        f"Chunk ID：{result['chunk_id']} | "
        f"{chunk.metadata['article']} | "
        f"相似度：{result['score']:.4f}"
    )
