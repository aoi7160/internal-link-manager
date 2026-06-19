import re

_PATTERN = re.compile(r"/useful_info_ec/(\d+)/?")


def short_label(url):
    if not url:
        return ""
    m = _PATTERN.search(url)
    return f"/{m.group(1)}" if m else url
