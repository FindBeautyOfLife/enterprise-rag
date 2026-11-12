
from pathlib import Path
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader
from src.retrievers.bm25_retriever import BM25Retriever


# 1. 加载文档
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

documents = DocxLoader(file_path).load()

# 2. 文本切分
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

chunks = splitter.split_documents(documents)

# 3. 创建 BM25Retriever
retriever = BM25Retriever()

# 4. 构建索引
retriever.index(chunks)

print("索引 Chunk 数量：", len(retriever.chunks))

# 5. 执行检索
query = "南京信息工程大学学术委员会有哪些职责？"

print("Query 分词：", retriever.tokenize(query))

results = retriever.search(query, top_k=3)

print("\n========== BM25Retriever Top-3 ==========")

for rank, result in enumerate(results, start=1):
    chunk = result["document"]

    print(
        f"Top {rank} | "
        f"Chunk ID：{result['chunk_id']} | "
        f"{chunk.metadata['article']} | "
        f"BM25分数：{result['score']:.4f}"
    )
