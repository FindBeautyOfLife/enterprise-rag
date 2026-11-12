"""解析上传文件，生成父段和带有确定性标识的子片段。"""

import hashlib
import io
import re
import zipfile
from pathlib import PurePosixPath

from docx import Document as WordDocument
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.vectorstores.id_utils import make_hash, prepare_chunks

SUPPORTED_SUFFIXES = {".docx", ".txt", ".md"}


def parse_upload(filename, content, document_key):
    # 仅保留客户端文件名，不将其作为服务端文件路径使用。
    filename = PurePosixPath(filename.replace("\\", "/")).name
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("仅支持 .docx、.txt、.md 文件")
    if not content:
        raise ValueError("文件不能为空")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if (
                    sum(info.file_size for info in archive.infolist())
                    > 50 * 1024 * 1024
                ):
                    raise ValueError("DOCX 解压后超过 50 MB，请拆分文件")
            word = WordDocument(io.BytesIO(content))
            lines = [p.text.strip() for p in word.paragraphs if p.text.strip()]
            # 提取表格文字，补充原章程加载器未处理的表格内容。
            lines.extend(
                " | ".join(c.text for c in row.cells)
                for table in word.tables
                for row in table.rows
            )
            text = "\n".join(lines)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("无法解析 DOCX，请确认文件完整且未加密") from exc
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("TXT / Markdown 请使用 UTF-8 编码") from exc
    if not text.strip() or "\x00" in text:
        raise ValueError("文档没有可索引的文本，或包含无效字符")

    # 章程保留章节和条款结构，普通文档按标题或段落组织父段。
    sections = []
    chapter = "正文"
    article = "段落 1"
    buffer = []

    def flush():
        if buffer:
            sections.append((chapter, article, "\n".join(buffer)))
            buffer.clear()

    for line in text.splitlines():
        line = line.strip()
        if not line:
            if not re.match(r"^第.+条$", article):
                flush()
                article = f"段落 {len(sections) + 1}"
            continue
        if re.match(r"^第[一二三四五六七八九十百零〇\d]+章", line) or re.match(
            r"^#{1,6}\s", line
        ):
            flush()
            chapter = line
            article = f"段落 {len(sections) + 1}"
        elif match := re.match(r"^第[一二三四五六七八九十百零〇\d]+条", line):
            flush()
            article = match.group()
        buffer.append(line)
    flush()

    # 限制父段长度，避免无结构的长文档占满模型上下文。
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1800, chunk_overlap=0)
    parents = []
    document_id = make_hash(document_key)
    for ch, ar, body in sections:
        for part in parent_splitter.split_text(body):
            position = len(parents)
            label = f"{ar} · {position + 1}"
            parents.append(
                Document(
                    page_content=part,
                    metadata={
                        "source": filename,
                        "chapter": ch,
                        "article": label,
                        "document_id": document_id,
                        "parent_id": make_hash(f"{document_id}|{ch}|{label}"),
                    },
                )
            )
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "；", "，", ""],
    )
    chunks = prepare_chunks(splitter.split_documents(parents), document_key)
    return filename, hashlib.sha256(content).hexdigest(), parents, chunks
