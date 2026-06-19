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
