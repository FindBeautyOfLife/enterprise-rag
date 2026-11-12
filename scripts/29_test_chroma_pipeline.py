
from pathlib import Path
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader
from src.embeddings.embedding_model import EmbeddingModel
from src.vectorstores.id_utils import prepare_chunks
from src.vectorstores.chroma_store import ChromaStore

from src.retrievers.bm25_retriever import BM25Retriever
from src.retrievers.hybrid_retriever import HybridRetriever
from src.retrievers.parent_retriever import ParentRetriever
from src.retrievers.reranker import Reranker
from src.retrievers.retrieval_pipeline import RetrievalPipeline


# ==================================================
# 1. 加载文档及切分
# ==================================================
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

parents = DocxLoader(file_path).load()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

chunks = splitter.split_documents(parents)

# 为全部 Chunk 分配统一 ID
chunks = prepare_chunks(
    chunks,
    document_key="nuist_charter_2023"
)

document_id = chunks[0].metadata["document_id"]

print("父文档数量：", len(parents))
print("子 Chunk 数量：", len(chunks))
print("Document ID：", document_id)


# ==================================================
# 2. 初始化并同步 Chroma
# ==================================================
embedding_model = EmbeddingModel()

chroma = ChromaStore(
    persist_directory=BASE_DIR / "data" / "chroma_db",
    collection_name="nuist_charter_v2",
    embedding_model=embedding_model
)

sync_result = chroma.sync_document(
    document_id=document_id,
    chunks=chunks
)

print("\n========== Chroma 同步结果 ==========")
print(sync_result)
print("数据库记录数：", chroma.count())


# ==================================================
# 3. 初始化 BM25 + Hybrid
# ==================================================
bm25 = BM25Retriever()
bm25.index(chunks)

# ChromaStore 提供与 DenseRetriever 兼容的 search()
hybrid = HybridRetriever(
    dense_retriever=chroma,
    bm25_retriever=bm25
)


# ==================================================
# 4. 恢复父文档并进行重排序
# ==================================================
parent_retriever = ParentRetriever(
    child_retriever=hybrid,
    parent_documents=parents
)

reranker = Reranker()

pipeline = RetrievalPipeline(
    parent_retriever=parent_retriever,
    reranker=reranker
)



# ==================================================
# LangGraph RAG Agent 集成测试
# ==================================================
from src.generation.llm_client import LLMClient
from src.generation.rag_generator import RAGGenerator
from src.agent.workflow import EnterpriseRAGAgent

llm_client = LLMClient()
generator = RAGGenerator(llm_client)

agent = EnterpriseRAGAgent(
    retrieval_pipeline=pipeline,
    generator=generator,
    llm_client=llm_client
)


questions = [
    "南京信息工程大学学术委员会有哪些职责？",
    "南京信息工程大学章程规定的食堂午餐价格是多少？"
]

for question in questions:
    print("\n" + "=" * 60)
    print("问题：", question)

    result = agent.invoke(question)

    print("答案：", result["answer"])
    print("检索重试次数：", result["retry_count"])
    print("证据是否充分：", result["evidence_sufficient"])
    print("引用编号有效：", result.get("citation_valid"))

    for source in result.get("cited_sources", []):
        print(f"[{source['number']}] {source['article']}")
