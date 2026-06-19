# 内部リンク管理ツール Supabase 移行 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SQLite ベースの内部リンク管理ツールを Supabase（クラウド PostgreSQL）に移行し、GitHub Actions による週次自動クロール・Slack 通知・CSV エクスポート・前週比較を実装する。

**Architecture:** Flask + supabase-py のローカルアプリと、GitHub Actions cron で走る `crawler_runner.py` が Supabase を共有書き込み。`status` カラムでソフト削除、PageRank 風のリンクジューススコアを毎回計算し `article_score_history` に保存して前週比を出す。

**Tech Stack:** Python 3.11, Flask 3.0, supabase-py 2.0+, BeautifulSoup4, requests, pytest, vis.js, GitHub Actions

**作業ディレクトリ:** `C:\Users\wwahamaji\claude-workspace\internal-link-manager`

**参照する仕様書:** `docs/superpowers/specs/2026-06-19-internal-link-manager-supabase-design.md`

---

## Task 1: Supabase スキーマ SQL を作成し、Supabase 上で実行する

**Files:**
- Create: `supabase_schema.sql`

- [ ] **Step 1: `supabase_schema.sql` を作成**

```sql
-- supabase_schema.sql
-- Supabase ダッシュボード > SQL Editor で実行する

DROP TABLE IF EXISTS article_score_history CASCADE;
DROP TABLE IF EXISTS crawl_sessions CASCADE;
DROP TABLE IF EXISTS link_suggestions CASCADE;
DROP TABLE IF EXISTS clusters CASCADE;
DROP TABLE IF EXISTS article_keywords CASCADE;
DROP TABLE IF EXISTS links CASCADE;
DROP TABLE IF EXISTS articles CASCADE;

CREATE TABLE articles (
  id               BIGSERIAL PRIMARY KEY,
  url              TEXT UNIQUE NOT NULL,
  main_kw          TEXT,
  title            TEXT,
  crawled_at       TIMESTAMPTZ,
  link_juice_score FLOAT DEFAULT 0,
  status           TEXT DEFAULT 'active',
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE links (
  id              BIGSERIAL PRIMARY KEY,
  from_article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  to_article_id   BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  anchor_text     TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(from_article_id, to_article_id)
);

CREATE TABLE article_keywords (
  id         BIGSERIAL PRIMARY KEY,
  article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  keyword    TEXT NOT NULL
);

CREATE TABLE clusters (
  id                BIGSERIAL PRIMARY KEY,
  parent_article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  child_article_id  BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  reason            TEXT,
  ai_suggested      BOOLEAN DEFAULT FALSE,
  confirmed         BOOLEAN DEFAULT FALSE,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(parent_article_id, child_article_id)
);

CREATE TABLE link_suggestions (
  id              BIGSERIAL PRIMARY KEY,
  from_article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  to_article_id   BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  anchor_text     TEXT,
  reason          TEXT,
  confirmed       BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(from_article_id, to_article_id)
);

CREATE TABLE crawl_sessions (
  id                  BIGSERIAL PRIMARY KEY,
  started_at          TIMESTAMPTZ DEFAULT NOW(),
  completed_at        TIMESTAMPTZ,
  articles_discovered INT DEFAULT 0,
  articles_crawled    INT DEFAULT 0,
  links_found         INT DEFAULT 0,
  errors              INT DEFAULT 0,
  triggered_by        TEXT
);

CREATE TABLE article_score_history (
  id               BIGSERIAL PRIMARY KEY,
  article_id       BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  session_id       BIGINT REFERENCES crawl_sessions(id) ON DELETE CASCADE,
  link_juice_score FLOAT,
  inbound_count    INT,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_links_from   ON links(from_article_id);
CREATE INDEX idx_links_to     ON links(to_article_id);
CREATE INDEX idx_articles_status ON articles(status);
CREATE INDEX idx_history_session ON article_score_history(session_id);
CREATE INDEX idx_history_article ON article_score_history(article_id);
```

- [ ] **Step 2: Supabase ダッシュボードで SQL を実行**

Supabase ダッシュボード（https://supabase.com/dashboard/project/tsuitsrwxkwawwqumpxj）→ SQL Editor → New query → 上記 SQL を貼り付けて「Run」。

確認: Table Editor で全 7 テーブルが作成されていること。

- [ ] **Step 3: コミット**

```bash
git add supabase_schema.sql
git commit -m "feat: add Supabase schema with status, score_history, crawl_sessions"
```

---

## Task 2: `requirements.txt` を更新

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: `requirements.txt` を全面置換**

```
flask==3.0.3
flask-cors==4.0.1
requests==2.32.3
beautifulsoup4==4.12.3
anthropic==0.40.0
supabase>=2.7.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 2: pip install で動作確認**

```bash
cd C:\Users\wwahamaji\claude-workspace\internal-link-manager
python -m venv workspace\.venv
workspace\.venv\Scripts\activate
pip install -r requirements.txt
```

Expected: エラーなく完了。

- [ ] **Step 3: コミット**

```bash
git add requirements.txt
git commit -m "chore: switch from psycopg2 to supabase-py, add pytest"
```

---

## Task 3: `.env.example` と `.gitignore` の整備

**Files:**
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: `.env.example` を作成**

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ANTHROPIC_API_KEY=sk-ant-...
TRIGGERED_BY=manual
```

- [ ] **Step 2: `.gitignore` に `.env` 行があることを確認**

`internal-link-manager/.gitignore` を開いて以下が含まれているか確認。なければ追記：

```
.env
workspace/
__pycache__/
*.pyc
output/
data/
.pytest_cache/
```

- [ ] **Step 3: コミット**

```bash
git add .env.example .gitignore
git commit -m "chore: add .env.example template and update .gitignore"
```

---

## Task 4: `url_utils.py` を実装（TDD）

**Files:**
- Create: `url_utils.py`
- Create: `tests/__init__.py`
- Create: `tests/test_url_utils.py`

- [ ] **Step 1: `tests/__init__.py` を空ファイルとして作成**

```python
```

