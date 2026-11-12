"""知识库管理服务：以 SQLite 保存的资料为准，Chroma 保存可重建的版本化向量索引。

部署时使用一个 API 工作进程。通过进程内锁串行处理资料修改、索引构建和问答，
避免同一次检索混用新版本的 BM25 语料和旧版本的向量集合。
"""

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone

from langchain_core.documents import Document

from src.loaders.knowledge_loader import parse_upload

logger = logging.getLogger(__name__)


class KnowledgeError(Exception):
    """携带 HTTP 状态码的业务异常，由接口层统一转换为错误响应。"""

    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def now():
    """生成带时区的 UTC 时间，供前端转换为本地时间显示。"""
    return datetime.now(timezone.utc).isoformat()


def pack(documents):
    """将文档正文和元数据序列化为 JSON，供 SQLite 持久化保存。"""
    return json.dumps(
        [{"page_content": d.page_content, "metadata": d.metadata} for d in documents],
        ensure_ascii=False,
    )


def unpack(value):
    """将数据库中的 JSON 还原为 LangChain 文档对象。"""
    return [Document(**item) for item in json.loads(value)]


class KnowledgeService:
    """统一管理知识库、原文件、解析结果及检索索引。"""

    def __init__(self, settings, store_factory=None):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = settings.data_dir / "knowledge.sqlite3"
        self.lock = threading.RLock()
        # 模型按需加载，管理资料时无需提前加载模型权重。
        self.embedding = None
        self.reranker = None
        self.store_factory = store_factory
        self.stores = {}
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL, created_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    indexed_revision INTEGER NOT NULL DEFAULT -1,
                    collection TEXT, index_error TEXT
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, kb_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL, content_hash TEXT NOT NULL,
                    size INTEGER NOT NULL, created_at TEXT NOT NULL,
                    parents TEXT NOT NULL, chunks TEXT NOT NULL, raw BLOB NOT NULL,
                    UNIQUE(kb_id, content_hash)
                );
            """)

    @contextmanager
    def db(self):
        """提供数据库事务，正常退出时提交、异常时回滚，并保证连接关闭。"""
        with closing(sqlite3.connect(self.db_path, timeout=30)) as connection:
            with connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                yield connection

    def _kb(self, db, kb_id):
        """查询知识库；不存在时返回明确的业务错误。"""
        row = db.execute(
            "SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)
        ).fetchone()
        if row is None:
            raise KnowledgeError(404, "知识库不存在")
        return dict(row)

    def list_bases(self):
        """列出知识库，汇总文档数、子片段数和索引是否匹配当前资料版本。"""
        with self.lock, self.db() as db:
            result = []
            for row in db.execute("SELECT * FROM knowledge_bases ORDER BY created_at"):
                item = dict(row)
                docs = db.execute(
                    "SELECT chunks FROM documents WHERE kb_id=?", (item["id"],)
                ).fetchall()
                item.update(
                    document_count=len(docs),
                    chunk_count=sum(len(json.loads(d[0])) for d in docs),
                )
                item["index_status"] = (
                    "ready"
                    if item["revision"] == item["indexed_revision"]
                    else "pending"
                )
                result.append(item)
            return result

    def save_base(self, name, description, kb_id=None):
        """创建或编辑知识库基本信息，数据库唯一约束用于防止名称重复。"""
        with self.lock, self.db() as db:
            try:
                if kb_id:
                    self._kb(db, kb_id)
                    db.execute(
                        "UPDATE knowledge_bases SET name=?, description=? WHERE id=?",
                        (name, description, kb_id),
                    )
                else:
                    kb_id = uuid.uuid4().hex
                    db.execute(
                        "INSERT INTO knowledge_bases(id,name,description,created_at) VALUES(?,?,?,?)",
                        (kb_id, name, description, now()),
                    )
            except sqlite3.IntegrityError as exc:
                raise KnowledgeError(409, "知识库名称已存在") from exc
            return self._kb(db, kb_id)

    def delete_base(self, kb_id):
        """级联删除知识库及其文档，再尝试清理对应的向量集合。"""
        with self.lock:
            with self.db() as db:
                kb = self._kb(db, kb_id)
                db.execute("DELETE FROM knowledge_bases WHERE id=?", (kb_id,))
            self._cleanup_collection(kb["collection"])

    def documents(self, kb_id):
        """返回指定知识库的文档列表与分块统计，不返回原文件正文。"""
        with self.lock, self.db() as db:
            self._kb(db, kb_id)
            rows = db.execute(
                "SELECT id,filename,size,created_at,parents,chunks FROM documents WHERE kb_id=? ORDER BY created_at",
                (kb_id,),
            )
            return [
                dict(
                    id=r["id"],
                    filename=r["filename"],
                    size=r["size"],
                    created_at=r["created_at"],
                    parent_count=len(json.loads(r["parents"])),
                    chunk_count=len(json.loads(r["chunks"])),
                )
                for r in rows
            ]

    def _document(self, db, kb_id, document_id):
        """同时按知识库和文档 ID 查询，避免访问其他知识库的文档。"""
        self._kb(db, kb_id)
        row = db.execute(
            "SELECT * FROM documents WHERE kb_id=? AND id=?", (kb_id, document_id)
        ).fetchone()
        if row is None:
            raise KnowledgeError(404, "文档不存在")
        return row

    def preview(self, kb_id, document_id, offset=0, limit=20):
        """分页返回子片段正文与元数据，便于检查解析和切分效果。"""
        with self.lock, self.db() as db:
            row = self._document(db, kb_id, document_id)
            chunks = json.loads(row["chunks"])
            return {
                "filename": row["filename"],
                "total": len(chunks),
                "offset": offset,
                "items": chunks[offset : offset + limit],
            }

    def download(self, kb_id, document_id):
        """读取上传时保存的原始文件名和字节内容。"""
        with self.lock, self.db() as db:
            row = self._document(db, kb_id, document_id)
            return row["filename"], row["raw"]

    def upload(self, kb_id, filename, content, document_id=None):
        """解析并保存新文档；传入文档 ID 时替换原文件并保留文档身份。"""
        if len(content) > self.settings.max_upload_bytes:
            raise KnowledgeError(413, "文件超过上传大小限制")
        with self.lock, self.db() as db:
            self._kb(db, kb_id)
            if document_id:
                self._document(db, kb_id, document_id)
            doc_id = document_id or uuid.uuid4().hex
            try:
                filename, digest, parents, chunks = parse_upload(
                    filename, content, f"{kb_id}:{doc_id}"
                )
            except ValueError as exc:
                raise KnowledgeError(422, str(exc)) from exc
            try:
                if document_id:
                    db.execute(
                        """UPDATE documents SET filename=?,content_hash=?,size=?,created_at=?,parents=?,chunks=?,raw=?
                                  WHERE id=? AND kb_id=?""",
                        (
                            filename,
                            digest,
                            len(content),
                            now(),
                            pack(parents),
                            pack(chunks),
                            content,
                            doc_id,
                            kb_id,
                        ),
                    )
                else:
                    db.execute(
                        "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?)",
                        (
                            doc_id,
                            kb_id,
                            filename,
                            digest,
                            len(content),
                            now(),
                            pack(parents),
                            pack(chunks),
                            content,
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise KnowledgeError(409, "知识库内已存在相同内容的文档") from exc
            # 文档内容变化后递增资料版本，混合检索前需要重建对应索引。
            db.execute(
                "UPDATE knowledge_bases SET revision=revision+1,index_error=NULL WHERE id=?",
                (kb_id,),
            )
            return {
                "id": doc_id,
                "filename": filename,
                "parent_count": len(parents),
                "chunk_count": len(chunks),
            }

    def delete_document(self, kb_id, document_id):
        """删除文档并递增资料版本，使旧向量索引进入待重建状态。"""
        with self.lock, self.db() as db:
            self._document(db, kb_id, document_id)
            db.execute(
                "DELETE FROM documents WHERE id=? AND kb_id=?", (document_id, kb_id)
            )
            db.execute(
                "UPDATE knowledge_bases SET revision=revision+1,index_error=NULL WHERE id=?",
                (kb_id,),
            )

    def _corpus(self, db, kb_id):
        """从 SQLite 读取指定知识库当前保存的全部父段和子片段。"""
        parents, chunks = [], []
        for row in db.execute(
            "SELECT parents,chunks FROM documents WHERE kb_id=? ORDER BY id", (kb_id,)
        ):
            parents.extend(unpack(row[0]))
            chunks.extend(unpack(row[1]))
        return parents, chunks

    def _store(self, name):
        """按集合名称复用向量库连接，首次使用时加载嵌入模型。"""
        if name not in self.stores:
            if self.store_factory:
                self.stores[name] = self.store_factory(name)
            else:
                from src.embeddings.embedding_model import EmbeddingModel
                from src.vectorstores.chroma_store import ChromaStore

                if self.embedding is None:
                    self.embedding = EmbeddingModel(
                        self.settings.embedding_model, self.settings.device
                    )
                self.stores[name] = ChromaStore(
                    self.settings.data_dir / "chroma", name, self.embedding
                )
        return self.stores[name]

    def _cleanup_collection(self, name):
        """尽力清理派生索引，清理失败仅记录日志，不撤销已提交的数据操作。"""
        if not name:
            return
        try:
            store = self.stores.pop(name, None)
            if store is not None:
                store.client.delete_collection(name=name)
            elif (self.settings.data_dir / "chroma").exists():
                import chromadb

                chromadb.PersistentClient(
                    path=str(self.settings.data_dir / "chroma")
                ).delete_collection(name=name)
        except Exception:
            # 资料数据库已提交成功，即使残留索引未清理，也不应将成功操作报告为失败。
            logger.warning("未能清理旧索引 %s", name, exc_info=True)

    def rebuild(self, kb_id):
        """构建新版本集合，校验通过后切换生效指针，失败则保留原有索引。"""
        with self.lock:
            with self.db() as db:
                kb = self._kb(db, kb_id)
                _, chunks = self._corpus(db, kb_id)
            name = f"kb_{kb_id}_{uuid.uuid4().hex}"
            try:
                if chunks:
                    store = self._store(name)
                    grouped = {}
                    for chunk in chunks:
                        grouped.setdefault(chunk.metadata["document_id"], []).append(
                            chunk
                        )
                    for document_id, group in grouped.items():
                        store.sync_document(document_id, group)
                    if store.count() != len(chunks):
                        raise RuntimeError("索引写入数量校验失败")
                # 新集合全部写入且数量校验通过后，才在事务中切换生效版本。
                with self.db() as db:
                    db.execute(
                        "UPDATE knowledge_bases SET collection=?,indexed_revision=?,index_error=NULL WHERE id=?",
                        (name if chunks else None, kb["revision"], kb_id),
                    )
            except Exception as exc:
                # 只清理本次构建的新集合，旧集合及其版本指针保持不变。
                self._cleanup_collection(name)
                with self.db() as db:
                    db.execute(
                        "UPDATE knowledge_bases SET index_error=? WHERE id=?",
                        ("索引构建失败，请检查模型路径、依赖和服务日志", kb_id),
                    )
                logger.exception("知识库索引构建失败")
                raise KnowledgeError(
                    503, "索引构建失败，请检查模型路径、依赖和服务日志后重试"
                ) from exc
            self._cleanup_collection(kb["collection"])
            return {
                "indexed_revision": kb["revision"],
                "chunks": len(chunks),
                "status": "ready",
            }

    def _pipeline(self, db, kb_id, mode):
        """按当前知识库组装关键词检索或包含重排序的混合检索流水线。"""
        from src.retrievers.bm25_retriever import BM25Retriever
        from src.retrievers.parent_retriever import ParentRetriever

        kb = self._kb(db, kb_id)
        parents, chunks = self._corpus(db, kb_id)
        if not chunks:
            raise KnowledgeError(409, "知识库为空，请先上传文档")
        bm25 = BM25Retriever()
        bm25.index(chunks)
        if mode == "keyword":
            # 关键词模式直接使用当前资料，无需向量索引或重排序模型。
            class KeywordAdapter:
                def search(self, query, top_k=10, candidate_k=None):
                    return bm25.search(query, top_k=candidate_k or top_k)

            return ParentRetriever(KeywordAdapter(), parents)
        # 混合模式要求两路检索使用同一版本的资料，防止引用已经删除或替换的内容。
        if kb["revision"] != kb["indexed_revision"] or not kb["collection"]:
            raise KnowledgeError(409, "文档已变化，请先重建索引再进行混合检索或问答")
        from src.retrievers.hybrid_retriever import HybridRetriever
        from src.retrievers.reranker import Reranker
        from src.retrievers.retrieval_pipeline import RetrievalPipeline

        if self.reranker is None:
            self.reranker = Reranker(self.settings.reranker_model, self.settings.device)
        return RetrievalPipeline(
            ParentRetriever(
                HybridRetriever(self._store(kb["collection"]), bm25), parents
            ),
            self.reranker,
        )

    def search(self, kb_id, question, mode="hybrid", top_k=3):
        """执行检索，返回父段正文、来源及召回和重排序分数。"""
        with self.lock, self.db() as db:
            pipeline = self._pipeline(db, kb_id, mode)
            results = pipeline.search(
                question, top_k=top_k, child_top_k=max(10, top_k), candidate_k=72
            )
            return {
                "query": question,
                "mode": mode,
                "items": [
                    {
                        "content": r["document"].page_content,
                        "metadata": r["document"].metadata,
                        "score": r["score"],
                        "rerank_score": r.get("rerank_score"),
                    }
                    for r in results
                ],
            }

    def ask(self, kb_id, question):
        """将指定知识库的混合检索流水线交给 Agent 执行问答。"""
        from src.services.agent_service import AgentService

        with self.lock, self.db() as db:
            pipeline = self._pipeline(db, kb_id, "hybrid")
            return AgentService(pipeline).ask(question)
