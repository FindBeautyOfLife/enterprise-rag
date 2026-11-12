
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


# 1. 加载父 Document
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

documents = DocxLoader(file_path).load()

# 2. 创建子 Chunk
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

chunks = splitter.split_documents(documents)

# 3. 初始化 Dense 和 BM25
embedding_model = EmbeddingModel()

dense = DenseRetriever(embedding_model)
bm25 = BM25Retriever()

dense.index(chunks)
bm25.index(chunks)

# 4. 创建 HybridRetriever
hybrid = HybridRetriever(dense, bm25)

# 5. 创建 ParentRetriever
parent_retriever = ParentRetriever(
    child_retriever=hybrid,
    parent_documents=documents
)

# 6. 执行父文档检索
query = "南京信息工程大学学术委员会有哪些职责？"

results = parent_retriever.search(
    query,
    top_k=10,
    child_top_k=10,
    candidate_k=len(chunks)
)


from src.retrievers.reranker import Reranker

# 1. 获取候选父文档
parent_results = parent_retriever.search(
    query,
    top_k=10,
    child_top_k=10,
    candidate_k=len(chunks)
)

print("候选父文档数量：", len(parent_results))

# 2. 初始化 Reranker
reranker = Reranker()

# 3. 测试两种 Query
queries = [
    "南京信息工程大学学术委员会有哪些职责？",
    "学术委员会有哪些职责？"
]

for rerank_query in queries:

    results = reranker.rerank(
        query=rerank_query,
        documents=parent_results,
        top_k=5
    )

    print(f"\n========== Rerank Query：{rerank_query} ==========")

    for rank, item in enumerate(results, start=1):
        parent = item["document"]

        print(
            f"Top {rank} | "
            f"{parent.metadata['article']} | "
            f"Rerank分数：{item['rerank_score']:.4f}"
        )

