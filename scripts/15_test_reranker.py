
from sentence_transformers import CrossEncoder

# 1. 加载 Reranker 模型
model = CrossEncoder(
    "BAAI/bge-reranker-base",
    device="cpu"
)

# 2. 用户问题
query = "南京信息工程大学学术委员会有哪些职责？"

# 3. 候选文本
documents = [
    "第二十九条 中国共产党南京信息工程大学委员会是学校的领导核心，主要职责是决定学校重大问题。",

    "第三十七条 学术委员会按照章程履行以下职责：审议学科建设、专业设置，评定教学科研成果，调查处理学术纠纷。",

    "第四十九条 社会捐赠管理：学校鼓励并接受各类社会捐赠。"
]


# ==================================================
# Query Rewrite 对照实验
# ==================================================

queries = [
    "南京信息工程大学学术委员会有哪些职责？",
    "学术委员会有哪些职责？"
]

for query in queries:

    pairs = [
        (query, doc)
        for doc in documents
    ]

    scores = model.predict(pairs)

    results = sorted(
        zip(documents, scores),
        key=lambda item: float(item[1]),
        reverse=True
    )

    print(f"\n========== Query：{query} ==========")

    for rank, (doc, score) in enumerate(
        results,
        start=1
    ):
        print(
            f"Top {rank} | "
            f"分数：{float(score):.4f} | "
            f"{doc[:45]}"
        )
