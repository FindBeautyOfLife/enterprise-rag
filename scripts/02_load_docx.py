
from pathlib import Path
from docx import Document

BASE_DIR = Path(__file__).resolve().parent.parent
file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

# 加载 Word 文档
doc = Document(file_path)

print("文档段落总数：", len(doc.paragraphs))

# 读取前10个非空段落
count = 0

for paragraph in doc.paragraphs:
    text = paragraph.text.strip()

    if not text:
        continue

    print(f"段落 {count + 1}：{text}")

    count += 1

    if count >= 10:
        break


print("\n前10个非空段落及其样式：")

count = 0

for paragraph in doc.paragraphs:
    text = paragraph.text.strip()

    if not text:
        continue

    print(f"文本：{text[:60]}")
    print(f"样式：{paragraph.style.name}")
    print("-" * 40)

    count += 1

    if count >= 10:
        break


import re

# 章标题和条款的正则表达式
chapter_pattern = r"^第[一二三四五六七八九十百零〇]+章"
article_pattern = r"^第[一二三四五六七八九十百零〇]+条"

chapter_count = 0
article_count = 0

for paragraph in doc.paragraphs:
    text = paragraph.text.strip()

    if not text:
        continue

    if re.match(chapter_pattern, text):
        chapter_count += 1
        print(f"[章标题] {text}")

    elif re.match(article_pattern, text):
        article_count += 1
        print(f"[条款] {text[:45]}...")

print("\n统计结果：")
print("章节数量：", chapter_count)
print("条款数量：", article_count)
