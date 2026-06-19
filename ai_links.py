import os
import json
import anthropic
import database as db

MODEL = "claude-opus-4-8"


def suggest_links(article_ids: list[int] | None = None) -> list[dict]:
    """
    Claude が記事のキーワードを分析し、
    「この記事 → この記事にリンクすべき（アンカーテキスト付き）」を提案する。
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
        f'- id={a["id"]}, kw="{a["main_kw"] or "(未設定)"}"'
        for a in articles
    )

    prompt = f"""あなたはECサイト向けSEOの内部リンク戦略の専門家です。
以下はECに関するSEO記事の一覧です（id, メインKW）。

{article_list}

各記事のメインKWを分析し、「記事AはそのコンテンツとしてKWの関連性から記事Bに内部リンクを貼るべきだ」という組み合わせを提案してください。

ルール：
- 読者が記事Aを読んでいるときに、記事Bへのリンクが自然に役立つ場合のみ提案する
- KWの関連性・補完関係が明確なもののみ
- 1記事から複数のリンク先を提案してよい
- 1記事あたり最大5件まで
- アンカーテキストは自然な日本語で、リンク先KWを含む20文字以内
- 合計50〜80ペア程度を目安に

JSON配列で返してください。各要素：
{{"from_id": 数字, "to_id": 数字, "anchor_text": "アンカーテキスト", "reason": "理由（30文字以内）"}}

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

    suggestions = json.loads(raw)

    article_id_set = {a["id"] for a in articles}
    saved = []
    for s in suggestions:
        fid, tid = s.get("from_id"), s.get("to_id")
        if fid not in article_id_set or tid not in article_id_set:
            continue
        if fid == tid:
            continue
        anchor = s.get("anchor_text", "")
        reason = s.get("reason", "")
        db.upsert_link_suggestion(fid, tid, anchor=anchor, reason=reason)
        saved.append({"from_id": fid, "to_id": tid, "anchor_text": anchor, "reason": reason})

    return saved
