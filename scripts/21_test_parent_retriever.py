
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

print("父文档索引数量：", len(parent_retriever.parent_store))
print("恢复的父文档数量：", len(results))

print("\n========== ParentRetriever 结果 ==========")

for rank, item in enumerate(results, start=1):
    parent_doc = item["document"]

    print(
        f"Parent {rank} | "
        f"命中 Chunk ID：{item['chunk_id']} | "
        f"{parent_doc.metadata['article']} | "
        f"RRF分数：{item['score']:.6f}"
    )

    if parent_doc.metadata["article"] == "第三十七条":
        print("\n第三十七条完整内容：")
        print(parent_doc.page_content)
