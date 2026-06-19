# 内部リンク管理ツール Supabase 移行設計書

日付: 2026-06-19  
対象プロジェクト: `claude-workspace/internal-link-manager`  
ステータス: 確定

---

## 1. 概要

W2 Solution の `/useful_info_ec/*` 配下の記事間内部リンクを完全管理するツールを、SQLite ローカル DB から Supabase（PostgreSQL クラウド DB）に移行し、週次自動クロールを GitHub Actions で実現する。

**主要ゴール:**
- チームで同一データを共有（Supabase）
- 全記事の自動発見（サイトマップ解析）
- 週次クロールの完全自動化（GitHub Actions）
- 孤立記事・低リンクジュース記事のビジュアル可視化
- 前週比較で SEO 改善を継続的にモニタリング
- Slack 通知でクロール結果・失敗を即時把握
- CSV エクスポートで AI 分析を容易に

---

## 2. アーキテクチャ

```
┌─────────────────────────────────────┐
│  チームメンバーのPC                    │
│  Flask + supabase-py（ローカル起動）   │
│  http://localhost:5000               │
│  認証情報は各自の .env で管理          │
└──────────────┬──────────────────────┘
               │ 読み書き（supabase-py）
               ▼
┌─────────────────────────────────────┐
│  Supabase（クラウド）                 │
│  PostgreSQL DB（チーム共有）          │
│  Project: tsuitsrwxkwawwqumpxj      │
│  RLS なし・ログイン認証なし            │
└──────────────▲──────────────────────┘
               │ 週次書き込み
┌──────────────┴──────────────────────┐
│  GitHub Actions                      │
│  schedule: 毎週月曜 10:00 JST        │
│  python crawler_runner.py            │
│  Secrets: SUPABASE_URL /             │
│           SERVICE_ROLE_KEY /         │
│           SLACK_WEBHOOK_URL          │
│  → Slack に成功/失敗を通知            │
└─────────────────────────────────────┘
```

**認証情報の運用方針:**
- RLS・ログイン認証は導入しない（チーム内ツールのため）
- `service_role` キー：GitHub Actions 専用（Secrets に登録）
- チームメンバーのローカル：各自の `.env`（`.gitignore` 済み）にキーを置く
- キー配布：Slack DM など安全な経路で配布
- `.env` は絶対にコミットしない

---

## 3. データベーススキーマ（Supabase / PostgreSQL）

### 既存テーブル（SQLite から移行）

```sql
CREATE TABLE articles (
  id               BIGSERIAL PRIMARY KEY,
  url              TEXT UNIQUE NOT NULL,
  main_kw          TEXT,
  title            TEXT,
  crawled_at       TIMESTAMPTZ,
  link_juice_score FLOAT DEFAULT 0,
  status           TEXT DEFAULT 'active',  -- 'active' | '404' | 'error'
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE links (
  id              BIGSERIAL PRIMARY KEY,
  from_article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  to_article_id   BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  anchor_text     TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(from_article_id, to_article_id)
);

CREATE TABLE clusters (
  id                BIGSERIAL PRIMARY KEY,
  parent_article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  child_article_id  BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  reason            TEXT,
  ai_suggested      BOOLEAN DEFAULT FALSE,
  confirmed         BOOLEAN DEFAULT FALSE,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(parent_article_id, child_article_id)
);

CREATE TABLE link_suggestions (
  id              BIGSERIAL PRIMARY KEY,
  from_article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  to_article_id   BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  anchor_text     TEXT,
  reason          TEXT,
  confirmed       BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(from_article_id, to_article_id)
);

CREATE TABLE article_keywords (
  id         BIGSERIAL PRIMARY KEY,
  article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  keyword    TEXT NOT NULL
);
```

### 新規テーブル

