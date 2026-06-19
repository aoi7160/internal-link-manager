import csv
import io
import os
from url_utils import short_label

COLUMNS = ["url", "label", "title", "main_kw", "status",
           "link_juice_score", "inbound_count", "outbound_count", "is_orphan"]


def to_csv_string(articles) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for a in articles:
        writer.writerow({
            "url": a.get("url", ""),
            "label": short_label(a.get("url", "")),
            "title": a.get("title") or "",
            "main_kw": a.get("main_kw") or "",
            "status": a.get("status") or "active",
            "link_juice_score": a.get("link_juice_score", 0),
            "inbound_count": a.get("inbound_count", 0),
            "outbound_count": a.get("outbound_count", 0),
            "is_orphan": "true" if (a.get("inbound_count", 0) == 0) else "false",
        })
    return buf.getvalue()


def write_csv_file(articles, output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    content = to_csv_string(articles)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return output_path
