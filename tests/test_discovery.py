from unittest.mock import patch, MagicMock
import discovery


def test_extract_article_urls_filters_target_path(sample_sitemap_xml):
    urls = discovery.extract_article_urls(sample_sitemap_xml)
    assert "https://www.w2solution.co.jp/useful_info_ec/1001/" in urls or "https://www.w2solution.co.jp/useful_info_ec/1001" in urls
    assert "https://www.w2solution.co.jp/useful_info_ec/1002/" in urls or "https://www.w2solution.co.jp/useful_info_ec/1002" in urls
    assert "https://www.w2solution.co.jp/useful_info_ec/1003/" in urls or "https://www.w2solution.co.jp/useful_info_ec/1003" in urls
    # other_page は対象外
    assert all("other_page" not in u for u in urls)
    assert len(urls) == 3


def test_extract_article_urls_handles_empty():
    assert discovery.extract_article_urls("") == []


def test_fetch_sitemap_returns_text_on_success(sample_sitemap_xml):
    mock_resp = MagicMock(status_code=200, text=sample_sitemap_xml)
    mock_resp.raise_for_status = MagicMock()
    with patch("discovery.requests.get", return_value=mock_resp):
        result = discovery.fetch_sitemap("https://example.com/sitemap.xml")
    assert "useful_info_ec/1001" in result


def test_discover_articles_inserts_new_urls(sample_sitemap_xml):
    inserted = []
    with patch("discovery.fetch_sitemap", return_value=sample_sitemap_xml), \
         patch("discovery.db.upsert_article", side_effect=lambda url, **kw: inserted.append(url) or len(inserted)):
        count = discovery.discover_articles()
    assert count == 3
    assert all("useful_info_ec" in u for u in inserted)


def test_collect_article_urls_follows_sitemap_index():
    """sitemap index を再帰展開して useful_info_ec URL を収集する"""
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sub1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sub2.xml</loc></sitemap>
</sitemapindex>"""
    sub1_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.w2solution.co.jp/useful_info_ec/1001/</loc></url>
  <url><loc>https://www.w2solution.co.jp/other/</loc></url>
</urlset>"""
    sub2_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.w2solution.co.jp/useful_info_ec/1002/</loc></url>
  <url><loc>https://www.w2solution.co.jp/useful_info_ec/1003/</loc></url>
</urlset>"""

    def fetch_mock(url):
        if "sub1" in url:
            return sub1_xml
        if "sub2" in url:
            return sub2_xml
        return index_xml

    with patch("discovery.fetch_sitemap", side_effect=fetch_mock):
        urls = discovery.collect_article_urls("https://example.com/sitemap.xml")

    assert len(urls) == 3
    assert any("1001" in u for u in urls)
    assert any("1002" in u for u in urls)
    assert any("1003" in u for u in urls)


def test_is_sitemap_index_detects_correctly():
    index = "<?xml version='1.0'?><sitemapindex xmlns='...'><sitemap><loc>...</loc></sitemap></sitemapindex>"
    urlset = "<?xml version='1.0'?><urlset xmlns='...'><url><loc>...</loc></url></urlset>"
    assert discovery.is_sitemap_index(index) is True
    assert discovery.is_sitemap_index(urlset) is False
    assert discovery.is_sitemap_index("") is False
