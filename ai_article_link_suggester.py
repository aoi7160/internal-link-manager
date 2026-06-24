import os
import json
import anthropic
import database as db

MODEL = "claude-opus-4-8"


def get_target_link_range(char_count: int) -> tuple[int, int]:
    if char_count <= 3000:
        return (4, 6)
    elif char_count <= 6500:
        return (6, 8)
    else:
        return (10, 15)


def suggest_article_links(title: str, body: str) -> dict:
    """
    記事タイトルと本文を受け取り、挿入すべき内部リンクと
    そのまま使える紹介文を提案する。DBへの保存は行わない。
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)

    char_count = len(body)
    min_links, max_links = get_target_link_range(char_count)
    target_range = f"{min_links}〜{max_links}"

    articles = db.get_articles()
    if not articles:
        return {
            "char_count": char_count,
            "target_range": target_range,
            "detected_parent_articles": [],
            "suggestions": [],
        }

    clusters = db.get_clusters()
    confirmed_clusters = [c for c in clusters if c.get("confirmed")]

    article_list = "\n".join(
        f'- id={a["id"]}, title="{a.get("title") or "(タイトルなし)"}", kw="{a.get("main_kw") or "(未設定)"}", url="{a["url"]}"'
        for a in articles
    )

    cluster_list = "\n".join(
        f'- 親id={c["parent_id"]}({c.get("parent_kw") or "?"}) → 子id={c["child_id"]}({c.get("child_kw") or "?"})'
        for c in confirmed_clusters
    ) or "（クラスター関係なし）"

    prompt = f"""あなたはECサイト向けSEOの内部リンク戦略の専門家です。

## 対象記事
タイトル：{title}

本文：
{body}

---

## サイト内記事一覧（id, タイトル, メインKW, URL）
{article_list}

---

## トピッククラスター親子関係（確認済みのみ）
{cluster_list}

---

## タスク
上記の対象記事に追加すべき内部リンクを{min_links}〜{max_links}個提案してください。

### ルール
1. トピッククラスターで「対象記事が子記事」の場合、その親記事は必ず「priority: 必須」としてリード文（1〜2段落目）への配置を提案してください
2. クラスター関係のある記事を最優先に選ぶ
3. 次に、本文の内容と関連性が高い記事を選ぶ
4. 合計{min_links}〜{max_links}個になるよう調整する

### 出力フォーマット
各提案の formatted_text は以下の2パターンのどちらかを使ってください：

【パターンA：通常リンク（記事本文中に挿入）】
以下の記事では〇〇について詳しく解説しています。
ぜひ合わせてご覧ください。

【記事タイトル】

または

関連記事：記事タイトル

【パターンB：リード文の親記事リンク（子記事でのみ使用）】
なお、〇〇に関する詳細は下記で詳しく解説しているので合わせて一読ください。

関連記事：記事タイトル

---

JSON形式で返してください：
{{
  "detected_parent_articles": [
    {{"article_id": 数字, "title": "タイトル", "url": "URL", "reason": "親記事と判断した理由"}}
  ],
  "suggestions": [
    {{
      "priority": "必須" または "推奨",
      "placement": "挿入箇所の説明（例：リード文（1〜2段落目）、〇〇の説明後、まとめ前など）",
      "article_id": 数字,
      "url": "URL",
      "title": "記事タイトル",
      "formatted_text": "そのままコピーして使えるリンク紹介文",
      "reason": "この記事を選んだ理由（30文字以内）"
    }}
  ]
}}

JSONのみ返し、説明文は不要です。"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)

    return {
        "char_count": char_count,
        "target_range": target_range,
        "detected_parent_articles": result.get("detected_parent_articles", []),
        "suggestions": result.get("suggestions", []),
    }
