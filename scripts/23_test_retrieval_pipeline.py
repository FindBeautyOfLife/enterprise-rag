
from pathlib import Path
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader
from src.embeddings.embedding_model import EmbeddingModel
from src.retrievers.dense_retriever import DenseRetriever
from src.retrievers.bm25_retriever import BM25Retriever
from src.retrievers.hybrid_retriever import HybridRetriever
from src.retrievers.parent_retriever import ParentRetriever
from src.retrievers.reranker import Reranker
from src.retrievers.retrieval_pipeline import RetrievalPipeline


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
# 2. 初始化基础检索器
# ==================================================
embedding_model = EmbeddingModel()

dense = DenseRetriever(embedding_model)
bm25 = BM25Retriever()

dense.index(chunks)
bm25.index(chunks)


# ==================================================
# 3. 初始化高级检索模块
# ==================================================
hybrid = HybridRetriever(dense, bm25)

parent_retriever = ParentRetriever(
    child_retriever=hybrid,
    parent_documents=documents
)

reranker = Reranker()


# ==================================================
# 4. 组装 RetrievalPipeline
# ==================================================
pipeline = RetrievalPipeline(
    parent_retriever=parent_retriever,
    reranker=reranker
)


# ==================================================
# 5. 执行检索
# ==================================================
query = "南京信息工程大学学术委员会有哪些职责？"

results = pipeline.search(
    query=query,
    rerank_query="学术委员会有哪些职责？",
    top_k=3,
    child_top_k=10,
    candidate_k=len(chunks)
)


# ==================================================
# 6. 输出最终结果
# ==================================================
print("\n========== RetrievalPipeline Top-3 ==========")

for rank, item in enumerate(results, start=1):
    doc = item["document"]

    print(f"\nTop {rank}")
    print("条款：", doc.metadata["article"])
    print("章节：", doc.metadata["chapter"])
    print("RRF 分数：", f"{item['score']:.6f}")
    print("Rerank 分数：", f"{item['rerank_score']:.4f}")
    print("完整内容：")
    print(doc.page_content)
