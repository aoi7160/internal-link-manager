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
