
import re
from pathlib import Path

from docx import Document as WordDocument
from langchain_core.documents import Document


class DocxLoader:

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def load(self):
        word_doc = WordDocument(self.file_path)

        chapter_pattern = r"^第[一二三四五六七八九十百零〇]+章"
        article_pattern = r"^第[一二三四五六七八九十百零〇]+条"

        documents = []

        current_chapter = None
        current_article = None
        current_content = []

        def save_article():
            if current_article is not None:
                documents.append(
                    Document(
                        page_content="\n".join(current_content),
                        metadata={
                            "source": self.file_path.name,
                            "chapter": current_chapter,
                            "article": current_article
                        }
                    )
                )

        for paragraph in word_doc.paragraphs:
            text = paragraph.text.strip()

            if not text:
                continue

            if re.match(chapter_pattern, text):
                save_article()
                current_chapter = text
                current_article = None
                current_content = []

            elif re.match(article_pattern, text):
                save_article()
                current_article = re.match(
                    article_pattern, text
                ).group()
                current_content = [text]

            elif current_article is not None:
                current_content.append(text)

        save_article()

        return documents
