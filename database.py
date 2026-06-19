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

    from url_utils import short_label
    nodes = [{
        "id": a["id"],
        "label": a.get("main_kw") or short_label(a["url"]),
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
