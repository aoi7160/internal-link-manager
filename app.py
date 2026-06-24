import os
import sys
import threading
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

import database as db
import crawler
import ai_cluster
import ai_links
import ai_article_link_suggester

app = Flask(__name__)
CORS(app)

db.init_db()

_crawl_status = {"running": False, "total": 0, "done": 0, "errors": 0, "current_url": ""}


# ── Articles ──────────────────────────────────────────────────────────────────

@app.get("/api/articles")
def list_articles():
    return jsonify(db.get_articles())


@app.post("/api/articles")
def create_article():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    article_id = db.upsert_article(url, main_kw=data.get("main_kw"), title=data.get("title"))
    return jsonify({"id": article_id}), 201


@app.put("/api/articles/<int:article_id>")
def update_article(article_id):
    data = request.json or {}
    db.update_article(article_id, main_kw=data.get("main_kw"), title=data.get("title"), tags=data.get("tags"))
    return jsonify({"ok": True})


@app.delete("/api/articles/<int:article_id>")
def delete_article(article_id):
    db.delete_article(article_id)
    return jsonify({"ok": True})


@app.get("/api/articles/<int:article_id>/links")
def article_links(article_id):
    return jsonify(db.get_links_for_article(article_id))


# ── Links ─────────────────────────────────────────────────────────────────────

@app.get("/api/links")
def list_links():
    return jsonify(db.get_links())


@app.post("/api/links")
def create_link():
    data = request.json or {}
    from_id = data.get("from_article_id")
    to_id = data.get("to_article_id")
    if not from_id or not to_id:
        return jsonify({"error": "from_article_id and to_article_id are required"}), 400
    db.upsert_link(int(from_id), int(to_id), data.get("anchor_text"))
    return jsonify({"ok": True}), 201


@app.delete("/api/links/<int:link_id>")
def delete_link(link_id):
    db.delete_link(link_id)
    return jsonify({"ok": True})


# ── Crawl ─────────────────────────────────────────────────────────────────────

@app.post("/api/crawl/<int:article_id>")
def crawl_single(article_id):
    result = crawler.crawl_article(article_id)
    return jsonify(result)


@app.post("/api/crawl/all")
def crawl_all():
    if _crawl_status["running"]:
        return jsonify({"message": "Already running", "status": _crawl_status})

    articles = db.get_articles()

    def run():
        _crawl_status.update({"running": True, "total": len(articles), "done": 0, "errors": 0, "current_url": ""})
        for a in articles:
            _crawl_status["current_url"] = a["url"]
            result = crawler.crawl_article(a["id"])
            if result.get("error"):
                _crawl_status["errors"] += 1
            _crawl_status["done"] += 1
        _crawl_status["running"] = False
        _crawl_status["current_url"] = ""

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return jsonify({"message": f"Crawling {len(articles)} articles in background", "total": len(articles)})


@app.get("/api/crawl/status")
def crawl_status():
    return jsonify(_crawl_status)


# ── Clusters ──────────────────────────────────────────────────────────────────

@app.get("/api/clusters")
def list_clusters():
    return jsonify(db.get_clusters())


@app.post("/api/clusters")
def create_cluster():
    data = request.json or {}
    parent_id = data.get("parent_article_id")
    child_id = data.get("child_article_id")
    if not parent_id or not child_id:
        return jsonify({"error": "parent_article_id and child_article_id are required"}), 400
    db.upsert_cluster(
        int(parent_id),
        int(child_id),
        reason=data.get("reason", ""),
        ai_suggested=False,
        confirmed=True,
    )
    return jsonify({"ok": True}), 201


@app.patch("/api/clusters/<int:cluster_id>")
def update_cluster(cluster_id):
    data = request.json or {}
    confirmed = data.get("confirmed")
    if confirmed is not None:
        db.confirm_cluster(cluster_id, bool(confirmed))
    return jsonify({"ok": True})


@app.delete("/api/clusters/<int:cluster_id>")
def delete_cluster(cluster_id):
    db.delete_cluster(cluster_id)
    return jsonify({"ok": True})


@app.post("/api/ai/suggest-clusters")
def ai_suggest():
    data = request.json or {}
    article_ids = data.get("article_ids")
    try:
        suggestions = ai_cluster.suggest_clusters(article_ids)
        return jsonify({"suggestions": suggestions, "count": len(suggestions)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/ai/suggest-article-links")
def ai_suggest_article_links():
    data = request.json or {}
    title = data.get("title", "").strip()
    body = data.get("body", "").strip()
    if not body:
        return jsonify({"error": "body is required"}), 400
    try:
        result = ai_article_link_suggester.suggest_article_links(title, body)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/ai/suggest-links")
def ai_suggest_links():
    data = request.json or {}
    article_ids = data.get("article_ids")
    try:
        suggestions = ai_links.suggest_links(article_ids)
        return jsonify({"suggestions": suggestions, "count": len(suggestions)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/link-suggestions")
def list_link_suggestions():
    return jsonify(db.get_link_suggestions())


@app.post("/api/link-suggestions/<int:suggestion_id>/confirm")
def confirm_link_suggestion(suggestion_id):
    db.confirm_link_suggestion(suggestion_id)
    return jsonify({"ok": True})


@app.delete("/api/link-suggestions/<int:suggestion_id>")
def delete_link_suggestion(suggestion_id):
    db.delete_link_suggestion(suggestion_id)
    return jsonify({"ok": True})


# ── Graph ─────────────────────────────────────────────────────────────────────

@app.get("/api/graph")
def graph_data():
    return jsonify(db.get_graph_data())


# ── Settings / Health ─────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/settings")
def get_settings():
    return jsonify({
        "anthropic_api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


@app.post("/api/settings")
def post_settings():
    data = request.json or {}
    key = data.get("anthropic_api_key", "").strip()
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key
    return jsonify({"ok": True})


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


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Internal Link Manager on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
