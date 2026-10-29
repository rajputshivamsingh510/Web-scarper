import http.server
import threading
from pathlib import Path

import duckdb
import phonenumbers
import pytest

EXAMPLE_PHONE = phonenumbers.format_number(
    phonenumbers.example_number("IN"), phonenumbers.PhoneNumberFormat.E164)  # library's documented example


@pytest.fixture()
def overture_parquet(tmp_path: Path) -> str:
    """Synthetic file with Overture's column layout. All businesses are fictional test records."""
    path = tmp_path / "places.parquet"
    con = duckdb.connect()
    con.execute(f"""
    COPY (
      SELECT * FROM (VALUES
        ('id-1', {{'primary': 'Sample Jewellers One (synthetic)'}}, {{'primary': 'jewelry_store'}},
         ['{EXAMPLE_PHONE}'], ['https://www.example.com'],
         [{{'freeform': '1 Test Road', 'locality': 'Testville', 'region': 'XX', 'postcode': '000001', 'country': 'IN'}}],
         0.95, 'open', {{'xmin': 75.80, 'xmax': 75.80, 'ymin': 30.90, 'ymax': 30.90}}),
        ('id-2', {{'primary': 'Sample Jewellers One'}}, {{'primary': 'jewelry_store'}},
         ['{EXAMPLE_PHONE}'], NULL,
         [{{'freeform': '1 Test Road', 'locality': 'Testville', 'region': 'XX', 'postcode': '000001', 'country': 'IN'}}],
         0.70, 'open', {{'xmin': 75.80, 'xmax': 75.80, 'ymin': 30.90, 'ymax': 30.90}}),
        ('id-3', {{'primary': 'Sample Jewellers Two (synthetic)'}}, {{'primary': 'jewelry_store'}},
         NULL, ['https://www.example.org'],
         [{{'freeform': '2 Test Road', 'locality': 'Testville', 'region': 'XX', 'postcode': '000002', 'country': 'IN'}}],
         0.90, 'open', {{'xmin': 75.85, 'xmax': 75.85, 'ymin': 30.95, 'ymax': 30.95}}),
        ('id-4', {{'primary': 'Sample Closed Shop (synthetic)'}}, {{'primary': 'jewelry_store'}},
         NULL, NULL, NULL, 0.90, 'closed', {{'xmin': 75.80, 'xmax': 75.80, 'ymin': 30.90, 'ymax': 30.90}}),
        ('id-5', {{'primary': 'Sample Restaurant (synthetic)'}}, {{'primary': 'restaurant'}},
         NULL, NULL, NULL, 0.90, 'open', {{'xmin': 75.80, 'xmax': 75.80, 'ymin': 30.90, 'ymax': 30.90}}),
        ('id-6', {{'primary': 'Sample Far Away Jewellers (synthetic)'}}, {{'primary': 'jewelry_store'}},
         NULL, NULL, NULL, 0.90, 'open', {{'xmin': 10.0, 'xmax': 10.0, 'ymin': 10.0, 'ymax': 10.0}})
      ) AS t(id, names, taxonomy, phones, websites, addresses, confidence, operating_status, bbox)
    ) TO '{path}' (FORMAT PARQUET)
    """)
    return str(path)


class _Handler(http.server.BaseHTTPRequestHandler):
    PAGES = {
        "/robots.txt": ("text/plain", "User-agent: *\nDisallow: /private\n"),
        "/": ("text/html", '<html><body><h1>Test shop</h1><a href="/contact-us">Contact us</a></body></html>'),
        "/contact-us": ("text/html", f'<html><body>Call <a href="tel:{EXAMPLE_PHONE}">us</a></body></html>'),
    }

    def do_GET(self):
        if self.path in self.PAGES:
            ctype, body = self.PAGES[self.path]
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture()
def local_site():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CONTACT_EMAIL", "tester@example.com")
    monkeypatch.setenv("RATE_LIMIT_SECONDS", "0")
    monkeypatch.setenv("WORKERS", "2")
    from leadcollector.config import load_config
    return load_config()
