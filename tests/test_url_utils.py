import pytest
from url_utils import short_label


def test_short_label_with_trailing_slash():
    assert short_label("https://www.w2solution.co.jp/useful_info_ec/1717/") == "/1717"


def test_short_label_without_trailing_slash():
    assert short_label("https://www.w2solution.co.jp/useful_info_ec/1717") == "/1717"


def test_short_label_no_match_returns_url():
    assert short_label("https://example.com/foo") == "https://example.com/foo"


def test_short_label_none_returns_empty():
    assert short_label(None) == ""


def test_short_label_empty_string():
    assert short_label("") == ""
