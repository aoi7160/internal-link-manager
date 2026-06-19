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
