"""
AI provider abstraction.
- AI_PROVIDER=openrouter  →  OpenRouter（無料モデル / Render用）
- AI_PROVIDER=gemini      →  Google Gemini
- それ以外（デフォルト）  →  Anthropic Claude（ローカル開発）
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

    if provider == "openrouter":
        import requests
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY が設定されていません")
        model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-lite-001")
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://internal-link-manager.onrender.com",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        if not resp.ok:
            raise ValueError(f"OpenRouter error {resp.status_code}: {resp.text}")
        return resp.json()["choices"][0]["message"]["content"].strip()

    elif provider == "gemini":
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY が設定されていません")
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
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
