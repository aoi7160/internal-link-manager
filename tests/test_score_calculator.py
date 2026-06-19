import score_calculator


def test_pagerank_simple_chain():
    """1 -> 2 -> 3 の単純チェーンで 3 が最も高い"""
    articles = [{"id": 1}, {"id": 2}, {"id": 3}]
    links = [
        {"from_article_id": 1, "to_article_id": 2},
        {"from_article_id": 2, "to_article_id": 3},
    ]
    scores = score_calculator.compute_pagerank(articles, links, iterations=30)
    assert scores[3] > scores[2] > scores[1]
    # 正規化されているので 0〜1
    assert 0 <= scores[1] <= 1
    assert scores[3] == 1.0  # 最大が 1.0


def test_pagerank_orphan_gets_low_score():
    """孤立記事（被リンクなし）は最低スコア付近"""
    articles = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 99}]
    links = [
        {"from_article_id": 1, "to_article_id": 2},
        {"from_article_id": 2, "to_article_id": 3},
    ]
    scores = score_calculator.compute_pagerank(articles, links, iterations=30)
    assert scores[99] <= scores[1]  # 孤立は最低レベル


def test_pagerank_handles_empty():
    assert score_calculator.compute_pagerank([], []) == {}


def test_inbound_counts():
    articles = [{"id": 1}, {"id": 2}, {"id": 3}]
    links = [
        {"from_article_id": 1, "to_article_id": 2},
        {"from_article_id": 3, "to_article_id": 2},
        {"from_article_id": 1, "to_article_id": 3},
    ]
    counts = score_calculator.compute_inbound_counts(articles, links)
    assert counts[1] == 0
    assert counts[2] == 2
    assert counts[3] == 1
