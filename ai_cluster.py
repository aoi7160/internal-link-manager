import os
import json
import anthropic
import database as db

MODEL = "claude-sonnet-4-6"


def suggest_clusters(article_ids: list[int] | None = None) -> list[dict]:
    """
    Call Claude to suggest parent-child topic cluster relationships.
    Returns a list of {parent_id, child_id, reason} dicts.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)

    articles = db.get_articles()
    if article_ids:
        articles = [a for a in articles if a["id"] in article_ids]

    if len(articles) < 2:
        return []

    article_list = "\n".join(
        f'- id={a["id"]}, kw="{a["main_kw"] or "(未設定)"}", url={a["url"]}'
        for a in articles
    )

    prompt = f"""あなたはSEOのトピッククラスター専門家です。
以下はECに関するSEO記事の一覧です（id, メインKW, URL）。

{article_list}

各記事のメインKWを分析し、「この記事（親）がより広いトピックを扱っており、別の記事（子）はその下位・詳細トピックを扱っている」という親子関係を提案してください。

ルール：
- 1記事は複数の子を持てる
- 明確なKWの包含関係・トピック階層がある場合のみ提案する
- 同じカテゴリ（例：D2C）内の概論記事が親、事例・業種別記事が子になる
- 30〜50ペア程度を目安に提案する（多すぎず少なすぎず）

JSON配列で返してください。各要素は以下の形式：
{{"parent_id": 数字, "child_id": 数字, "reason": "理由（日本語、50文字以内）"}}

JSONのみ返し、説明文は不要です。"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    suggestions = json.loads(raw)

    # Persist to DB as unconfirmed AI suggestions
    article_id_set = {a["id"] for a in articles}
    saved = []
    for s in suggestions:
        pid, cid = s.get("parent_id"), s.get("child_id")
        if pid not in article_id_set or cid not in article_id_set:
            continue
        if pid == cid:
            continue
        reason = s.get("reason", "")
        db.upsert_cluster(pid, cid, reason=reason, ai_suggested=True, confirmed=False)
        saved.append({"parent_id": pid, "child_id": cid, "reason": reason})

    return saved
