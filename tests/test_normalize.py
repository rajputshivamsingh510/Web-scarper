from leadcollector.normalize import (domain_of, is_social, normalize_name, normalize_phone,
                                     normalize_phones, normalize_url)
from conftest import EXAMPLE_PHONE


def test_phone_valid_and_formats():
    assert normalize_phone(EXAMPLE_PHONE) == (EXAMPLE_PHONE, "format_valid")
    national = EXAMPLE_PHONE[3:]
    assert normalize_phone(national)[0] == EXAMPLE_PHONE


def test_phone_invalid_and_missing():
    assert normalize_phone("12345") == ("", "invalid_format")
    assert normalize_phone("") == ("", "missing")


def test_multiple_phones():
    assert normalize_phones(f"{EXAMPLE_PHONE}; 12345") == [EXAMPLE_PHONE]


def test_url_normalisation():
    assert normalize_url("WWW.Example.com/") == "https://www.example.com"
    assert normalize_url("http://example.com/a/?utm_source=x&id=2") == "http://example.com/a?id=2"
    assert normalize_url("not a url") == ""
    assert normalize_url("localhost") == ""


def test_domain_and_social():
    assert domain_of("https://www.example.com/x") == "example.com"
    assert is_social("https://m.facebook.com/shop")
    assert not is_social("https://example.com")


def test_name_normalisation():
    assert normalize_name("Sharma & Sons Pvt. Ltd.") == "sharma sons"
