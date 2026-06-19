import re
import requests
import database as db

SITEMAP_URL = "https://www.w2solution.co.jp/sitemap.xml"
TARGET_PATH = "/useful_info_ec/"
MAX_NESTED_DEPTH = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; W2InternalLinkManager/1.0)",
    "Accept": "application/xml,text/xml,*/*",
}

_LOC_PATTERN = re.compile(r"<loc>(.*?)</loc>", re.IGNORECASE | re.DOTALL)
_SITEMAPINDEX_PATTERN = re.compile(r"<sitemapindex[\s>]", re.IGNORECASE)


def fetch_sitemap(url: str = SITEMAP_URL) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def is_sitemap_index(xml_text: str) -> bool:
    return bool(_SITEMAPINDEX_PATTERN.search(xml_text or ""))


def extract_article_urls(xml_text: str) -> list:
    if not xml_text:
        return []
    matches = _LOC_PATTERN.findall(xml_text)
    urls = []
    for m in matches:
        url = m.strip()
        if TARGET_PATH in url:
            urls.append(url.rstrip("/"))
    return urls


def collect_article_urls(sitemap_url: str = SITEMAP_URL, depth: int = 0) -> list:
    """サイトマップ index も再帰展開して全 useful_info_ec URL を収集する"""
    if depth > MAX_NESTED_DEPTH:
        return []
    try:
        xml = fetch_sitemap(sitemap_url)
    except requests.RequestException as e:
        print(f"[discovery] サイトマップ取得失敗 ({sitemap_url}): {e}")
        return []

    if is_sitemap_index(xml):
        all_urls = []
        sub_sitemap_urls = [m.strip() for m in _LOC_PATTERN.findall(xml)]
        for sub in sub_sitemap_urls:
            all_urls.extend(collect_article_urls(sub, depth=depth + 1))
        seen = set()
        deduped = []
        for u in all_urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

    return extract_article_urls(xml)


def discover_articles(sitemap_url: str = SITEMAP_URL) -> int:
    """サイトマップ取得 → URL 抽出 → DB に upsert"""
    urls = collect_article_urls(sitemap_url)
    for u in urls:
        db.upsert_article(u)
    return len(urls)
