-- supabase_schema.sql
-- Supabase ダッシュボード > SQL Editor で実行する

DROP TABLE IF EXISTS article_score_history CASCADE;
DROP TABLE IF EXISTS crawl_sessions CASCADE;
DROP TABLE IF EXISTS link_suggestions CASCADE;
DROP TABLE IF EXISTS clusters CASCADE;
DROP TABLE IF EXISTS article_keywords CASCADE;
DROP TABLE IF EXISTS links CASCADE;
DROP TABLE IF EXISTS articles CASCADE;

CREATE TABLE articles (
  id               BIGSERIAL PRIMARY KEY,
  url              TEXT UNIQUE NOT NULL,
  main_kw          TEXT,
  title            TEXT,
  crawled_at       TIMESTAMPTZ,
  link_juice_score FLOAT DEFAULT 0,
  status           TEXT DEFAULT 'active',
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

CREATE TABLE article_keywords (
  id         BIGSERIAL PRIMARY KEY,
  article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  keyword    TEXT NOT NULL
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

CREATE TABLE crawl_sessions (
  id                  BIGSERIAL PRIMARY KEY,
  started_at          TIMESTAMPTZ DEFAULT NOW(),
  completed_at        TIMESTAMPTZ,
  articles_discovered INT DEFAULT 0,
  articles_crawled    INT DEFAULT 0,
  links_found         INT DEFAULT 0,
  errors              INT DEFAULT 0,
  triggered_by        TEXT
);

CREATE TABLE article_score_history (
  id               BIGSERIAL PRIMARY KEY,
  article_id       BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  session_id       BIGINT REFERENCES crawl_sessions(id) ON DELETE CASCADE,
  link_juice_score FLOAT,
  inbound_count    INT,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_links_from   ON links(from_article_id);
CREATE INDEX idx_links_to     ON links(to_article_id);
CREATE INDEX idx_articles_status ON articles(status);
CREATE INDEX idx_history_session ON article_score_history(session_id);
CREATE INDEX idx_history_article ON article_score_history(article_id);