- [ ] **Step 2: `tests/test_url_utils.py` を作成（失敗するテスト）**

```python
import pytest
from url_utils import short_label


def test_short_label_with_trailing_slash():
    assert short_label("https://www.w2solution.co.jp/useful_info_ec/1717/") == "/1717"


def test_short_label_without_trailing_slash():
    assert short_label("https://www.w2solution.co.jp/useful_info_ec/1717") == "/1717"


def test_short_label_no_match_returns_url():
    assert short_label("https://example.com/foo") == "https://example.com/foo"


def test_short_label_none_returns_empty():
    assert short_label(None) == ""


def test_short_label_empty_string():
    assert short_label("") == ""
```

- [ ] **Step 3: テストを実行して失敗を確認**

```bash
pytest tests/test_url_utils.py -v
```

Expected: FAIL（`ModuleNotFoundError: No module named 'url_utils'`）

- [ ] **Step 4: `url_utils.py` を作成**

```python
import re

_PATTERN = re.compile(r"/useful_info_ec/(\d+)/?")


def short_label(url):
    if not url:
        return ""
    m = _PATTERN.search(url)
    return f"/{m.group(1)}" if m else url
```

- [ ] **Step 5: テストを実行して成功を確認**

```bash
pytest tests/test_url_utils.py -v
```

Expected: 5 passed

- [ ] **Step 6: コミット**

```bash
git add url_utils.py tests/__init__.py tests/test_url_utils.py
git commit -m "feat: add url_utils.short_label helper with tests"
```

---

## Task 5: `tests/conftest.py` を作成（共通フィクスチャ）

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: `tests/conftest.py` を作成**

```python
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
```

- [ ] **Step 2: コミット**

```bash
git add tests/conftest.py
git commit -m "test: add common pytest fixtures (mock supabase, sample data)"
```

---

## Task 6: `database.py` を Supabase 対応に全面置換（TDD）

**Files:**
- Modify: `database.py`（完全に書き換え）
- Create: `tests/test_database.py`

- [ ] **Step 1: `tests/test_database.py` を作成（失敗するテスト）**

```python
from unittest.mock import MagicMock, patch
import database as db


def test_fetch_all_paginates_over_1000_rows(mock_supabase):
    """1000件超のテーブルを range() で全件取得できる"""
    def execute_mock():
        offset = mock_supabase.table.return_value.select.return_value.range.call_args[0][0]
        if offset == 0:
            return MagicMock(data=[{"id": i} for i in range(1, 1001)])
        elif offset == 1000:
            return MagicMock(data=[{"id": i} for i in range(1001, 1501)])
        return MagicMock(data=[])

    mock_supabase.table.return_value.select.return_value.range.return_value.execute.side_effect = execute_mock

    with patch.object(db, "_client", mock_supabase):
        result = db.fetch_all("articles")

    assert len(result) == 1500


def test_normalize_url_strips_trailing_slash():
    assert db.normalize_url("https://example.com/foo/") == "https://example.com/foo"


def test_normalize_url_adds_https():
    assert db.normalize_url("example.com/foo") == "https://example.com/foo"


def test_get_articles_returns_with_counts(mock_supabase, sample_articles, sample_links):
    """articles と links から inbound/outbound 数を集計して返す"""
    def table_select(table_name):
        m = MagicMock()
        if table_name == "articles":
            m.select.return_value.eq.return_value.range.return_value.execute.return_value = MagicMock(data=sample_articles)
            m.select.return_value.range.return_value.execute.return_value = MagicMock(data=sample_articles)
        elif table_name == "links":
            m.select.return_value.range.return_value.execute.return_value = MagicMock(data=sample_links)
        return m

    mock_supabase.table.side_effect = table_select

    with patch.object(db, "_client", mock_supabase):
        rows = db.get_articles()

    by_id = {r["id"]: r for r in rows}
    assert by_id[1]["inbound_count"] == 1   # 2→1
    assert by_id[1]["outbound_count"] == 1  # 1→2
    assert by_id[2]["inbound_count"] == 1
    assert by_id[2]["outbound_count"] == 2
    assert by_id[3]["inbound_count"] == 1
    assert by_id[3]["outbound_count"] == 0
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_database.py -v
```

Expected: FAIL（関数未定義）

- [ ] **Step 3: `database.py` を新規実装**

