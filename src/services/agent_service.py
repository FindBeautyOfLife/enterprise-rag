"""将所选知识库的检索流水线接入现有 LangGraph 问答流程。"""
from src.agent.workflow import EnterpriseRAGAgent
from src.generation.llm_client import LLMClient
from src.generation.rag_generator import RAGGenerator


class AgentService:
    def __init__(self, retrieval_pipeline):
        llm = LLMClient()
        self.agent = EnterpriseRAGAgent(retrieval_pipeline, RAGGenerator(llm), llm)

    def ask(self, question):
        result = self.agent.invoke(question)
        return {
            "question": result["question"], "answer": result["answer"],
            "retrieval_query": result.get("retrieval_query"),
            "rerank_query": result.get("rerank_query"),
            "retry_count": result.get("retry_count", 0),
            "evidence_sufficient": result.get("evidence_sufficient", False),
            "citation_valid": result.get("citation_valid", False),
            "sources": result.get("cited_sources", []),
        }
