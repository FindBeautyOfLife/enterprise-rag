"""提供后端接口并托管同源前端，启动命令：uvicorn src.api.main:app --reload。"""

import io
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from src.config import BASE_DIR, Settings
from src.services.knowledge_service import KnowledgeError, KnowledgeService

logger = logging.getLogger(__name__)


class BaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        if not value.strip():
            raise ValueError("知识库名称不能为空")
        return value.strip()


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    knowledge_base_id: str = Field(min_length=1, max_length=64)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class SearchRequest(AskRequest):
    mode: str = Field(default="hybrid", pattern="^(keyword|hybrid)$")
    top_k: int = Field(default=3, ge=1, le=10)


def create_app(settings=None, service=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.knowledge = service or KnowledgeService(settings)
        yield

    app = FastAPI(
        title="Enterprise RAG · 知识库工作台", version="0.2.0", lifespan=lifespan
    )

    @app.exception_handler(KnowledgeError)
    async def knowledge_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    @app.get("/health")
    def health(request: Request):
        bases = request.app.state.knowledge.list_bases()
        return {
            "status": "ok",
            "knowledge_bases": len(bases),
            "documents": sum(b["document_count"] for b in bases),
            "chunks": sum(b["chunk_count"] for b in bases),
            "llm_configured": bool(os.getenv("DASHSCOPE_API_KEY")),
            "max_upload_bytes": settings.max_upload_bytes,
        }

    @app.get("/api/v1/knowledge-bases")
    def list_bases(request: Request):
        return request.app.state.knowledge.list_bases()

    @app.post("/api/v1/knowledge-bases", status_code=201)
    def create_base(data: BaseInput, request: Request):
        return request.app.state.knowledge.save_base(data.name, data.description)

    @app.put("/api/v1/knowledge-bases/{kb_id}")
    def update_base(kb_id: str, data: BaseInput, request: Request):
        return request.app.state.knowledge.save_base(data.name, data.description, kb_id)

    @app.delete("/api/v1/knowledge-bases/{kb_id}", status_code=204)
    def delete_base(kb_id: str, request: Request):
        request.app.state.knowledge.delete_base(kb_id)

    @app.get("/api/v1/knowledge-bases/{kb_id}/documents")
    def documents(kb_id: str, request: Request):
        return request.app.state.knowledge.documents(kb_id)

    async def receive_file(kb_id, file, request, document_id=None):
        try:
            content = await file.read(settings.max_upload_bytes + 1)
            return await run_in_threadpool(
                request.app.state.knowledge.upload,
                kb_id,
                file.filename or "",
                content,
                document_id,
            )
        finally:
            await file.close()

    @app.post("/api/v1/knowledge-bases/{kb_id}/documents", status_code=201)
    async def upload(kb_id: str, file: UploadFile, request: Request):
        return await receive_file(kb_id, file, request)

    @app.put("/api/v1/knowledge-bases/{kb_id}/documents/{document_id}")
    async def replace_document(
        kb_id: str, document_id: str, file: UploadFile, request: Request
    ):
        return await receive_file(kb_id, file, request, document_id)

    @app.get("/api/v1/knowledge-bases/{kb_id}/documents/{document_id}/chunks")
    def preview(
        kb_id: str,
        document_id: str,
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ):
        return request.app.state.knowledge.preview(kb_id, document_id, offset, limit)

    @app.get("/api/v1/knowledge-bases/{kb_id}/documents/{document_id}/download")
    def download(kb_id: str, document_id: str, request: Request):
        filename, raw = request.app.state.knowledge.download(kb_id, document_id)
        return StreamingResponse(
            io.BytesIO(raw),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
            },
        )

    @app.delete(
        "/api/v1/knowledge-bases/{kb_id}/documents/{document_id}", status_code=204
    )
    def delete_document(kb_id: str, document_id: str, request: Request):
        request.app.state.knowledge.delete_document(kb_id, document_id)

    @app.post("/api/v1/knowledge-bases/{kb_id}/reindex")
    def reindex(kb_id: str, request: Request):
        return request.app.state.knowledge.rebuild(kb_id)

    @app.post("/api/v1/search")
    def search(data: SearchRequest, request: Request):
        try:
            return request.app.state.knowledge.search(
                data.knowledge_base_id, data.question, data.mode, data.top_k
            )
        except KnowledgeError:
            raise
        except Exception as exc:
            logger.exception("检索失败")
            raise HTTPException(503, "检索暂不可用，请检查模型配置和服务日志") from exc

    @app.post("/api/v1/ask")
    def ask(data: AskRequest, request: Request):
        if not os.getenv("DASHSCOPE_API_KEY"):
            raise HTTPException(503, "未配置 DASHSCOPE_API_KEY，可先使用关键词检索")
        try:
            return request.app.state.knowledge.ask(
                data.knowledge_base_id, data.question
            )
        except KnowledgeError:
            raise
        except Exception as exc:
            logger.exception("问答失败")
            raise HTTPException(
                503, "问答暂不可用，请检查模型和大模型服务配置"
            ) from exc

    frontend = BASE_DIR / "frontend"
    app.mount("/static", StaticFiles(directory=frontend), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(frontend / "index.html")

    return app


app = create_app()
