"""应用配置：默认使用项目内的数据和模型目录，相对配置路径按工作目录解析。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    embedding_model: str
    reranker_model: str
    device: str
    max_upload_bytes: int

    @classmethod
    def from_env(cls):
        local_model = BASE_DIR / "data/models/bge-small-zh-v1.5"
        return cls(
            data_dir=Path(os.getenv("RAG_DATA_DIR", str(BASE_DIR / "data/knowledge"))).resolve(),
            embedding_model=os.getenv("RAG_EMBEDDING_MODEL", str(local_model)),
            reranker_model=os.getenv("RAG_RERANKER_MODEL", "BAAI/bge-reranker-base"),
            device=os.getenv("RAG_DEVICE", "cpu"),
            max_upload_bytes=int(os.getenv("RAG_MAX_UPLOAD_MB", "20")) * 1024 * 1024,
        )
