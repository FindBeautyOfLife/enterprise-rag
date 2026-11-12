
import hashlib
from collections import defaultdict
from pathlib import Path
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader


# 1. 通用哈希函数
def make_hash(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()[:16]


# 2. 加载文档
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"
documents = DocxLoader(file_path).load()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

chunks = splitter.split_documents(documents)


# 3. 为当前知识库指定逻辑文件标识
document_id = make_hash("nuist_charter_2023")

# 按父条款统计局部 Chunk 序号
parent_counters = defaultdict(int)

for chunk in chunks:
    article = chunk.metadata["article"]

    parent_id = make_hash(
        f"{document_id}|{article}"
    )

    chunk_index = parent_counters[parent_id]
    parent_counters[parent_id] += 1

    chunk_id = make_hash(
        f"{parent_id}|{chunk_index}"
    )

    content_hash = make_hash(chunk.page_content)

    chunk.metadata.update({
        "document_id": document_id,
        "parent_id": parent_id,
        "chunk_id": chunk_id,
        "chunk_index": chunk_index,
        "content_hash": content_hash
    })


# 4. 查看第三十七条两个 Chunk
print("========== 第三十七条 ID ==========")

target_chunks = [
    chunk for chunk in chunks
    if chunk.metadata["article"] == "第三十七条"
]

for chunk in target_chunks:
    print("\nDocument ID：", chunk.metadata["document_id"])
    print("Parent ID：", chunk.metadata["parent_id"])
    print("Chunk ID：", chunk.metadata["chunk_id"])
    print("Chunk Index：", chunk.metadata["chunk_index"])
    print("Content Hash：", chunk.metadata["content_hash"])


# 5. 验证内容变化是否影响 Chunk ID
chunk = target_chunks[0]

old_chunk_id = chunk.metadata["chunk_id"]
old_hash = chunk.metadata["content_hash"]

new_content = chunk.page_content + "新增测试内容"

new_hash = make_hash(new_content)

print("\n========== 内容修改实验 ==========")
print("Chunk ID 是否保持不变：", old_chunk_id == chunk.metadata["chunk_id"])
print("Content Hash 是否变化：", old_hash != new_hash)
