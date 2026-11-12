
# Dense Retrieval 排名
dense_ranks = {
    "第二十九条": 1,
    "第三十七条": 6,
    "第四十九条": 3
}

# BM25 排名
bm25_ranks = {
    "第二十九条": 1,
    "第三十七条": 2,
    "第四十九条": 3
}

# RRF 平滑参数
k = 60

# 计算融合分数
rrf_scores = {}

for article in dense_ranks:
    dense_rank = dense_ranks[article]
    bm25_rank = bm25_ranks[article]

    score = (
        1 / (k + dense_rank)
        + 1 / (k + bm25_rank)
    )

    rrf_scores[article] = score

# 按融合分数降序排序
sorted_results = sorted(
    rrf_scores.items(),
    key=lambda item: item[1],
    reverse=True
)

print("========== RRF 融合结果 ==========")

for rank, (article, score) in enumerate(sorted_results, start=1):
    print(
        f"Top {rank} | "
        f"{article} | "
        f"RRF分数：{score:.6f}"
    )
