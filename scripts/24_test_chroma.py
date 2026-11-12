
from pathlib import Path
import sys

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader
from src.embeddings.embedding_model import EmbeddingModel


# 1. 创建持久化 Chroma 客户端
db_path = BASE_DIR / "data" / "chroma_db"

client = chromadb.PersistentClient(
    path=str(db_path)
)

collection = client.get_or_create_collection(
    name="nuist_charter_v1",
    embedding_function=None,
    configuration={"hnsw": {"space": "cosine"}}
)

print("当前数据库记录数：", collection.count())


# 2. 首次运行时建立索引
if collection.count() == 0:

    file_path = (
        BASE_DIR / "data" / "documents"
        / "南京信息工程大学章程.docx"
    )

    documents = DocxLoader(file_path).load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "；", "，", ""]
    )

    chunks = splitter.split_documents(documents)

    embedding_model = EmbeddingModel()

    vectors = embedding_model.embed_documents(
        [chunk.page_content for chunk in chunks]
    )

    collection.add(
        ids=[f"chunk_{i}" for i in range(len(chunks))],
        embeddings=vectors.tolist(),
        documents=[chunk.page_content for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks]
    )

    print("首次建立索引完成")


# 3. 检查持久化结果
print("Chroma 记录数：", collection.count())


# 4. 使用同一个 Embedding 模型查询
embedding_model = EmbeddingModel()

query = "南京信息工程大学学术委员会有哪些职责？"
query_vector = embedding_model.embed_query(query)

results = collection.query(
    query_embeddings=[query_vector.tolist()],
    n_results=3
)

print("\n========== Chroma Top-3 ==========")

for i in range(len(results["ids"][0])):
    print(
        f"Top {i + 1} | "
        f"ID：{results['ids'][0][i]} | "
        f"条款：{results['metadatas'][0][i]['article']} | "
        f"距离：{results['distances'][0][i]:.4f}"
    )
