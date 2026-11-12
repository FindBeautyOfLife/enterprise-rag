
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.embeddings.embedding_model import EmbeddingModel

embedding_model = EmbeddingModel()

texts = [
    "学术委员会负责学术事务。",
    "学校党委负责学校重大决策。"
]

document_vectors = embedding_model.embed_documents(texts)
query_vector = embedding_model.embed_query("学术委员会有哪些职责？")

print("文档向量形状：", document_vectors.shape)
print("查询向量形状：", query_vector.shape)

print("相似度结果：", document_vectors @ query_vector)
