
from pathlib import Path
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader

# 加载文档
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

loader = DocxLoader(file_path)
documents = loader.load()

# 创建文本切分器
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

# 执行切分
chunks = splitter.split_documents(documents)

print("原始 Document 数量：", len(documents))
print("切分后 Chunk 数量：", len(chunks))
print("最长 Chunk 字符数：", max(len(c.page_content) for c in chunks))
print("最短 Chunk 字符数：", min(len(c.page_content) for c in chunks))


target_article = "第三十七条"

target_chunks = [
    chunk for chunk in chunks
    if chunk.metadata["article"] == target_article
]

print(f"\n{target_article} 被切分为 {len(target_chunks)} 个 Chunk")

for i, chunk in enumerate(target_chunks, start=1):
    print(f"\n{'=' * 40}")
    print(f"Chunk {i}")
    print(f"字符数：{len(chunk.page_content)}")
    print(f"Metadata：{chunk.metadata}")
    print(f"内容：\n{chunk.page_content}")

# 获取第三十七条的完整原文
original_doc = next(
    doc for doc in documents
    if doc.metadata["article"] == "第三十七条"
)

# 第一行包含条款编号和主题
article_title = original_doc.page_content.split("\n")[0]

print("条款标题：", article_title)

# 为第二个 Chunk 补充上下文
chunk = target_chunks[1]

enhanced_content = (
    f"章节：{chunk.metadata['chapter']}\n"
    f"条款：{article_title}\n\n"
    f"{chunk.page_content}"
)

print("\n增强前：")
print(chunk.page_content)

print("\n增强后：")
print(enhanced_content)
