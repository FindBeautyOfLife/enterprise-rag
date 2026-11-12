
from typing import TypedDict
from typing_extensions import NotRequired


class AgentState(TypedDict):
    question: str
    retrieval_query: NotRequired[str]
    rerank_query: NotRequired[str]
    retrieved_results: NotRequired[list]
    answer: NotRequired[str]
    sources: NotRequired[list]
    citation_valid: NotRequired[bool]
    cited_sources: NotRequired[list]
    route: NotRequired[str]
    evidence_sufficient: NotRequired[bool]
    retry_count: NotRequired[int]