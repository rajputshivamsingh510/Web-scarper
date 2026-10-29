import requests
import pytest
from leadcollector.http import HttpClient, RequestFailed
from leadcollector.normalize import is_social


def test_ssl_error_is_not_retried(monkeypatch):
    c = HttpClient("t", max_retries=4, min_interval=0)
    calls = []
    def boom(*a, **k):
        calls.append(1)
        raise requests.exceptions.SSLError("bad cert")
    monkeypatch.setattr(c.session, "request", boom)
    with pytest.raises(RequestFailed):
        c.get("https://example.com")
    assert len(calls) == 1


def test_dns_failure_is_not_retried(monkeypatch):
    c = HttpClient("t", max_retries=4, min_interval=0)
    calls = []
    def boom(*a, **k):
        calls.append(1)
        raise requests.ConnectionError("getaddrinfo failed")
    monkeypatch.setattr(c.session, "request", boom)
    with pytest.raises(RequestFailed):
        c.get("http://nonexistent.example")
    assert len(calls) == 1


def test_whatsapp_short_links_are_not_websites():
    assert is_social("https://wa.link/abc")
