"""
AI provider abstraction.
- AI_PROVIDER=gemini  →  Google Gemini (Render / 無料運用)
- それ以外（デフォルト） →  Anthropic Claude (ローカル開発)
"""
import os
import json


def _strip_fences(raw: str) -> str:
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def call_ai(prompt: str, max_tokens: int = 8192) -> str:
    """プロンプトを送り、テキスト応答を返す。"""
    provider = os.environ.get("AI_PROVIDER", "claude").lower()

    if provider == "gemini":
        import google.generativeai as genai
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY が設定されていません")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens},
        )
        return response.text.strip()

    else:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY が設定されていません")
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()


def call_ai_json(prompt: str, max_tokens: int = 8192):
    """JSONを返すプロンプト用。コードフェンスを除去してパースして返す。"""
    raw = call_ai(prompt, max_tokens)
    return json.loads(_strip_fences(raw))
