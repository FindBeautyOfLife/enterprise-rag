import re

from langgraph.graph import StateGraph, START, END

from src.agent.state import AgentState


class EnterpriseRAGAgent:

    MAX_RETRIES = 1

    def __init__(self, retrieval_pipeline, generator, llm_client):
        self.pipeline = retrieval_pipeline
        self.generator = generator
        self.llm = llm_client
        self.graph = self._build_graph()

    # 1. 查询改写
    def rewrite_node(self, state: AgentState):
        question = state["question"].strip()

        prompt = """
你是知识库查询优化器。
把用户问题改写成适合语义检索的简洁问句。
保留核心对象、限定条件和问题意图。
不要回答问题，只输出改写后的查询。
"""

        try:
            rewritten = self.llm.chat(prompt, question).strip().strip('"“”')

            if not rewritten or len(rewritten) > 100:
                rewritten = question
        except Exception:
            rewritten = question

        print("[Rewrite] 查询改写完成")

        return {
            "retrieval_query": question,
            "rerank_query": rewritten,
            "retry_count": 0,
        }

    # 2. 检索
    def retrieve_node(self, state: AgentState):
        results = self.pipeline.search(
            query=state["retrieval_query"],
            rerank_query=state["rerank_query"],
            top_k=3,
            child_top_k=10,
            candidate_k=72,
        )

        print(f"[Retrieve] 找到 {len(results)} 个父文档")

        return {"retrieved_results": results}

    # 3. 评估证据是否足够
    def evaluate_node(self, state: AgentState):
        results = state["retrieved_results"]

        if not results:
            return {"evidence_sufficient": False}

        context = "\n\n".join(
            f"[{i}] {item['document'].page_content}"
            for i, item in enumerate(results, start=1)
        )

        prompt = """
你是知识库证据评估器。

请判断提供的文档是否包含足够信息，
能够直接回答用户问题。

注意：
- 仅判断证据是否充分，不要回答问题。
- 不要因为某条证据排名靠后就判定不充分。
- 不能仅因为主题相近就判定充分。
- 只输出 YES 或 NO。
"""

        try:
            decision = (
                self.llm.chat(prompt, f"问题：{state['question']}\n\n证据：\n{context}")
                .strip()
                .upper()
            )

            sufficient = decision == "YES"

        except Exception:
            print("[Evaluate] 评估失败，请检查大模型服务配置")
            sufficient = False

        print(f"[Evaluate] 证据充分：{sufficient}")

        return {"evidence_sufficient": sufficient}

    # 4. 条件路由
    def route_after_evaluate(self, state: AgentState):
        if state["evidence_sufficient"]:
            return "generate"

        if state.get("retry_count", 0) < self.MAX_RETRIES:
            return "retry"

        return "fallback"

    # 5. 重新构造查询
    def retry_node(self, state: AgentState):
        question = state["question"]

        prompt = """
你是知识检索优化器。
上一次检索未找到足够证据。

请从原始问题中提取核心对象和查询意图，
构造一个更简洁的检索问句。

必须保留会影响答案范围的限定条件。
不能编造事实，不要回答问题。
只输出查询。
"""

        try:
            new_query = self.llm.chat(prompt, question).strip().strip('"“”')

            if not new_query or len(new_query) > 100:
                new_query = question
        except Exception:
            new_query = question

        print("[Retry] 查询重试准备完成")

        return {
            "rerank_query": new_query,
            "retry_count": state.get("retry_count", 0) + 1,
        }

    # 6. 生成答案
    def generate_node(self, state: AgentState):
        result = self.generator.generate(
            question=state["question"], retrieved_results=state["retrieved_results"]
        )

        print("[Generate] 答案生成完成")

        return {"answer": result["answer"], "sources": result["sources"]}

    # 7. 引用检查
    def verify_node(self, state: AgentState):
        answer = state["answer"]
        sources = state.get("sources", [])

        valid_numbers = {item["number"] for item in sources}

        cited_numbers = {int(number) for number in re.findall(r"\[(\d+)\]", answer)}

        valid = bool(cited_numbers) and cited_numbers.issubset(valid_numbers)

        cited_sources = [
            source for source in sources if source["number"] in cited_numbers
        ]

        print(f"[Verify] 引用编号有效：{valid}")

        return {"citation_valid": valid, "cited_sources": cited_sources}

    # 8. 证据不足时回退
    def fallback_node(self, state: AgentState):
        return {
            "answer": "当前知识库资料不足，无法可靠回答该问题。",
            "sources": [],
            "cited_sources": [],
            "citation_valid": False,
        }

    # 9. 构建 LangGraph
    def _build_graph(self):
        builder = StateGraph(AgentState)

        builder.add_node("rewrite", self.rewrite_node)
        builder.add_node("retrieve", self.retrieve_node)
        builder.add_node("evaluate", self.evaluate_node)
        builder.add_node("retry", self.retry_node)
        builder.add_node("generate", self.generate_node)
        builder.add_node("verify", self.verify_node)
        builder.add_node("fallback", self.fallback_node)

        builder.add_edge(START, "rewrite")
        builder.add_edge("rewrite", "retrieve")
        builder.add_edge("retrieve", "evaluate")

        builder.add_conditional_edges(
            "evaluate",
            self.route_after_evaluate,
            {"generate": "generate", "retry": "retry", "fallback": "fallback"},
        )

        builder.add_edge("retry", "retrieve")
        builder.add_edge("generate", "verify")
        builder.add_edge("verify", END)
        builder.add_edge("fallback", END)

        return builder.compile()

    def invoke(self, question):
        if not question.strip():
            raise ValueError("问题不能为空")

        return self.graph.invoke({"question": question})