```python
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        _client = create_client(url, key)
    return _client


def fetch_all(table_name: str, page_size: int = 1000, filter_status_active: bool = False):
    """range() でページネーションして全件取得"""
    client = _client or get_client()
    rows = []
    offset = 0
    while True:
        query = client.table(table_name).select("*")
        if filter_status_active and table_name == "articles":
            query = query.eq("status", "active")
        res = query.range(offset, offset + page_size - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def normalize_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and not url.startswith("http"):
        url = "https://" + url
    return url


# ── Articles ──────────────────────────────────────────────────────────────────

def upsert_article(url: str, main_kw: str = None, title: str = None, status: str = "active") -> int:
    url = normalize_url(url)
    client = _client or get_client()
    payload = {"url": url}
    if main_kw is not None:
        payload["main_kw"] = main_kw
    if title is not None:
        payload["title"] = title
    if status is not None:
        payload["status"] = status
    res = client.table("articles").upsert(payload, on_conflict="url").execute()
    return res.data[0]["id"]


def get_articles():
    articles = fetch_all("articles")
    links = fetch_all("links")
    inbound = {}
    outbound = {}
    for l in links:
        outbound[l["from_article_id"]] = outbound.get(l["from_article_id"], 0) + 1
        inbound[l["to_article_id"]] = inbound.get(l["to_article_id"], 0) + 1
    result = []
    for a in articles:
        result.append({
            **a,
            "inbound_count": inbound.get(a["id"], 0),
            "outbound_count": outbound.get(a["id"], 0),
        })
    result.sort(key=lambda r: (r.get("main_kw") is None, r.get("main_kw") or ""))
    return result


def get_article(article_id: int):
    client = _client or get_client()
    res = client.table("articles").select("*").eq("id", article_id).limit(1).execute()
    return res.data[0] if res.data else None


def update_article(article_id: int, main_kw: str = None, title: str = None, status: str = None):
    client = _client or get_client()
    payload = {}
    if main_kw is not None:
        payload["main_kw"] = main_kw
    if title is not None:
        payload["title"] = title
    if status is not None:
        payload["status"] = status
    if payload:
        client.table("articles").update(payload).eq("id", article_id).execute()


def update_article_status(article_id: int, status: str):
    client = _client or get_client()
    client.table("articles").update({"status": status}).eq("id", article_id).execute()


def update_article_score(article_id: int, score: float):
    client = _client or get_client()
    client.table("articles").update({"link_juice_score": score}).eq("id", article_id).execute()


def delete_article(article_id: int):
    client = _client or get_client()
    client.table("articles").delete().eq("id", article_id).execute()


def set_crawled(article_id: int):
    from datetime import datetime, timezone
    client = _client or get_client()
    client.table("articles").update({"crawled_at": datetime.now(timezone.utc).isoformat()}).eq("id", article_id).execute()


# ── Links ─────────────────────────────────────────────────────────────────────

def upsert_link(from_id: int, to_id: int, anchor: str = None):
    client = _client or get_client()
    client.table("links").upsert(
        {"from_article_id": from_id, "to_article_id": to_id, "anchor_text": anchor},
        on_conflict="from_article_id,to_article_id"
    ).execute()


def delete_links_from(article_id: int):
    """再クロール時、その記事の発リンクを全削除（DELETE → INSERT 用）"""
    client = _client or get_client()
    client.table("links").delete().eq("from_article_id", article_id).execute()


def get_links():
    client = _client or get_client()
    articles = {a["id"]: a for a in fetch_all("articles")}
    links = fetch_all("links")
    result = []
    for l in links:
        fa = articles.get(l["from_article_id"], {})
        ta = articles.get(l["to_article_id"], {})
        result.append({
            "id": l["id"],
            "from_url": fa.get("url"),
            "from_kw": fa.get("main_kw"),
            "to_url": ta.get("url"),
            "to_kw": ta.get("main_kw"),
            "anchor_text": l.get("anchor_text"),
            "created_at": l.get("created_at"),
        })
    return result


def delete_link(link_id: int):
    client = _client or get_client()
    client.table("links").delete().eq("id", link_id).execute()


def get_links_for_article(article_id: int):
    client = _client or get_client()
    articles = {a["id"]: a for a in fetch_all("articles")}
    out_res = client.table("links").select("*").eq("from_article_id", article_id).execute()
    in_res = client.table("links").select("*").eq("to_article_id", article_id).execute()
    outbound = [{
        "id": ta_id, "url": articles[ta_id]["url"], "main_kw": articles[ta_id].get("main_kw"),
        "anchor_text": l["anchor_text"]
    } for l in out_res.data if (ta_id := l["to_article_id"]) in articles]
    inbound = [{
        "id": fa_id, "url": articles[fa_id]["url"], "main_kw": articles[fa_id].get("main_kw"),
        "anchor_text": l["anchor_text"]
    } for l in in_res.data if (fa_id := l["from_article_id"]) in articles]
    return {"outbound": outbound, "inbound": inbound}


# ── Clusters ──────────────────────────────────────────────────────────────────

def upsert_cluster(parent_id, child_id, reason=None, ai_suggested=False, confirmed=False):
    client = _client or get_client()
    client.table("clusters").upsert({
        "parent_article_id": parent_id, "child_article_id": child_id,
        "reason": reason, "ai_suggested": ai_suggested, "confirmed": confirmed
    }, on_conflict="parent_article_id,child_article_id").execute()


def get_clusters():
    client = _client or get_client()
    articles = {a["id"]: a for a in fetch_all("articles")}
    clusters = fetch_all("clusters")
    result = []
    for c in clusters:
        pa = articles.get(c["parent_article_id"], {})
        ca = articles.get(c["child_article_id"], {})
        result.append({
            "id": c["id"],
            "parent_id": c["parent_article_id"], "parent_url": pa.get("url"), "parent_kw": pa.get("main_kw"),
            "child_id": c["child_article_id"], "child_url": ca.get("url"), "child_kw": ca.get("main_kw"),
            "reason": c.get("reason"), "ai_suggested": c.get("ai_suggested"),
            "confirmed": c.get("confirmed"), "created_at": c.get("created_at"),
        })
    return result


def confirm_cluster(cluster_id: int, confirmed: bool):
    client = _client or get_client()
    client.table("clusters").update({"confirmed": confirmed}).eq("id", cluster_id).execute()


def delete_cluster(cluster_id: int):
    client = _client or get_client()
    client.table("clusters").delete().eq("id", cluster_id).execute()


# ── Link Suggestions ──────────────────────────────────────────────────────────

def upsert_link_suggestion(from_id, to_id, anchor=None, reason=None):
    client = _client or get_client()
    client.table("link_suggestions").upsert({
        "from_article_id": from_id, "to_article_id": to_id,
        "anchor_text": anchor, "reason": reason
    }, on_conflict="from_article_id,to_article_id").execute()


def get_link_suggestions():
    client = _client or get_client()
    articles = {a["id"]: a for a in fetch_all("articles")}
    suggestions = fetch_all("link_suggestions")
    result = []
    for s in suggestions:
        fa = articles.get(s["from_article_id"], {})
        ta = articles.get(s["to_article_id"], {})
        result.append({
            "id": s["id"],
            "from_id": s["from_article_id"], "from_url": fa.get("url"), "from_kw": fa.get("main_kw"),
            "to_id": s["to_article_id"], "to_url": ta.get("url"), "to_kw": ta.get("main_kw"),
            "anchor_text": s.get("anchor_text"), "reason": s.get("reason"),
            "confirmed": s.get("confirmed"), "created_at": s.get("created_at"),
        })
    return result


def confirm_link_suggestion(suggestion_id: int):
    client = _client or get_client()
    res = client.table("link_suggestions").select("*").eq("id", suggestion_id).limit(1).execute()
    if not res.data:
        return
    s = res.data[0]
    upsert_link(s["from_article_id"], s["to_article_id"], s.get("anchor_text"))
    client.table("link_suggestions").update({"confirmed": True}).eq("id", suggestion_id).execute()


def delete_link_suggestion(suggestion_id: int):
    client = _client or get_client()
    client.table("link_suggestions").delete().eq("id", suggestion_id).execute()


# ── Crawl Sessions ────────────────────────────────────────────────────────────

def create_crawl_session(triggered_by: str) -> int:
    client = _client or get_client()
    res = client.table("crawl_sessions").insert({"triggered_by": triggered_by}).execute()
    return res.data[0]["id"]


def complete_crawl_session(session_id: int, articles_discovered: int, articles_crawled: int,
                            links_found: int, errors: int):
    from datetime import datetime, timezone
    client = _client or get_client()
    client.table("crawl_sessions").update({
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "articles_discovered": articles_discovered,
        "articles_crawled": articles_crawled,
        "links_found": links_found,
        "errors": errors,
    }).eq("id", session_id).execute()


def get_recent_sessions(limit: int = 10):
    client = _client or get_client()
    res = client.table("crawl_sessions").select("*").order("started_at", desc=True).limit(limit).execute()
    return res.data or []


# ── Score History ─────────────────────────────────────────────────────────────

def insert_score_history(session_id: int, rows: list):
    """rows: [{article_id, link_juice_score, inbound_count}]"""
    if not rows:
        return
    client = _client or get_client()
    payload = [{**r, "session_id": session_id} for r in rows]
    for i in range(0, len(payload), 500):
        client.table("article_score_history").insert(payload[i:i+500]).execute()


def get_latest_two_sessions_scores():
    """最新2セッションのスコアスナップショットを返す"""
    sessions = get_recent_sessions(limit=2)
    if len(sessions) < 1:
        return None, None, [], []
    current = sessions[0]
    previous = sessions[1] if len(sessions) > 1 else None
    client = _client or get_client()
    curr_res = client.table("article_score_history").select("*").eq("session_id", current["id"]).execute()
    prev_data = []
    if previous:
        prev_res = client.table("article_score_history").select("*").eq("session_id", previous["id"]).execute()
        prev_data = prev_res.data or []
    return current, previous, curr_res.data or [], prev_data


# ── Graph ─────────────────────────────────────────────────────────────────────

def get_graph_data():
    articles = [a for a in fetch_all("articles") if a.get("status", "active") == "active"]
    links = fetch_all("links")
    clusters = fetch_all("clusters")
    article_ids = {a["id"] for a in articles}

    inbound = {}
    outbound = {}
    for l in links:
        if l["from_article_id"] in article_ids and l["to_article_id"] in article_ids:
            outbound[l["from_article_id"]] = outbound.get(l["from_article_id"], 0) + 1
            inbound[l["to_article_id"]] = inbound.get(l["to_article_id"], 0) + 1

    nodes = [{
        "id": a["id"],
        "label": a.get("main_kw") or a["url"].rstrip("/").split("/")[-1],
        "url": a["url"],
        "inbound": inbound.get(a["id"], 0),
        "outbound": outbound.get(a["id"], 0),
        "link_juice_score": a.get("link_juice_score", 0),
        "is_orphan": inbound.get(a["id"], 0) == 0,
    } for a in articles]
    edges = [{
        "from": l["from_article_id"], "to": l["to_article_id"],
        "label": l.get("anchor_text") or "", "type": "link"
    } for l in links if l["from_article_id"] in article_ids and l["to_article_id"] in article_ids]
    cluster_edges = [{
        "from": c["parent_article_id"], "to": c["child_article_id"],
        "confirmed": bool(c.get("confirmed")), "type": "cluster"
    } for c in clusters if c["parent_article_id"] in article_ids and c["child_article_id"] in article_ids]

    return {"nodes": nodes, "edges": edges, "cluster_edges": cluster_edges}


# ── Backwards compat（旧コードから呼ばれていた関数）────────────────────────

def init_db():
    """Supabase ではダッシュボードで SQL を実行するため何もしない"""
    pass
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
pytest tests/test_database.py -v
```

Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add database.py tests/test_database.py
git commit -m "feat: migrate database.py to supabase-py with pagination"
```

---

## Task 7: `discovery.py` を実装（TDD）

**Files:**
- Create: `discovery.py`
- Create: `tests/test_discovery.py`

- [ ] **Step 1: `tests/test_discovery.py` を作成**

```python
from unittest.mock import patch, MagicMock
import discovery


