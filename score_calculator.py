DAMPING = 0.85
DEFAULT_ITERATIONS = 20


def compute_inbound_counts(articles, links):
    article_ids = {a["id"] for a in articles}
    counts = {aid: 0 for aid in article_ids}
    for l in links:
        if l["to_article_id"] in article_ids:
            counts[l["to_article_id"]] = counts.get(l["to_article_id"], 0) + 1
    return counts


def compute_pagerank(articles, links, iterations: int = DEFAULT_ITERATIONS):
    if not articles:
        return {}
    article_ids = {a["id"] for a in articles}

    # 発リンク数（status='active' 内の links のみ集計）
    outbound = {aid: [] for aid in article_ids}
    inbound = {aid: [] for aid in article_ids}
    for l in links:
        fa = l["from_article_id"]
        ta = l["to_article_id"]
        if fa in article_ids and ta in article_ids:
            outbound[fa].append(ta)
            inbound[ta].append(fa)

    n = len(article_ids)
    scores = {aid: 1.0 / n for aid in article_ids}
    base = (1 - DAMPING) / n

    for _ in range(iterations):
        new_scores = {}
        # ダングリングノード（発リンクなし）の合計スコアを全体に再配分
        dangling_sum = sum(scores[aid] for aid in article_ids if not outbound[aid])
        for aid in article_ids:
            inc = sum(scores[fa] / len(outbound[fa]) for fa in inbound[aid] if outbound[fa])
            new_scores[aid] = base + DAMPING * (inc + dangling_sum / n)
        scores = new_scores

    # 0〜1 に正規化（最大値で割る）
    max_score = max(scores.values()) if scores else 1.0
    if max_score > 0:
        scores = {k: v / max_score for k, v in scores.items()}
    return scores
