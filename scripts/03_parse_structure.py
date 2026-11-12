
import re
from pathlib import Path
from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

doc = Document(file_path)

chapter_pattern = r"^第[一二三四五六七八九十百零〇]+章"
article_pattern = r"^第[一二三四五六七八九十百零〇]+条"

documents = []

current_chapter = None
current_article = None
current_content = []


def save_article():
    if current_article is not None:
        documents.append({
            "chapter": current_chapter,
            "article": current_article,
            "content": "\n".join(current_content)
        })


for paragraph in doc.paragraphs:
    text = paragraph.text.strip()

    if not text:
        continue

    # 识别章节
    if re.match(chapter_pattern, text):
        save_article()

        current_chapter = text
        current_article = None
        current_content = []

    # 识别条款
    elif re.match(article_pattern, text):
        save_article()

        match = re.match(article_pattern, text)
        current_article = match.group()
        current_content = [text]

    # 普通正文
    elif current_article is not None:
        current_content.append(text)

# 保存最后一个条款
save_article()

print("提取条款数量：", len(documents))

# 查看第18条
for item in documents:
    if item["article"] == "第十八条":
        print("\n章节：", item["chapter"])
        print("条款：", item["article"])
        print("内容：\n", item["content"])
        break

from langchain_core.documents import Document

langchain_docs = []

for item in documents:
    doc = Document(
        page_content=item["content"],
        metadata={
            "source": file_path.name,
            "chapter": item["chapter"],
            "article": item["article"]
        }
    )
    langchain_docs.append(doc)

print("\nLangChain Document 数量：", len(langchain_docs))

print("\n第18个 Document：")
print(langchain_docs[17])
