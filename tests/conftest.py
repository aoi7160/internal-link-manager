import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_supabase():
    """supabase-py クライアントをモック化したフィクスチャ"""
    client = MagicMock()
    return client


@pytest.fixture
def sample_articles():
    return [
        {"id": 1, "url": "https://www.w2solution.co.jp/useful_info_ec/1001/",
         "main_kw": "EC構築", "title": "EC構築入門", "crawled_at": None,
         "link_juice_score": 0, "status": "active"},
        {"id": 2, "url": "https://www.w2solution.co.jp/useful_info_ec/1002/",
         "main_kw": "ECサイト 比較", "title": "比較ガイド", "crawled_at": None,
         "link_juice_score": 0, "status": "active"},
        {"id": 3, "url": "https://www.w2solution.co.jp/useful_info_ec/1003/",
         "main_kw": None, "title": None, "crawled_at": None,
         "link_juice_score": 0, "status": "active"},
    ]


@pytest.fixture
def sample_links():
    return [
        {"id": 1, "from_article_id": 1, "to_article_id": 2, "anchor_text": "比較記事へ"},
        {"id": 2, "from_article_id": 2, "to_article_id": 1, "anchor_text": "戻る"},
        {"id": 3, "from_article_id": 2, "to_article_id": 3, "anchor_text": "詳細"},
    ]


@pytest.fixture
def sample_sitemap_xml():
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.w2solution.co.jp/useful_info_ec/1001/</loc></url>
  <url><loc>https://www.w2solution.co.jp/useful_info_ec/1002/</loc></url>
  <url><loc>https://www.w2solution.co.jp/useful_info_ec/1003/</loc></url>
  <url><loc>https://www.w2solution.co.jp/other_page/</loc></url>
</urlset>
"""
