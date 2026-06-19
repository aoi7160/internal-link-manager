import io
import csv
import csv_exporter


def test_export_csv_has_required_columns():
    articles = [{
        "id": 1,
        "url": "https://www.w2solution.co.jp/useful_info_ec/1717/",
        "title": "テスト", "main_kw": "EC", "status": "active",
        "link_juice_score": 0.5, "inbound_count": 2, "outbound_count": 3,
    }]
    output = csv_exporter.to_csv_string(articles)
    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)
    assert rows[0]["url"] == "https://www.w2solution.co.jp/useful_info_ec/1717/"
    assert rows[0]["label"] == "/1717"
    assert rows[0]["title"] == "テスト"
    assert rows[0]["main_kw"] == "EC"
    assert rows[0]["status"] == "active"
    assert float(rows[0]["link_juice_score"]) == 0.5
    assert int(rows[0]["inbound_count"]) == 2
    assert int(rows[0]["outbound_count"]) == 3
    assert rows[0]["is_orphan"] == "false"


def test_orphan_flag_set_when_no_inbound():
    articles = [{
        "id": 1, "url": "https://www.w2solution.co.jp/useful_info_ec/1/",
        "title": "", "main_kw": "", "status": "active",
        "link_juice_score": 0, "inbound_count": 0, "outbound_count": 5,
    }]
    output = csv_exporter.to_csv_string(articles)
    rows = list(csv.DictReader(io.StringIO(output)))
    assert rows[0]["is_orphan"] == "true"


def test_csv_is_utf8_with_header():
    output = csv_exporter.to_csv_string([])
    # Header only
    assert "url,label,title,main_kw,status,link_juice_score,inbound_count,outbound_count,is_orphan" in output.split("\n")[0]
