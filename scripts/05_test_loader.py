
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.loaders.docx_loader import DocxLoader

file_path = BASE_DIR / "data" / "documents" / "南京信息工程大学章程.docx"

loader = DocxLoader(file_path)
documents = loader.load()

print("Document 数量：", len(documents))

for doc in documents[:3]:
    print("\n章节：", doc.metadata["chapter"])
    print("条款：", doc.metadata["article"])
    print("内容：", doc.page_content[:100])