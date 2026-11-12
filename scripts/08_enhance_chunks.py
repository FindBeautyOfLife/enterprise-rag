
from pathlib import Path
import sys

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader

file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

# 1. 加载原始 Document
documents = DocxLoader(file_path).load()

# 2. 创建条款标题映射
article_titles = {
    (doc.metadata["chapter"], doc.metadata["article"]):
        doc.page_content.split("\n")[0]
    for doc in documents
}

# 3. 文本切分
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "；", "，", ""]
)

original_chunks = splitter.split_documents(documents)

# 4. 创建增强后的 Chunk
enhanced_chunks = []

for chunk in original_chunks:
    chapter = chunk.metadata["chapter"]
    article = chunk.metadata["article"]

    article_title = article_titles[(chapter, article)]

    # 已包含完整条款标题的 Chunk 不重复添加
    if chunk.page_content.startswith(article_title):
        enhanced_content = chunk.page_content
    else:
        enhanced_content = (
            f"章节：{chapter}\n"
            f"条款：{article_title}\n\n"
            f"{chunk.page_content}"
        )

    enhanced_chunks.append(
        Document(
            page_content=enhanced_content,
            metadata=chunk.metadata.copy()
        )
    )

print("原始 Chunk 数量：", len(original_chunks))
print("增强 Chunk 数量：", len(enhanced_chunks))

print("\n第三十七条增强结果：")

for chunk in enhanced_chunks:
    if chunk.metadata["article"] == "第三十七条":
        print("-" * 40)
        print(chunk.page_content[:180])
