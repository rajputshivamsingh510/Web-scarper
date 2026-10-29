"""Local web UI.  Run:  python server.py   then open http://127.0.0.1:8000
Uses only the standard library. Listens on this computer only."""
import base64, csv, hmac, json, os, re, shutil, subprocess, sys, threading, time, webbrowser
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from leadcollector.config import load_config  # noqa: E402

WEB, DATA = ROOT / "web", (ROOT / load_config().data_dir).resolve()
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,&'()/_-]{0,79}$")
BBOX = re.compile(r"^-?\d+(\.\d+)?(,-?\d+(\.\d+)?){3}$")
MIME = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
LOCAL = ("127.0.0.1", "localhost")
# Hosting platforms (Render, etc.) set PORT. Then we listen publicly and REQUIRE a password.
PORT = int(os.getenv("PORT", "8000"))
PUBLIC = bool(os.getenv("PORT"))
HOST = "0.0.0.0" if PUBLIC else "127.0.0.1"
PASSWORD, USER = os.getenv("APP_PASSWORD", ""), os.getenv("APP_USER", "gemlab")
MAX_TARGET = int(os.getenv("MAX_TARGET", "50000"))
job = {"status": "idle"}
log = deque(maxlen=300)
proc = None


def lines(p):
    try:
        return sum(1 for _ in p.open(encoding="utf-8"))
    except OSError:
        return 0


def list_runs():
    out = []
    for d in DATA.glob("*/leads.csv"):
        d = d.parent
        try:
            rep = json.loads((d / "report.json").read_text("utf-8"))
        except (OSError, ValueError):
            rep = {}
        run = rep.get("run", {})
        out.append({"name": d.name, "modified": d.stat().st_mtime, "records": rep.get("total_records"),
                    "city": run.get("city"), "category": run.get("category")})
    return sorted(out, key=lambda r: -r["modified"])


