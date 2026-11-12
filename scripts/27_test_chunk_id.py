
import hashlib
from pathlib import Path
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader


# 1. 加载和切分文档
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

documents = DocxLoader(file_path).load()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

chunks = splitter.split_documents(documents)


# 2. 生成内容相关 ID
def generate_chunk_id(chunk):

    source = chunk.metadata["source"]
    chapter = chunk.metadata["chapter"]
    article = chunk.metadata["article"]

    raw_text = (
        f"{source}|{chapter}|{article}|{chunk.page_content}"
    )

    return hashlib.sha256(
        raw_text.encode("utf-8")
    ).hexdigest()[:16]


# 3. 输出前五个 Chunk 的 ID
print("Chunk 数量：", len(chunks))

for i, chunk in enumerate(chunks[:5]):
    chunk_id = generate_chunk_id(chunk)

    print(
        f"Chunk {i} | "
        f"{chunk.metadata['article']} | "
        f"ID：{chunk_id}"
    )


# 4. 验证相同内容生成相同 ID
id1 = generate_chunk_id(chunks[0])
id2 = generate_chunk_id(chunks[0])

print("\n相同 Chunk 的 ID 是否一致：", id1 == id2)


# 5. 验证内容变化后 ID 是否变化
from langchain_core.documents import Document

modified_chunk = Document(
    page_content=chunks[0].page_content + "新增测试内容",
    metadata=chunks[0].metadata.copy()
)

id3 = generate_chunk_id(modified_chunk)

print("原始 ID：", id1)
print("修改后 ID：", id3)
print("内容变化后 ID 是否变化：", id1 != id3)