def test_extract_article_urls_filters_target_path(sample_sitemap_xml):
    urls = discovery.extract_article_urls(sample_sitemap_xml)
    assert "https://www.w2solution.co.jp/useful_info_ec/1001/" in urls
    assert "https://www.w2solution.co.jp/useful_info_ec/1002/" in urls
    assert "https://www.w2solution.co.jp/useful_info_ec/1003/" in urls
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
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_discovery.py -v
```

Expected: FAIL

- [ ] **Step 3: `discovery.py` を作成**

```python
import re
import requests
import database as db

SITEMAP_URL = "https://www.w2solution.co.jp/sitemap.xml"
TARGET_PATH = "/useful_info_ec/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; W2InternalLinkManager/1.0)",
    "Accept": "application/xml,text/xml,*/*",
}

_LOC_PATTERN = re.compile(r"<loc>(.*?)</loc>", re.IGNORECASE | re.DOTALL)


def fetch_sitemap(url: str = SITEMAP_URL) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


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


def discover_articles(sitemap_url: str = SITEMAP_URL) -> int:
    """サイトマップ取得 → URL 抽出 → DB に upsert"""
    try:
        xml = fetch_sitemap(sitemap_url)
    except requests.RequestException as e:
        print(f"[discovery] サイトマップ取得失敗: {e}")
        return 0
    urls = extract_article_urls(xml)
    for u in urls:
        db.upsert_article(u)
    return len(urls)
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
pytest tests/test_discovery.py -v
```

Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add discovery.py tests/test_discovery.py
git commit -m "feat: add sitemap-based article discovery with tests"
```

