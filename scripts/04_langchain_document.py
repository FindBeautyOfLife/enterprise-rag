
from langchain_core.documents import Document

doc = Document(
    page_content="第十八条 教职工的权利",
    metadata={
        "source": "南京信息工程大学章程.docx",
        "chapter": "第三章 教职工的权利与义务",
        "article": "第十八条"
    }
)

print("对象类型：", type(doc))
print("文本内容：", doc.page_content)
print("元数据：", doc.metadata)
print("章节：", doc.metadata["chapter"])