def start_job(b):
    global proc
    src = b.get("source", "overture")
    if src not in ("overture", "osm", "overture,osm"):
        raise ValueError("Unknown source")
    city, state, cat = (b.get(k, "").strip() for k in ("city", "state", "category"))
    bbox = b.get("bbox", "").replace(" ", "")
    if not TEXT.match(cat) or (city and not TEXT.match(city)) or (state and not TEXT.match(state)):
        raise ValueError("Invalid city, state or category")
    if bbox and not BBOX.match(bbox):
        raise ValueError("Bounding box must be south,west,north,east")
    if not (city or bbox):
        raise ValueError("Enter a city or a bounding box")
    target = max(1, min(int(b.get("target", 200)), MAX_TARGET))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run = re.sub(r"[^a-z0-9]+", "-", f"{src}-{city or 'area'}-{cat}".lower()).strip("-") + "-" + stamp
    cmd = [sys.executable, "-u", "-m", "leadcollector", "run", "--source", src, "--category", cat,
           "--target", str(target), "--run-name", run, "--min-confidence", str(float(b.get("min_confidence", 0)))]
    for flag, val in (("--city", city), ("--state", state), ("--bbox", bbox)):
        if val:
            cmd += [flag, val]
    for flag, key in (("--no-enrich", "skip_enrich"), ("--require-phone", "require_phone"),
                      ("--require-website", "require_website"), ("--pilot", "pilot")):
        if b.get(key):
            cmd.append(flag)
    log.clear()
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    job.clear()
    job.update(status="running", run=run, started=time.time(), label=f"{cat} in {city or bbox}")

    def pump(p=proc):
        for line in p.stdout:
            log.append(line.rstrip())
        p.wait()
        if job.get("status") == "running":
            job["status"] = "finished" if p.returncode == 0 else "failed"
        job["ended"] = time.time()
    threading.Thread(target=pump, daemon=True).start()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json", headers=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype != "text/csv" else ""))
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        origin, host = self.headers.get("Origin"), self.headers.get("Host", "")
        if PUBLIC:  # the password protects access; just block cross-site requests
            return not origin or urlsplit(origin).netloc == host
        return host.split(":")[0] in LOCAL and (not origin or urlsplit(origin).hostname in LOCAL)

    def authed(self):
        if not PASSWORD:
            return True
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return False
        try:
            user, _, pw = base64.b64decode(h[6:]).decode("utf-8").partition(":")
        except Exception:
            return False
        return hmac.compare_digest(pw.encode(), PASSWORD.encode()) and hmac.compare_digest(user.encode(), USER.encode())

    def route(self, method):
        path = unquote(urlsplit(self.path).path)
        if path == "/healthz":
            return self.send(200, {"ok": True})
        if not self.allowed():
            return self.send(403, {"error": "Forbidden"})
        if not self.authed():
            return self.send(401, {"error": "Login required"}, headers={"WWW-Authenticate": 'Basic realm="Lead Collector"'})
        try:
            if method == "GET" and path == "/api/runs":
                return self.send(200, list_runs())
            m = re.fullmatch(r"/api/runs/([^/]+)(/csv)?", path)
            if m:
                name, d = m.group(1), DATA / m.group(1)
                if not SAFE.match(name) or not (d / "leads.csv").exists():
                    return self.send(404, {"error": "Not found"})
                if method == "GET" and m.group(2):
                    return self.send(200, (d / "leads.csv").read_bytes(), "text/csv",
                                     {"Content-Disposition": f'attachment; filename="{name}.csv"'})
                if method == "GET":
                    with (d / "leads.csv").open(encoding="utf-8-sig", newline="") as fh:
                        rows = list(csv.DictReader(fh))
                    rep = json.loads((d / "report.json").read_text("utf-8")) if (d / "report.json").exists() else {}
                    return self.send(200, {"name": name, "report": rep, "rows": rows})
                if method == "DELETE":
                    if job.get("status") == "running" and job.get("run") == name:
                        return self.send(409, {"error": "This run is still in progress"})
                    shutil.rmtree(d)
                    return self.send(200, {"deleted": name})
            if method == "GET" and path == "/api/job":
                d = DATA / job.get("run", "_")
                n1, n2 = lines(d / "stage1_collected.jsonl"), lines(d / "stage2_enriched.jsonl")
                return self.send(200, {**job, "log": list(log)[-120:], "done": n2, "total": n1})
            if method == "POST" and path == "/api/job":
                if job.get("status") == "running":
                    return self.send(409, {"error": "A search is already running"})
                n = int(self.headers.get("Content-Length", 0))
                start_job(json.loads(self.rfile.read(n) or b"{}"))
                return self.send(200, {"started": job["run"]})
            if method == "DELETE" and path == "/api/job":
                if proc and job.get("status") == "running":
                    job["status"] = "cancelled"
                    proc.terminate()
                return self.send(200, {"ok": True})
            if method == "GET":
                f = (WEB / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
                if WEB in f.parents and f.is_file():
                    return self.send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))
            return self.send(404, {"error": "Not found"})
        except (ValueError, KeyError) as exc:
            return self.send(400, {"error": str(exc)})

    do_GET = lambda self: self.route("GET")
    do_POST = lambda self: self.route("POST")
    do_DELETE = lambda self: self.route("DELETE")


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    if PUBLIC and not PASSWORD:
        if os.getenv("ALLOW_NO_PASSWORD") != "1":
            sys.exit("Public start without a password refused. Set APP_PASSWORD, or set ALLOW_NO_PASSWORD=1 to run open.")
        print("WARNING: running publicly WITHOUT a password. Anyone with the link can run searches and delete data.")
    srv = ThreadingHTTPServer((HOST, PORT), H)
    print(f"Lead Collector UI on {HOST}:{PORT} (Ctrl+C to stop)")
    if not PUBLIC:
        threading.Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    srv.serve_forever()
