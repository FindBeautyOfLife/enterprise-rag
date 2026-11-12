
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


# 1. 加载文档
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

documents = DocxLoader(file_path).load()

# 2. 切分 Chunk
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

chunks = splitter.split_documents(documents)

# 3. 创建并初始化两个检索器
embedding_model = EmbeddingModel()

dense = DenseRetriever(embedding_model)
bm25 = BM25Retriever()

dense.index(chunks)
bm25.index(chunks)

# 4. 创建 HybridRetriever
hybrid = HybridRetriever(dense, bm25)

# 5. 执行检索
query = "南京信息工程大学学术委员会有哪些职责？"

results = hybrid.search(
    query,
    top_k=10,
    candidate_k=len(chunks)
)

print("\n========== HybridRetriever Top-10 ==========")

for rank, result in enumerate(results, start=1):
    chunk = result["document"]

    print(
        f"Top {rank} | "
        f"Chunk ID：{result['chunk_id']} | "
        f"{chunk.metadata['article']} | "
        f"RRF分数：{result['score']:.6f}"
    )
