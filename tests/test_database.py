from unittest.mock import MagicMock, patch
import database as db


def test_fetch_all_paginates_over_1000_rows(mock_supabase):
    """1000件超のテーブルを range() で全件取得できる"""
    def execute_mock():
        offset = mock_supabase.table.return_value.select.return_value.range.call_args[0][0]
        if offset == 0:
            return MagicMock(data=[{"id": i} for i in range(1, 1001)])
        elif offset == 1000:
            return MagicMock(data=[{"id": i} for i in range(1001, 1501)])
        return MagicMock(data=[])

    mock_supabase.table.return_value.select.return_value.range.return_value.execute.side_effect = execute_mock

    with patch.object(db, "_client", mock_supabase):
        result = db.fetch_all("articles")

    assert len(result) == 1500


def test_normalize_url_strips_trailing_slash():
    assert db.normalize_url("https://example.com/foo/") == "https://example.com/foo"


def test_normalize_url_adds_https():
    assert db.normalize_url("example.com/foo") == "https://example.com/foo"


def test_get_articles_returns_with_counts(mock_supabase, sample_articles, sample_links):
    """articles と links から inbound/outbound 数を集計して返す"""
    def table_select(table_name):
        m = MagicMock()
        if table_name == "articles":
            m.select.return_value.eq.return_value.range.return_value.execute.return_value = MagicMock(data=sample_articles)
            m.select.return_value.range.return_value.execute.return_value = MagicMock(data=sample_articles)
        elif table_name == "links":
            m.select.return_value.range.return_value.execute.return_value = MagicMock(data=sample_links)
        return m

    mock_supabase.table.side_effect = table_select

    with patch.object(db, "_client", mock_supabase):
        rows = db.get_articles()

    by_id = {r["id"]: r for r in rows}
    assert by_id[1]["inbound_count"] == 1   # 2→1
    assert by_id[1]["outbound_count"] == 1  # 1→2
    assert by_id[2]["inbound_count"] == 1
    assert by_id[2]["outbound_count"] == 2
    assert by_id[3]["inbound_count"] == 1
    assert by_id[3]["outbound_count"] == 0
