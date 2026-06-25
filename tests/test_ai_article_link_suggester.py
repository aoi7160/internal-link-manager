import json
import pytest
from unittest.mock import MagicMock, patch
import ai_article_link_suggester as suggester


# ── get_target_link_range ──────────────────────────────────────────────────────

def test_link_range_short_article():
    assert suggester.get_target_link_range(1000) == (4, 6)

def test_link_range_at_boundary_3000():
    assert suggester.get_target_link_range(3000) == (4, 6)

def test_link_range_medium_article():
    assert suggester.get_target_link_range(5000) == (6, 8)

def test_link_range_at_boundary_6500():
    assert suggester.get_target_link_range(6500) == (6, 8)

def test_link_range_long_article():
    assert suggester.get_target_link_range(8000) == (10, 15)

def test_link_range_very_long_article():
    assert suggester.get_target_link_range(15000) == (10, 15)

def test_link_range_just_over_3000():
    assert suggester.get_target_link_range(3001) == (6, 8)

def test_link_range_just_over_6500():
    assert suggester.get_target_link_range(6501) == (10, 15)


# ── suggest_article_links ──────────────────────────────────────────────────────

SAMPLE_ARTICLES = [
    {"id": 1, "url": "https://www.w2solution.co.jp/useful_info_ec/1001/",
     "main_kw": "ECサイト構築", "title": "ECサイト構築入門", "inbound_count": 3, "outbound_count": 2},
    {"id": 2, "url": "https://www.w2solution.co.jp/useful_info_ec/1002/",
     "main_kw": "EC集客", "title": "EC集客16選", "inbound_count": 1, "outbound_count": 0},
    {"id": 3, "url": "https://www.w2solution.co.jp/useful_info_ec/1003/",
     "main_kw": "オムニチャネル", "title": "オムニチャネル完全解説", "inbound_count": 0, "outbound_count": 0},
]

SAMPLE_CLUSTERS = [
    {"parent_id": 1, "parent_url": "https://www.w2solution.co.jp/useful_info_ec/1001/",
     "parent_kw": "ECサイト構築",
     "child_id": 3, "child_url": "https://www.w2solution.co.jp/useful_info_ec/1003/",
     "child_kw": "オムニチャネル",
     "reason": "ECサイト構築の一部", "ai_suggested": False, "confirmed": True},
]

CLAUDE_RESPONSE = {
    "detected_parent_articles": [
        {"article_id": 1, "title": "ECサイト構築入門",
         "url": "https://www.w2solution.co.jp/useful_info_ec/1001/",
         "reason": "オムニチャネルの親記事"}
    ],
    "suggestions": [
        {
            "priority": "必須",
            "placement": "リード文（1〜2段落目）",
            "article_id": 1,
            "url": "https://www.w2solution.co.jp/useful_info_ec/1001/",
            "title": "ECサイト構築入門",
            "formatted_text": "なお、ECサイト構築に関する詳細は下記で詳しく解説しているので合わせて一読ください。\n\n関連記事：ECサイト構築入門",
            "reason": "クラスター親記事"
        },
        {
            "priority": "推奨",
            "placement": "本文中盤",
            "article_id": 2,
            "url": "https://www.w2solution.co.jp/useful_info_ec/1002/",
            "title": "EC集客16選",
            "formatted_text": "以下の記事ではEC集客について詳しく解説しています。\nぜひ合わせてご覧ください。\n\nEC集客16選",
            "reason": "集客との関連性"
        },
    ]
}


def make_mock_message(response_dict: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(response_dict))]
    return msg


def test_suggest_article_links_returns_structured_result():
    body = "a" * 5000
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("ai_article_link_suggester.db.get_articles", return_value=SAMPLE_ARTICLES), \
         patch("ai_article_link_suggester.db.get_clusters", return_value=SAMPLE_CLUSTERS), \
         patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_mock_message(CLAUDE_RESPONSE)

        result = suggester.suggest_article_links("オムニチャネル完全解説", body)

    assert result["char_count"] == len(body)
    assert result["target_range"] == "6〜8"
    assert len(result["suggestions"]) == 2
    assert result["suggestions"][0]["priority"] == "必須"
    assert len(result["detected_parent_articles"]) == 1


def test_suggest_article_links_short_article():
    body = "a" * 2000
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("ai_article_link_suggester.db.get_articles", return_value=SAMPLE_ARTICLES), \
         patch("ai_article_link_suggester.db.get_clusters", return_value=SAMPLE_CLUSTERS), \
         patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_mock_message(CLAUDE_RESPONSE)

        result = suggester.suggest_article_links("短い記事", body)

    assert result["target_range"] == "4〜6"
    assert result["char_count"] == 2000


