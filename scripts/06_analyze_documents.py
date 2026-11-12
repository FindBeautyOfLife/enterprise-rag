
from pathlib import Path
import sys
import statistics

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader

file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

loader = DocxLoader(file_path)
documents = loader.load()

# 统计每个 Document 的字符长度
lengths = [len(doc.page_content) for doc in documents]

print("Document 数量：", len(documents))
print("总字符数：", sum(lengths))
print("最短长度：", min(lengths))
print("最长长度：", max(lengths))
print("平均长度：", round(statistics.mean(lengths), 2))
print("中位数长度：", statistics.median(lengths))

print("\n长度最大的 10 个条款：")

sorted_docs = sorted(
    documents,
    key=lambda doc: len(doc.page_content),
    reverse=True
)

for doc in sorted_docs[:10]:
    print(
        doc.metadata["article"],
        "字符数：",
        len(doc.page_content)
    )

ranges = {
    "0-100": 0,
    "101-300": 0,
    "301-500": 0,
    "501-1000": 0,
    "1000以上": 0
}

for length in lengths:
    if length <= 100:
        ranges["0-100"] += 1
    elif length <= 300:
        ranges["101-300"] += 1
    elif length <= 500:
        ranges["301-500"] += 1
    elif length <= 1000:
        ranges["501-1000"] += 1
    else:
        ranges["1000以上"] += 1

print("\nDocument 长度分布：")

for name, count in ranges.items():
    print(f"{name}: {count} 个")
