"""
全記事の内部リンクを一括クロールするスクリプト
使い方: python bulk_crawl.py
"""
import sys
import time
import database as db
import crawler as c

def main():
    print("=== 内部リンク 一括クロール ===")
    print()

    db.init_db()
    articles = db.get_articles()
    total = len(articles)
    print(f"対象記事数: {total} 件")
    print("クロール開始します... (Ctrl+C で中断できます)")
    print()

    done = 0
    errors = 0

    for art in articles:
        done += 1
        url_short = art["url"].replace("https://www.w2solution.co.jp/useful_info_ec/", ".../")
        print(f"[{done}/{total}] {url_short}", end=" ... ", flush=True)

        result = c.crawl_article(art["id"])

        if result.get("error"):
            print(f"エラー: {result['error']}")
            errors += 1
        else:
            found = result.get("links_found", 0)
            print(f"発内部リンク {found} 件")

    print()
    print("=" * 40)
    print(f"完了！ {done} 記事クロール / エラー {errors} 件")
    print("ブラウザで http://localhost:5000 をリロードしてください")

if __name__ == "__main__":
    main()