```sql
CREATE TABLE crawl_sessions (
  id                  BIGSERIAL PRIMARY KEY,
  started_at          TIMESTAMPTZ DEFAULT NOW(),
  completed_at        TIMESTAMPTZ,
  articles_discovered INT DEFAULT 0,
  articles_crawled    INT DEFAULT 0,
  links_found         INT DEFAULT 0,
  errors              INT DEFAULT 0,
  triggered_by        TEXT  -- 'manual' | 'github_actions'
);

CREATE TABLE article_score_history (
  id               BIGSERIAL PRIMARY KEY,
  article_id       BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  session_id       BIGINT REFERENCES crawl_sessions(id) ON DELETE CASCADE,
  link_juice_score FLOAT,
  inbound_count    INT,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. ファイル変更一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `database.py` | 全面置換 | SQLite → supabase-py、`status` 対応、ページネーション関数追加 |
| `crawler.py` | 改修 | 404 検出時に `status='404'` に更新、リンク再投入は DELETE → INSERT |
| `discovery.py` | 新規作成 | サイトマップ解析（ネスト sitemap は対象外） |
| `crawler_runner.py` | 新規作成 | 発見→クロール→スコア計算→履歴保存→Slack 通知→CSV 出力 |
| `score_calculator.py` | 新規作成 | 簡易 PageRank、ページネーションで全件取得 |
| `slack_notifier.py` | 新規作成 | Slack Incoming Webhook 通知 |
| `csv_exporter.py` | 新規作成 | CSV 出力（API 共通利用） |
| `url_utils.py` | 新規作成 | `/useful_info_ec/(\d+)/` → `/{id}` 短縮ラベル変換ヘルパー |
| `app.py` | 追加 | `/api/crawl-sessions` `/api/score-diff` `/api/export.csv` 追加、`/api/graph` で `url_utils` 適用 |
| `requirements.txt` | 改修 | `supabase>=2.0.0` 追加、`psycopg2-binary` 削除 |
| `.github/workflows/weekly-crawl.yml` | 新規作成 | 週次 Actions cron、失敗時 Slack 通知 |
| `.env.example` | 新規作成 | `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` / `SLACK_WEBHOOK_URL` / `ANTHROPIC_API_KEY` |
| `supabase_schema.sql` | 新規作成 | DB 初期化 SQL（Supabase ダッシュボードで実行） |
| `static/js/url-label.js` | 新規作成 | フロント側の URL → `/{id}` 変換 |
| `templates/index.html` | 改修 | `url-label.js` 読み込み、表示部で短縮ラベル適用 |
| `static/js/app.js` | 改修 | 記事一覧・リンク一覧で短縮ラベル適用 |
| `tests/test_url_utils.py` | 新規作成 | URL → 短縮ラベル変換の単体テスト |
| `tests/test_discovery.py` | 新規作成 | サイトマップ解析の単体テスト（モック HTML） |
| `tests/test_database.py` | 新規作成 | supabase-py をモック化して DB ロジック検証 |
| `tests/test_score_calculator.py` | 新規作成 | ページネーション + PageRank の単体テスト |
| `tests/test_csv_exporter.py` | 新規作成 | CSV 出力の単体テスト |
| `tests/test_slack_notifier.py` | 新規作成 | Slack 通知の単体テスト（requests をモック化） |
| `tests/conftest.py` | 新規作成 | 共通フィクスチャ（モック supabase クライアント） |

---

## 5. クロールフロー

```
crawler_runner.py 起動（手動 or GitHub Actions）
        │
        ▼
1. crawl_sessions にレコード作成（triggered_by を記録）
        │
        ▼