---

## Task 8: `crawler.py` を改修（404 検出・DELETE→INSERT）

**Files:**
- Modify: `crawler.py`

- [ ] **Step 1: `crawler.py` を全面置換**

```python
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
        absolute = urljoin(url, href)
        clean = _strip_query(absolute)
        if not _is_internal_article(clean) or clean == url or clean in seen:
            continue
        seen.add(clean)
        anchor = a.get_text(strip=True)[:200]
        to_id = db.upsert_article(clean)
        db.upsert_link(article_id, to_id, anchor)
        found_links.append({"url": clean, "anchor": anchor})

    db.set_crawled(article_id)
    return {"article_id": article_id, "url": url, "status": "active",
            "links_found": len(found_links), "links": found_links}
```

- [ ] **Step 2: コミット**

```bash
git add crawler.py
git commit -m "feat: crawler handles 404/error status, DELETE→INSERT links on recrawl"
```

---

## Task 9: `score_calculator.py` を実装（TDD）

**Files:**
- Create: `score_calculator.py`
- Create: `tests/test_score_calculator.py`

- [ ] **Step 1: `tests/test_score_calculator.py` を作成**

```python
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
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_score_calculator.py -v
```

Expected: FAIL

- [ ] **Step 3: `score_calculator.py` を作成**

```python
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
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
pytest tests/test_score_calculator.py -v
```

Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add score_calculator.py tests/test_score_calculator.py
git commit -m "feat: add simplified PageRank link-juice score calculator"
```

---

## Task 10: `csv_exporter.py` を実装（TDD）

**Files:**
- Create: `csv_exporter.py`
- Create: `tests/test_csv_exporter.py`

- [ ] **Step 1: `tests/test_csv_exporter.py` を作成**

```python
import io
import csv
import csv_exporter


def test_export_csv_has_required_columns():
    articles = [{
        "id": 1,
        "url": "https://www.w2solution.co.jp/useful_info_ec/1717/",
        "title": "テスト", "main_kw": "EC", "status": "active",
        "link_juice_score": 0.5, "inbound_count": 2, "outbound_count": 3,
    }]
    output = csv_exporter.to_csv_string(articles)
    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)
    assert rows[0]["url"] == "https://www.w2solution.co.jp/useful_info_ec/1717/"
    assert rows[0]["label"] == "/1717"
    assert rows[0]["title"] == "テスト"
    assert rows[0]["main_kw"] == "EC"
    assert rows[0]["status"] == "active"
    assert float(rows[0]["link_juice_score"]) == 0.5
    assert int(rows[0]["inbound_count"]) == 2
    assert int(rows[0]["outbound_count"]) == 3
    assert rows[0]["is_orphan"] == "false"


def test_orphan_flag_set_when_no_inbound():
    articles = [{
        "id": 1, "url": "https://www.w2solution.co.jp/useful_info_ec/1/",
        "title": "", "main_kw": "", "status": "active",
        "link_juice_score": 0, "inbound_count": 0, "outbound_count": 5,
    }]
    output = csv_exporter.to_csv_string(articles)
    rows = list(csv.DictReader(io.StringIO(output)))
    assert rows[0]["is_orphan"] == "true"


def test_csv_is_utf8_with_header():
    output = csv_exporter.to_csv_string([])
    # Header only
    assert "url,label,title,main_kw,status,link_juice_score,inbound_count,outbound_count,is_orphan" in output.split("\n")[0]
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_csv_exporter.py -v
```

Expected: FAIL

- [ ] **Step 3: `csv_exporter.py` を作成**

```python
import csv
import io
import os
from url_utils import short_label

COLUMNS = ["url", "label", "title", "main_kw", "status",
           "link_juice_score", "inbound_count", "outbound_count", "is_orphan"]


def to_csv_string(articles) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for a in articles:
        writer.writerow({
            "url": a.get("url", ""),
            "label": short_label(a.get("url", "")),
            "title": a.get("title") or "",
            "main_kw": a.get("main_kw") or "",
            "status": a.get("status") or "active",
            "link_juice_score": a.get("link_juice_score", 0),
            "inbound_count": a.get("inbound_count", 0),
            "outbound_count": a.get("outbound_count", 0),
            "is_orphan": "true" if (a.get("inbound_count", 0) == 0) else "false",
        })
    return buf.getvalue()


