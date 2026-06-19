import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import database as db
import time

BASE_DOMAIN = "www.w2solution.co.jp"
BASE_PATH = "/useful_info_ec/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}


def _is_internal_article(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == BASE_DOMAIN and parsed.path.startswith(BASE_PATH)


def _strip_query(url: str) -> str:
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return clean.geturl().rstrip("/")


def crawl_article(article_id: int, sleep_seconds: float = 1.5) -> dict:
    article = db.get_article(article_id)
    if not article:
        return {"error": "Article not found", "article_id": article_id}

    url = article["url"]
    time.sleep(sleep_seconds)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        db.update_article_status(article_id, "error")
        return {"error": str(e), "article_id": article_id, "status": "error"}

    if resp.status_code == 404:
        db.update_article_status(article_id, "404")
        return {"article_id": article_id, "url": url, "status": "404", "links_found": 0}

    if resp.status_code >= 400:
        db.update_article_status(article_id, "error")
        return {"error": f"HTTP {resp.status_code}", "article_id": article_id, "status": "error"}

    db.update_article_status(article_id, "active")

    soup = BeautifulSoup(resp.text, "html.parser")
    title_tag = soup.find("title")
    if title_tag and not article.get("title"):
        db.update_article(article_id, title=title_tag.text.strip())

    db.delete_links_from(article_id)

    found_links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        try:
            absolute = urljoin(url, href)
            clean = _strip_query(absolute)
            if not _is_internal_article(clean):
                continue
        except (ValueError, UnicodeError):
            continue
        if clean == url or clean in seen:
            continue
        seen.add(clean)
        anchor = a.get_text(strip=True)[:200]
        to_id = db.upsert_article(clean)
        db.upsert_link(article_id, to_id, anchor)
        found_links.append({"url": clean, "anchor": anchor})

    db.set_crawled(article_id)
    return {"article_id": article_id, "url": url, "status": "active",
            "links_found": len(found_links), "links": found_links}