2. discovery.py：全記事 URL を自動発見
   ├─ https://www.w2solution.co.jp/sitemap.xml を取得
   ├─ /useful_info_ec/* にマッチする URL を抽出
   └─ DB に未登録の URL を articles に upsert（status='active'）
        │
        ▼
3. crawler.py：全記事をクロール（1.5秒間隔）
   ├─ 各記事の HTML を取得
   ├─ 200 OK：タイトル取得・更新、status='active' 確認
   ├─ 404：articles.status='404' に更新、リンク抽出スキップ
   ├─ その他エラー：articles.status='error' に更新、errors++
   ├─ links の更新：その記事の既存 from リンクを DELETE → 新規 INSERT
   └─ 他記事から本記事へのリンクは変更しない
        │
        ▼
4. score_calculator.py：link_juice_score を計算（status='active' のみ対象）
   ├─ articles と links を range() で全件ページネーション取得（1000 件超対応）
   ├─ 全記事のスコアを 1.0 で初期化
   ├─ score[i] = 0.15 + 0.85 × Σ(score[j] / out_count[j]) を 20 回反復
   ├─ 最大値で正規化（0〜1）
   └─ articles.link_juice_score を一括更新
        │
        ▼
5. article_score_history に当該セッションのスコアを一括 INSERT
   （article_id, session_id, link_juice_score, inbound_count）
        │
        ▼
6. csv_exporter.py：成果物 CSV を出力（GitHub Actions では artifact として保存）
        │
        ▼
7. crawl_sessions を完了に更新
   （completed_at, articles_discovered, articles_crawled, links_found, errors）
        │
        ▼
8. slack_notifier.py：Slack に完了サマリを通知
   （発見/クロール/リンク/エラー/孤立記事数、前回比、CSV 添付なし URL）
```

**失敗時の挙動：**
- ランナー内で try/except で全体を包む
- 例外発生時：`crawl_sessions.completed_at` は未設定のまま、Slack に失敗通知
- GitHub Actions の `if: failure()` ステップでも保険として Slack 通知

---

## 6. URL 表示ルール（短縮ラベル）

DB に保存する `articles.url` は **フル URL のまま**：  
`https://www.w2solution.co.jp/useful_info_ec/1717/`

表示・グラフラベルは **`/1717` 短縮形** を使用。

**ヘルパー関数（バックエンド：`url_utils.py`）：**

```python
import re
_PATTERN = re.compile(r"/useful_info_ec/(\d+)/?")

def short_label(url: str) -> str:
    m = _PATTERN.search(url or "")
    return f"/{m.group(1)}" if m else (url or "")
```

**フロントエンド（`static/js/url-label.js`）：**

```js
function shortLabel(url) {
  const m = (url || "").match(/\/useful_info_ec\/(\d+)\/?/);
  return m ? `/${m[1]}` : (url || "");
}
```

適用箇所：
- 記事一覧テーブル（URL カラム）
- リンク一覧テーブル（from / to カラム）
- vis.js グラフのノードラベル（`main_kw` がなければ短縮ラベル）
- CSV 出力の `label` カラム

リンクの **クリック先 / `href`** はフル URL のまま。

---

## 7. スコア計算のページネーション（重要）

supabase-py の `.select()` はデフォルト **最大 1000 行** で黙って打ち切られるため、`score_calculator.py` で `articles` と `links` を取得する際は **必ず `range()` でページネーション** して全件を取得する。

```python
def fetch_all(table_name: str, page_size: int = 1000):
    rows = []
    offset = 0
    while True:
        res = supabase.table(table_name).select("*").range(offset, offset + page_size - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows
```

**対象箇所：**
- `score_calculator.py` のスコア計算前のデータ取得
- `database.py` の `get_articles()` / `get_links()` / `get_graph_data()`
- `csv_exporter.py` の全件取得

---

## 8. 前週比較 API（`/api/score-diff`）

最新 2 セッション（最新と前回）の `article_score_history` を JOIN して差分を返す。

**レスポンス例：**
```json
{
  "current_session": {"id": 12, "started_at": "2026-06-19T01:00:00Z"},
  "previous_session": {"id": 11, "started_at": "2026-06-12T01:00:00Z"},
  "articles": [
    {
      "article_id": 42,
      "url": "https://...1717/",
      "label": "/1717",
      "current_score": 0.85,
      "previous_score": 0.72,
      "score_delta": 0.13,
      "current_inbound": 8,
      "previous_inbound": 5,
      "inbound_delta": 3
    }
  ],
  "summary": {
    "orphan_count_current": 12,
    "orphan_count_previous": 18,
    "orphan_delta": -6
  }
}
```

---

## 9. Slack 通知

**Webhook 方式（Incoming Webhook）。** 環境変数 `SLACK_WEBHOOK_URL` を `.env` と GitHub Secrets に追加。

### 成功時の通知例

```
✅ 内部リンクの週次クロール完了
- 発見記事: 215（前回比 +3）
- クロール成功: 213
- リンク総数: 1,842（前回比 +47）
- エラー: 2
- 孤立記事: 12（前回比 -6 🎉）
- 詳細: http://localhost:5000/sessions/12
```

### 失敗時の通知例

```
❌ 内部リンクの週次クロール失敗
- 開始: 2026-06-19 01:00 UTC
- エラー: <例外メッセージ>
- ワークフロー: <GitHub Actions URL>
```

### 失敗通知の二重保険

1. `crawler_runner.py` 内で `try/except` で全体を包んで例外時に Slack 通知
2. GitHub Actions の `if: failure()` ステップで Webhook を直接叩いて通知

`SLACK_WEBHOOK_URL` 未設定時は通知をスキップしてログ出力のみ。

---

## 10. CSV エクスポート

`csv_exporter.py` を **API と GitHub Actions の両方** で共通利用。

**カラム：**

| カラム | 説明 |
|--------|------|
| `url` | フル URL |
| `label` | `/1717` 形式の短縮ラベル |
| `title` | 記事タイトル |
| `main_kw` | メインキーワード |
| `status` | `active` / `404` / `error` |
| `link_juice_score` | 0〜1 |
| `inbound_count` | 被内部リンク数 |
| `outbound_count` | 発内部リンク数 |
| `is_orphan` | `true` / `false` |

**エンコーディング：UTF-8（BOM なし）、ヘッダー付き**

**配信方法：**
- API: `GET /api/export.csv` でダウンロード
- GitHub Actions: 実行時に `output/articles_<session_id>.csv` を artifact 保存（`actions/upload-artifact@v4`）

---

## 11. GitHub Actions 定義

```yaml
# .github/workflows/weekly-crawl.yml
name: Weekly Internal Link Crawl

on:
  schedule:
    - cron: '0 1 * * 1'   # 毎週月曜 10:00 JST（UTC+9）
  workflow_dispatch:        # 手動実行も可能

jobs:
  crawl:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run crawler
        id: crawl
        run: python crawler_runner.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          TRIGGERED_BY: github_actions
      - name: Upload CSV artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: articles-csv
          path: output/*.csv
      - name: Notify Slack on failure (保険)
        if: failure()
        run: |
          curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"❌ Weekly Crawl ジョブが失敗しました: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"}' \
            ${{ secrets.SLACK_WEBHOOK_URL }}
```

**GitHub Secrets 登録値：**
- `SUPABASE_URL`: `https://tsuitsrwxkwawwqumpxj.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY`: service_role key
- `SLACK_WEBHOOK_URL`: Slack Incoming Webhook URL

---

## 12. エラーハンドリング

| ケース | 対応 |
|--------|------|
| サイトマップ取得失敗 | ログ記録、既存 DB の `status='active'` 記事のみクロールに自動フォールバック |
| 個別記事 404 | `articles.status='404'` に更新、リンク抽出スキップ、スコア計算から除外 |
| 個別記事クロール失敗（5xx・タイムアウト等） | `status='error'` 一時設定、`errors++`、次回クロールで再試行 |
| Supabase 接続エラー | 例外を上位に伝播、`crawl_sessions` 未完了のまま Slack 失敗通知 |
| 重複リンク | `UNIQUE` 制約 + `upsert` で冪等処理 |
| ページネーションの取りこぼし | `range()` で 1000 件ずつ全件取得 |
| `SLACK_WEBHOOK_URL` 未設定 | ログ出力のみで継続 |

---

## 13. テスト方針

**外部依存（本番 Supabase / Slack / 実サイト）は一切叩かない。すべてモック化。**

| テストファイル | 対象 | 方針 |
|--------------|------|------|
| `tests/test_url_utils.py` | `url_utils.py` | URL → `/{id}` 変換、エッジケース（末尾スラッシュなし、マッチなし等） |
| `tests/test_discovery.py` | `discovery.py` | `requests` をモック化、サンプル sitemap.xml で URL 抽出を検証 |
| `tests/test_database.py` | `database.py` | supabase-py クライアントをモック化、CRUD ロジックとページネーションを検証 |
| `tests/test_score_calculator.py` | `score_calculator.py` | 小規模グラフでスコア収束を検証、1000 件超のページネーション動作確認 |
| `tests/test_csv_exporter.py` | `csv_exporter.py` | UTF-8・ヘッダー・全カラム出力を検証 |
| `tests/test_slack_notifier.py` | `slack_notifier.py` | `requests.post` をモック化、サマリ整形を検証、`SLACK_WEBHOOK_URL` 未設定時のスキップを検証 |

**フィクスチャ（`tests/conftest.py`）：**
- モック supabase クライアント（`MagicMock`）
- サンプル記事 / リンクデータ
- モック sitemap.xml

テスト実行: `pytest tests/ -v`

---

## 14. 環境変数

```bash
# .env.example
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ANTHROPIC_API_KEY=sk-ant-...  # AI機能使用時のみ
TRIGGERED_BY=manual            # crawler_runner.py 起動時の triggered_by 値
```

---

## 15. 仕様外（明示的に対象外）

- SQLite → Supabase の既存データ移行（実データを使っていないため不要）
- `robots.txt` 遵守処理
- サイトマップ index（ネスト sitemap）対応
- 同時実行ロック（Actions の週次自動化前提、二重起動の懸念は無し）
- RLS / ログイン認証
- 削除済み記事の物理削除（ソフト削除のみ）

---

## 16. 移行しない既存機能（そのまま維持）

- vis.js によるグラフ可視化フロントエンド（短縮ラベルだけ追加）
- AI クラスター提案（`ai_cluster.py`）
- AI リンク提案（`ai_links.py`）
- 記事・リンクの手動 CRUD
