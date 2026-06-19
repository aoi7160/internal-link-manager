# 内部リンク管理ツール（Supabase 版）

W2 Solution `/useful_info_ec/*` 配下の記事の内部リンクを管理し、孤立記事・低リンクジュース記事を可視化するチーム共有ツール。

## 機能

| 機能 | 説明 |
|------|------|
| 記事自動発見 | サイトマップから全記事を自動取得 |
| 内部リンク管理 | 発リンク・被リンクの可視化と編集 |
| ネットワークグラフ | vis.js で記事間リンク関係を表示 |
| リンクジューススコア | 簡易 PageRank によるスコアを毎回更新 |
| 前週比較 | クロールごとの増減を表示 |
| 週次自動クロール | GitHub Actions が毎週月曜 10:00 JST に実行 |
| Slack 通知 | クロール完了・失敗を通知 |
| CSV エクスポート | AI 読み込み用に CSV を出力 |
| AI クラスター提案 | Claude AI が親子関係を提案 |
| AI リンク提案 | Claude AI が追加すべき内部リンクを提案 |

## セットアップ

### 1. Supabase スキーマを作成

Supabase ダッシュボード > SQL Editor で `supabase_schema.sql` を実行。

### 2. ローカル環境

```bash
python -m venv workspace\.venv
workspace\.venv\Scripts\activate
pip install -r requirements.txt

# .env を作成
copy .env.example .env
# .env を編集して SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 等を設定

python app.py
```

ブラウザで `http://localhost:5000` を開く。

### 3. 初回クロール

```bash
python crawler_runner.py
```

サイトマップから記事を発見し、全記事をクロールしてリンク関係を構築する。

### 4. GitHub Actions 設定

リポジトリの Settings > Secrets and variables > Actions に登録：

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SLACK_WEBHOOK_URL`

以降、毎週月曜 10:00 JST に自動でクロールが走る。

## テスト

```bash
pytest tests/ -v
```

外部依存（Supabase / Slack / 実サイト）はすべてモック化されており、ネットワーク不要で実行可能。

## データ

すべてのデータは Supabase に保存される。
- SQLite は使用しない（`data/links.db` は移行不要）
- `.env` は絶対にコミットしない

## アーキテクチャ

- `app.py`: Flask Web サーバー
- `database.py`: Supabase アクセス層
- `discovery.py`: サイトマップ解析
- `crawler.py`: 個別記事クロール
- `score_calculator.py`: PageRank 風スコア計算
- `crawler_runner.py`: 一括クロールエントリーポイント
- `slack_notifier.py` / `csv_exporter.py` / `url_utils.py`: ユーティリティ
- `.github/workflows/weekly-crawl.yml`: 週次 cron