def write_csv_file(articles, output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    content = to_csv_string(articles)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return output_path
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
pytest tests/test_csv_exporter.py -v
```

Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add csv_exporter.py tests/test_csv_exporter.py
git commit -m "feat: add CSV exporter with /id label and orphan flag"
```

---

## Task 11: `slack_notifier.py` を実装（TDD）

**Files:**
- Create: `slack_notifier.py`
- Create: `tests/test_slack_notifier.py`

- [ ] **Step 1: `tests/test_slack_notifier.py` を作成**

```python
from unittest.mock import patch, MagicMock
import slack_notifier


def test_notify_skips_when_webhook_unset(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with patch("slack_notifier.requests.post") as mock_post:
        slack_notifier.notify_success({"articles_discovered": 10})
    mock_post.assert_not_called()


def test_notify_success_posts_to_webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST")
    with patch("slack_notifier.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        slack_notifier.notify_success({
            "articles_discovered": 215,
            "articles_crawled": 213,
            "links_found": 1842,
            "errors": 2,
            "orphan_count": 12,
            "orphan_delta": -6,
        })
    assert mock_post.called
    payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args.args[1]
    text = payload["text"] if isinstance(payload, dict) else str(payload)
    assert "クロール完了" in text or "✅" in text
    assert "215" in text
    assert "1842" in text or "1,842" in text


def test_notify_failure_includes_error(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST")
    with patch("slack_notifier.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        slack_notifier.notify_failure("接続エラー: timeout")
    payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args.args[1]
    text = payload["text"] if isinstance(payload, dict) else str(payload)
    assert "失敗" in text or "❌" in text
    assert "timeout" in text
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/test_slack_notifier.py -v
```

Expected: FAIL

- [ ] **Step 3: `slack_notifier.py` を作成**

```python
import os
import requests


def _webhook():
    return os.environ.get("SLACK_WEBHOOK_URL", "").strip()


def _post(text: str):
    url = _webhook()
    if not url:
        print(f"[slack] SLACK_WEBHOOK_URL 未設定。通知スキップ: {text[:80]}")
        return False
    try:
        resp = requests.post(url, json={"text": text}, timeout=10)
        return resp.status_code < 300
    except requests.RequestException as e:
        print(f"[slack] 通知失敗: {e}")
        return False


def notify_success(summary: dict) -> bool:
    delta = summary.get("orphan_delta")
    delta_str = ""
    if delta is not None:
        sign = "+" if delta > 0 else ""
        emoji = "🎉" if delta < 0 else ""
        delta_str = f"（前回比 {sign}{delta} {emoji}）"
    text = (
        "✅ 内部リンクの週次クロール完了\n"
        f"- 発見記事: {summary.get('articles_discovered', 0)}\n"
        f"- クロール成功: {summary.get('articles_crawled', 0)}\n"
        f"- リンク総数: {summary.get('links_found', 0)}\n"
        f"- エラー: {summary.get('errors', 0)}\n"
        f"- 孤立記事: {summary.get('orphan_count', 0)}{delta_str}"
    )
    return _post(text)


def notify_failure(error_message: str, run_url: str = "") -> bool:
    text = f"❌ 内部リンクの週次クロール失敗\n- エラー: {error_message[:500]}"
    if run_url:
        text += f"\n- ワークフロー: {run_url}"
    return _post(text)
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
pytest tests/test_slack_notifier.py -v
```

Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add slack_notifier.py tests/test_slack_notifier.py
git commit -m "feat: add Slack notifier for crawl success/failure"
```

---

## Task 12: `crawler_runner.py` を実装（オーケストレーター）

**Files:**
- Create: `crawler_runner.py`

- [ ] **Step 1: `crawler_runner.py` を作成**

```python
"""
内部リンクの一括クロールエントリーポイント。
GitHub Actions または手動から実行する。

実行手順:
  1. crawl_sessions レコード作成
  2. discovery でサイトマップから記事 URL を発見・upsert
  3. status='active' な記事を全件クロール
  4. PageRank 風スコアを計算して articles.link_juice_score を更新
  5. article_score_history にスナップショット保存
  6. CSV を output/ に出力
  7. crawl_sessions を完了に更新
  8. Slack に成功/失敗通知
"""
import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import database as db
import discovery
import crawler
import score_calculator
import csv_exporter
import slack_notifier


def _count_orphans(articles, links):
    article_ids = {a["id"] for a in articles}
    inbound = set()
    for l in links:
        if l["to_article_id"] in article_ids:
            inbound.add(l["to_article_id"])
    return sum(1 for a in articles if a["id"] not in inbound)


def main():
    triggered_by = os.environ.get("TRIGGERED_BY", "manual")
    session_id = db.create_crawl_session(triggered_by)
    print(f"[runner] crawl_session id={session_id} triggered_by={triggered_by}")

    discovered = 0
    crawled = 0
    errors = 0
    links_found_total = 0

    try:
        # 1. Discovery
        print("[runner] サイトマップから記事を発見中...")
        discovered = discovery.discover_articles()
        print(f"[runner] 発見: {discovered} 件")

        # 2. Crawl active articles
        all_articles = db.fetch_all("articles")
        active_articles = [a for a in all_articles if a.get("status") == "active"]
        total = len(active_articles)
        print(f"[runner] アクティブ記事数: {total}")

        for i, a in enumerate(active_articles, 1):
            print(f"[runner] [{i}/{total}] {a['url']}", flush=True)
            result = crawler.crawl_article(a["id"])
            if result.get("error"):
                errors += 1
                print(f"  -> エラー: {result.get('error')}")
            else:
                crawled += 1
                links_found_total += result.get("links_found", 0)

        # 3. Compute PageRank
        print("[runner] スコア計算中...")
        active_articles = [a for a in db.fetch_all("articles") if a.get("status") == "active"]
        all_links = db.fetch_all("links")
        scores = score_calculator.compute_pagerank(active_articles, all_links)
        inbound_counts = score_calculator.compute_inbound_counts(active_articles, all_links)

        for aid, score in scores.items():
            db.update_article_score(aid, score)

        # 4. Insert score history
        history_rows = [
            {"article_id": aid, "link_juice_score": scores[aid],
             "inbound_count": inbound_counts.get(aid, 0)}
            for aid in scores
        ]
        db.insert_score_history(session_id, history_rows)
        print(f"[runner] スコア履歴 {len(history_rows)} 件を保存")

        # 5. CSV export
        articles_with_counts = []
        for a in active_articles:
            articles_with_counts.append({
                **a,
                "link_juice_score": scores.get(a["id"], 0),
                "inbound_count": inbound_counts.get(a["id"], 0),
                "outbound_count": sum(1 for l in all_links if l["from_article_id"] == a["id"]),
            })
        out_path = f"output/articles_{session_id}.csv"
        csv_exporter.write_csv_file(articles_with_counts, out_path)
        print(f"[runner] CSV 出力: {out_path}")

        # 6. Complete session
        db.complete_crawl_session(session_id, discovered, crawled, links_found_total, errors)
        print("[runner] セッション完了")

        # 7. Notify Slack
        orphan_count = _count_orphans(active_articles, all_links)
        sessions = db.get_recent_sessions(limit=2)
        orphan_delta = None
        if len(sessions) >= 2:
            prev_history_res = db.get_client().table("article_score_history") \
                .select("inbound_count").eq("session_id", sessions[1]["id"]).execute()
            prev_orphans = sum(1 for r in (prev_history_res.data or []) if r.get("inbound_count") == 0)
            orphan_delta = orphan_count - prev_orphans

        slack_notifier.notify_success({
            "articles_discovered": discovered,
            "articles_crawled": crawled,
            "links_found": links_found_total,
            "errors": errors,
            "orphan_count": orphan_count,
            "orphan_delta": orphan_delta,
        })

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[runner] 失敗: {e}\n{tb}", file=sys.stderr)
        slack_notifier.notify_failure(f"{type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: コミット**

```bash
git add crawler_runner.py
git commit -m "feat: add crawler_runner orchestrator with score history and Slack"
```

---

## Task 13: `app.py` に新規エンドポイントを追加

**Files:**
- Modify: `app.py`

- [ ] **Step 1: `app.py` の末尾エンドポイント直前（`# ── Frontend` の前）に以下を追記**

```python
# ── Crawl Sessions ────────────────────────────────────────────────────────────

@app.get("/api/crawl-sessions")
def list_crawl_sessions():
    limit = int(request.args.get("limit", 10))
    return jsonify(db.get_recent_sessions(limit=limit))


# ── Score Diff (前週比較) ─────────────────────────────────────────────────────

@app.get("/api/score-diff")
def score_diff():
    current, previous, curr_rows, prev_rows = db.get_latest_two_sessions_scores()
    if not current:
        return jsonify({"error": "no crawl sessions yet"}), 404

    prev_by_aid = {r["article_id"]: r for r in prev_rows}
    articles = {a["id"]: a for a in db.fetch_all("articles") if a.get("status") == "active"}

    from url_utils import short_label
    diff_rows = []
    for r in curr_rows:
        aid = r["article_id"]
        if aid not in articles:
            continue
        a = articles[aid]
        prev = prev_by_aid.get(aid)
        prev_score = prev["link_juice_score"] if prev else None
        prev_inbound = prev["inbound_count"] if prev else None
        diff_rows.append({
            "article_id": aid,
            "url": a["url"],
            "label": short_label(a["url"]),
            "main_kw": a.get("main_kw"),
            "title": a.get("title"),
            "current_score": r["link_juice_score"],
            "previous_score": prev_score,
            "score_delta": (r["link_juice_score"] - prev_score) if prev_score is not None else None,
            "current_inbound": r["inbound_count"],
            "previous_inbound": prev_inbound,
            "inbound_delta": (r["inbound_count"] - prev_inbound) if prev_inbound is not None else None,
        })

    orphan_current = sum(1 for r in curr_rows if r["inbound_count"] == 0)
    orphan_previous = sum(1 for r in prev_rows if r["inbound_count"] == 0) if prev_rows else None

    return jsonify({
        "current_session": current,
        "previous_session": previous,
        "articles": diff_rows,
        "summary": {
            "orphan_count_current": orphan_current,
            "orphan_count_previous": orphan_previous,
            "orphan_delta": (orphan_current - orphan_previous) if orphan_previous is not None else None,
        }
    })


# ── CSV Export ────────────────────────────────────────────────────────────────

@app.get("/api/export.csv")
def export_csv():
    import csv_exporter
    articles = db.get_articles()
    csv_text = csv_exporter.to_csv_string(articles)
    from flask import Response
    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="articles.csv"'},
    )
```

- [ ] **Step 2: ローカルで起動確認**

```bash
cd C:\Users\wwahamaji\claude-workspace\internal-link-manager
workspace\.venv\Scripts\activate
# .env を作成（.env.example をコピーして埋める）
copy .env.example .env
# .env を編集して実値を設定
python app.py
```

別ターミナルで:
```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/crawl-sessions
```

Expected: 200 応答（crawl-sessions は空配列でも OK）。

- [ ] **Step 3: コミット**

```bash
git add app.py
git commit -m "feat: add /api/crawl-sessions, /api/score-diff, /api/export.csv"
```

---

## Task 14: フロントエンドに `/{id}` 短縮ラベル適用

**Files:**
- Create: `static/js/url-label.js`
- Modify: `templates/index.html`
- Modify: `static/js/app.js`

- [ ] **Step 1: `static/js/url-label.js` を作成**

```js
(function (global) {
  function shortLabel(url) {
    if (!url) return "";
    const m = url.match(/\/useful_info_ec\/(\d+)\/?/);
    return m ? "/" + m[1] : url;
  }
  global.shortLabel = shortLabel;
})(window);
```

- [ ] **Step 2: `templates/index.html` の `<head>` 内で `url-label.js` を `app.js` の前に読み込むよう追加**

```html
<script src="/static/js/url-label.js"></script>
```

`app.js` を読み込んでいる行（例：`<script src="/static/js/app.js"></script>`）の **直前** に挿入する。

- [ ] **Step 3: `static/js/app.js` 内で URL を表示しているすべての箇所を `shortLabel(url)` で置き換える**

該当箇所を grep で特定し、各箇所のテーブル描画ロジックで以下のように変更：

例（before）:
```js
td.textContent = article.url;
```

例（after）:
```js
const a = document.createElement("a");
a.href = article.url;
a.target = "_blank";
a.textContent = shortLabel(article.url);
td.appendChild(a);
```

vis.js のノードラベル生成も同様に：

例（before）:
```js
label: node.main_kw || node.url
```

例（after）:
```js
label: node.main_kw || shortLabel(node.url)
```

- [ ] **Step 4: ローカル起動して画面を確認**

```bash
python app.py
```

ブラウザで `http://localhost:5000` を開く。記事一覧の URL カラム、リンク一覧の from/to、グラフのノードラベルがすべて `/数字` 形式で表示されることを確認。

- [ ] **Step 5: コミット**

```bash
git add static/js/url-label.js templates/index.html static/js/app.js
git commit -m "feat: display URLs as /{id} short labels in frontend and graph"
```

---

## Task 15: GitHub Actions ワークフローを作成

**Files:**
- Create: `.github/workflows/weekly-crawl.yml`

- [ ] **Step 1: `.github/workflows/weekly-crawl.yml` を作成**

```yaml
name: Weekly Internal Link Crawl

on:
  schedule:
    - cron: '0 1 * * 1'   # 毎週月曜 10:00 JST (= 01:00 UTC)
  workflow_dispatch:

jobs:
  crawl:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run crawler
        run: python crawler_runner.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          TRIGGERED_BY: github_actions

      - name: Upload CSV artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: articles-csv
          path: output/*.csv
          if-no-files-found: ignore

      - name: Notify Slack on failure (保険)
        if: failure()
        run: |
          if [ -n "${{ secrets.SLACK_WEBHOOK_URL }}" ]; then
            curl -X POST -H 'Content-type: application/json' \
              --data "{\"text\":\"❌ Weekly Crawl ジョブが失敗しました: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}\"}" \
              "${{ secrets.SLACK_WEBHOOK_URL }}"
          fi
```

- [ ] **Step 2: コミット**

```bash
git add .github/workflows/weekly-crawl.yml
git commit -m "ci: add weekly crawl workflow with Slack failure notification"
```

- [ ] **Step 3: GitHub Secrets 登録手順をユーザに案内**

ユーザに以下を案内する：

```
GitHub リポジトリ > Settings > Secrets and variables > Actions > New repository secret
で 3 件を登録：

- SUPABASE_URL: https://tsuitsrwxkwawwqumpxj.supabase.co
- SUPABASE_SERVICE_ROLE_KEY: <ローカル credentials.json の supabase-service-role-key の値>
- SLACK_WEBHOOK_URL: <Slack の Incoming Webhook URL>

登録後、Actions > Weekly Internal Link Crawl > Run workflow で手動トリガーして
動作確認。
```

---

## Task 16: README を更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: `README.md` を全面置換**

````markdown
# 内部リンク管理ツール（Supabase 版）

W2 Solution `/useful_info_ec/*` 配下の記事の内部リンクを管理し、孤立記事・低リンクジュース記事を可視化するチーム共有ツール。

## 機能

| 機能 | 説明 |
|------|------|
| 記事自動発見 | サイトマップから全記事を自動取得 |
| 内部リンク管理 | 発リンク・被リンクの可視化と編集 |
| ネットワークグラフ | vis.js で記事間リンク関係を表示 |
| リンクジューススコア | 簡易 PageRank によるスコアを毎回更新 |
| 前週比較 | クロールごとの増減を表示 |
| 週次自動クロール | GitHub Actions が毎週月曜 10:00 JST に実行 |
| Slack 通知 | クロール完了・失敗を通知 |
| CSV エクスポート | AI 読み込み用に CSV を出力 |
| AI クラスター提案 | Claude AI が親子関係を提案 |
| AI リンク提案 | Claude AI が追加すべき内部リンクを提案 |

## セットアップ

### 1. Supabase スキーマを作成

Supabase ダッシュボード > SQL Editor で `supabase_schema.sql` を実行。

### 2. ローカル環境

```bash
python -m venv workspace\.venv
workspace\.venv\Scripts\activate
pip install -r requirements.txt

# .env を作成
copy .env.example .env
# .env を編集して SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 等を設定

python app.py
```

ブラウザで `http://localhost:5000` を開く。

### 3. 初回クロール

```bash
python crawler_runner.py
```

サイトマップから記事を発見し、全記事をクロールしてリンク関係を構築する。

### 4. GitHub Actions 設定

リポジトリの Settings > Secrets and variables > Actions に登録：

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SLACK_WEBHOOK_URL`

以降、毎週月曜 10:00 JST に自動でクロールが走る。

## テスト

```bash
pytest tests/ -v
```

外部依存（Supabase / Slack / 実サイト）はすべてモック化されており、ネットワーク不要で実行可能。

## データ

すべてのデータは Supabase に保存される。
- SQLite は使用しない（`data/links.db` は移行不要）
- `.env` は絶対にコミットしない

## アーキテクチャ

- `app.py`: Flask Web サーバー
- `database.py`: Supabase アクセス層
- `discovery.py`: サイトマップ解析
- `crawler.py`: 個別記事クロール
- `score_calculator.py`: PageRank 風スコア計算
- `crawler_runner.py`: 一括クロールエントリーポイント
- `slack_notifier.py` / `csv_exporter.py` / `url_utils.py`: ユーティリティ
- `.github/workflows/weekly-crawl.yml`: 週次 cron
````

- [ ] **Step 2: コミット**

```bash
git add README.md
git commit -m "docs: rewrite README for Supabase + GitHub Actions setup"
```

---

## Task 17: 全テストを実行して合格を確認

- [ ] **Step 1: 全テストを実行**

```bash
cd C:\Users\wwahamaji\claude-workspace\internal-link-manager
workspace\.venv\Scripts\activate
pytest tests/ -v
```

Expected: すべて green。失敗したものがあれば該当 Task に戻って修正。

- [ ] **Step 2: テスト結果の最終コミット（修正があった場合のみ）**

```bash
git add -A
git commit -m "test: fix test edge cases"
```

---

## Task 18: 初回エンドツーエンド実行で動作確認

- [ ] **Step 1: `.env` に実際の Supabase 接続情報を設定**

`internal-link-manager/.env` を編集：
```
SUPABASE_URL=https://tsuitsrwxkwawwqumpxj.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<credentials.json の supabase-service-role-key>
SLACK_WEBHOOK_URL=<任意、未設定でも動作可>
TRIGGERED_BY=manual
```

- [ ] **Step 2: `crawler_runner.py` を実行（実 Supabase に対して）**

```bash
python crawler_runner.py
```

Expected:
- `[runner] crawl_session id=1` のようなログ
- 発見記事数が ~200 件前後
- スコア計算完了
- `output/articles_1.csv` が生成される
- Supabase ダッシュボード > Table Editor で `articles` / `links` / `crawl_sessions` / `article_score_history` にレコードが入っている

- [ ] **Step 3: Flask アプリを起動して画面確認**

```bash
python app.py
```

ブラウザで以下を確認：
- 記事一覧に `/1717` のような短縮ラベル表示
- ネットワークグラフが描画される
- `/api/crawl-sessions` がセッション 1 件を返す
- `/api/export.csv` が CSV をダウンロードできる

- [ ] **Step 4: 動作確認の結果をユーザに報告**

問題なければ Task 完了。問題があれば該当箇所を修正して再実行。
