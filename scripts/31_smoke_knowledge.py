"""手动运行的本地 BGE 与 Chroma 冒烟检查，使用临时数据，不修改现有索引。
在项目根目录运行：python scripts/31_smoke_knowledge.py
"""
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from src.config import Settings
from src.services.knowledge_service import KnowledgeService


def main():
    config = Settings.from_env()
    # Windows 下 Chroma 会持有原生文件句柄，临时索引留给系统后续清理，
    # 避免在数据库连接仍存活时尝试删除文件。
    scratch = Path(tempfile.mkdtemp(prefix="enterprise-rag-smoke-"))
    settings = Settings(scratch, config.embedding_model, config.reranker_model, config.device, config.max_upload_bytes)
    service = KnowledgeService(settings)
    kb = service.save_base("本地模型验证", "临时测试数据")['id']
    result = service.upload(kb, "制度.txt", "第一条 报销需要财务审批。\n第二条 合同需要法务审核。".encode())
    indexed = service.rebuild(kb)
    assert indexed['chunks'] == result['chunk_count']
    store = service.stores[service.list_bases()[0]['collection']]
    hits = store.search("报销由谁审批", top_k=2)
    assert hits and "财务" in hits[0]['document'].page_content
    if "--hybrid" in sys.argv:
        hybrid = service.search(kb, "报销由谁审批", mode="hybrid", top_k=1)
        assert "财务" in hybrid['items'][0]['content']
        assert hybrid['items'][0]['rerank_score'] is not None
        print("PASS: real Dense + BM25 + RRF + Parent + CrossEncoder")
    # 创建新的服务实例，复用模型并重新连接 SQLite 和 Chroma，验证持久化数据。
    restarted = KnowledgeService(settings)
    restarted.embedding = service.embedding
    saved = restarted.list_bases()[0]
    assert restarted._store(saved['collection']).count() == indexed['chunks']
    service.delete_base(kb)
    assert service.list_bases() == []
    print(f"PASS: real BGE/Chroma index, retrieval, reopen and deletion; scratch={scratch}")


if __name__ == '__main__':
    main()
