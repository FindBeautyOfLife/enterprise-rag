
from pathlib import Path
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader


# ==================================================
# 1. 加载父文档
# ==================================================
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

parents = DocxLoader(file_path).load()

print("父 Document 数量：", len(parents))


# ==================================================
# 2. 建立父文档索引
# ==================================================
parent_store = {}

for doc in parents:
    parent_id = (
        doc.metadata["source"],
        doc.metadata["chapter"],
        doc.metadata["article"]
    )

    parent_store[parent_id] = doc


# ==================================================
# 3. 创建子 Chunk
# ==================================================
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

children = splitter.split_documents(parents)

print("子 Chunk 数量：", len(children))


# ==================================================
# 4. 根据子 Chunk 找到父文档
# ==================================================
def get_parent(chunk):
    parent_id = (
        chunk.metadata["source"],
        chunk.metadata["chapter"],
        chunk.metadata["article"]
    )

    return parent_store[parent_id]


# ==================================================
# 5. 模拟检索到 Chunk 43
# ==================================================
retrieved_chunk = children[43]

print("\n========== 检索到的子 Chunk ==========")
print(retrieved_chunk.page_content)

parent_doc = get_parent(retrieved_chunk)

print("\n========== 恢复完整父文档 ==========")
print(parent_doc.page_content)