def test_suggest_article_links_long_article():
    body = "a" * 9000
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("ai_article_link_suggester.db.get_articles", return_value=SAMPLE_ARTICLES), \
         patch("ai_article_link_suggester.db.get_clusters", return_value=SAMPLE_CLUSTERS), \
         patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_mock_message(CLAUDE_RESPONSE)

        result = suggester.suggest_article_links("長い記事", body)

    assert result["target_range"] == "10〜15"


def test_suggest_article_links_no_articles_returns_empty():
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("ai_article_link_suggester.db.get_articles", return_value=[]), \
         patch("ai_article_link_suggester.db.get_clusters", return_value=[]):

        result = suggester.suggest_article_links("タイトル", "本文テキスト")

    assert result["suggestions"] == []
    assert result["detected_parent_articles"] == []


def test_suggest_article_links_no_api_key_raises():
    with patch.dict("os.environ", {}, clear=True), \
         patch("ai_article_link_suggester.db.get_articles", return_value=SAMPLE_ARTICLES), \
         patch("ai_article_link_suggester.db.get_clusters", return_value=SAMPLE_CLUSTERS):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            suggester.suggest_article_links("タイトル", "本文")


def test_suggest_article_links_gemini_no_api_key_raises():
    with patch.dict("os.environ", {"AI_PROVIDER": "gemini"}, clear=True), \
         patch("ai_article_link_suggester.db.get_articles", return_value=SAMPLE_ARTICLES), \
         patch("ai_article_link_suggester.db.get_clusters", return_value=SAMPLE_CLUSTERS):
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            suggester.suggest_article_links("タイトル", "本文")


def test_suggest_article_links_handles_markdown_json_response():
    """ClaudeがMarkdownコードブロックで返してきた場合も正しくパースできる"""
    body = "a" * 5000
    md_response = f"```json\n{json.dumps(CLAUDE_RESPONSE)}\n```"

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("ai_article_link_suggester.db.get_articles", return_value=SAMPLE_ARTICLES), \
         patch("ai_article_link_suggester.db.get_clusters", return_value=SAMPLE_CLUSTERS), \
         patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        msg = MagicMock()
        msg.content = [MagicMock(text=md_response)]
        mock_client.messages.create.return_value = msg

        result = suggester.suggest_article_links("タイトル", body)

    assert len(result["suggestions"]) == 2


def test_suggest_article_links_only_unconfirmed_clusters_excluded():
    """未確認クラスターは除外され、確認済みのみ使われる"""
    unconfirmed_clusters = [
        {**SAMPLE_CLUSTERS[0], "confirmed": False}
    ]
    body = "a" * 5000
    call_args_captured = {}

    def capture_create(**kwargs):
        call_args_captured["prompt"] = kwargs["messages"][0]["content"]
        return make_mock_message({"detected_parent_articles": [], "suggestions": []})

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
         patch("ai_article_link_suggester.db.get_articles", return_value=SAMPLE_ARTICLES), \
         patch("ai_article_link_suggester.db.get_clusters", return_value=unconfirmed_clusters), \
         patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = capture_create

        suggester.suggest_article_links("タイトル", body)

    assert "クラスター関係なし" in call_args_captured.get("prompt", "")


# ── API endpoint integration test ──────────────────────────────────────────────

def test_api_endpoint_suggest_article_links(monkeypatch):
    import app as flask_app
    flask_app.app.config["TESTING"] = True
    client = flask_app.app.test_client()

    mock_result = {
        "char_count": 4000,
        "target_range": "6〜8",
        "detected_parent_articles": [],
        "suggestions": [
            {
                "priority": "推奨",
                "placement": "本文中",
                "article_id": 1,
                "url": "https://www.w2solution.co.jp/useful_info_ec/1001/",
                "title": "テスト記事",
                "formatted_text": "関連記事：テスト記事",
                "reason": "関連性あり"
            }
        ]
    }

    with patch("ai_article_link_suggester.suggest_article_links", return_value=mock_result):
        resp = client.post(
            "/api/ai/suggest-article-links",
            json={"title": "テスト", "body": "a" * 4000},
            content_type="application/json"
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["char_count"] == 4000
    assert data["target_range"] == "6〜8"
    assert len(data["suggestions"]) == 1


def test_api_endpoint_missing_body_returns_400():
    import app as flask_app
    flask_app.app.config["TESTING"] = True
    client = flask_app.app.test_client()

    resp = client.post(
        "/api/ai/suggest-article-links",
        json={"title": "テスト"},
        content_type="application/json"
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_endpoint_ai_error_returns_500():
    import app as flask_app
    flask_app.app.config["TESTING"] = True
    client = flask_app.app.test_client()

    with patch("ai_article_link_suggester.suggest_article_links", side_effect=Exception("API失敗")):
        resp = client.post(
            "/api/ai/suggest-article-links",
            json={"title": "テスト", "body": "本文テキスト"},
            content_type="application/json"
        )

    assert resp.status_code == 500
    assert "error" in resp.get_json()
