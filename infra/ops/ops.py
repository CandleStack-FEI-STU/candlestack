"""Ops status for ops.candlestack.tech: a collector plus a small HTTP server.

Every INTERVAL seconds the collector checks the health endpoint of prod (through the
public URL, as users see it), stage and every PR preview (on the internal Docker network),
samples host CPU, memory and disk, and reads container stats through a read-only Docker
socket proxy. Results live in SQLite for 35 days. Events (deploys, outages, recoveries,
previews starting and stopping) are derived automatically from the checks.

Standard library only, so the image stays small and there is nothing to update.
"""

import json
import os
import re
import sqlite3
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

INTERVAL = int(os.environ.get("INTERVAL", "60"))
DB_PATH = os.environ.get("DB_PATH", "/data/ops.db")
DOCKER_URL = os.environ.get("DOCKER_URL", "http://socket-proxy:2375")
PROD_URL = os.environ.get("PROD_URL", "https://app.candlestack.tech")
VM_LABEL = os.environ.get("VM_LABEL", "")
RETENTION_DAYS = 35
STATIC = Path(__file__).with_name("static")
PREVIEW_RE = re.compile(r"^pr-(\d+)$")

ENV_NAMES = {"prod": "Production", "stage": "Staging"}


def env_name(env):
    return ENV_NAMES.get(env, f"Preview {env}")


# --- storage ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (ts INTEGER, env TEXT, ok INTEGER, ms INTEGER, version TEXT);
CREATE INDEX IF NOT EXISTS checks_env_ts ON checks (env, ts);
CREATE TABLE IF NOT EXISTS metrics (ts INTEGER, cpu REAL, load REAL, mem_used INTEGER,
    mem_total INTEGER, disk_used INTEGER, disk_total INTEGER);
CREATE INDEX IF NOT EXISTS metrics_ts ON metrics (ts);
CREATE TABLE IF NOT EXISTS events (ts INTEGER, env TEXT, message TEXT, source TEXT);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);
CREATE TABLE IF NOT EXISTS state (env TEXT PRIMARY KEY, value TEXT);
"""


def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# --- collection ------------------------------------------------------------------------

def http_json(url, timeout=10):
    # Cloudflare's browser integrity check rejects the default Python-urllib user agent.
    request = urllib.request.Request(url, headers={"User-Agent": "candlestack-ops/1.0"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    return body, int((time.monotonic() - started) * 1000)


def check(env, url):
    try:
        body, ms = http_json(url)
        return {"env": env, "ok": body.get("status") == "ok", "ms": ms, "version": body.get("version")}
    except Exception:
        return {"env": env, "ok": False, "ms": None, "version": None}


def docker(path):
    with urllib.request.urlopen(DOCKER_URL + path, timeout=10) as resp:
        return json.loads(resp.read().decode())


_prev_cpu = {}  # container id -> (container total usage, system usage)


def container_stats(c):
    labels = c.get("Labels", {})
    row = {
        "name": labels.get("com.docker.compose.service") or c["Names"][0].lstrip("/"),
        "env": labels.get("com.docker.compose.project", ""),
        "state": c.get("State"),
        "up": re.sub(r"^Up\s+", "", c.get("Status", "")),
        "cpu": None,
        "mem": None,
    }
    try:
        s = docker(f"/containers/{c['Id']}/stats?stream=false&one-shot=true")
        cpu = s["cpu_stats"]
        total, system = cpu["cpu_usage"]["total_usage"], cpu.get("system_cpu_usage", 0)
        prev = _prev_cpu.get(c["Id"])
        if prev and system > prev[1]:
            cpus = cpu.get("online_cpus") or 1
            row["cpu"] = round((total - prev[0]) / (system - prev[1]) * cpus * 100, 1)
        _prev_cpu[c["Id"]] = (total, system)
        mem = s.get("memory_stats", {})
        inactive = mem.get("stats", {}).get("inactive_file", 0)
        row["mem"] = max(mem.get("usage", 0) - inactive, 0)
    except Exception:
        pass
    return row


_prev_host_cpu = None


def host_metrics():
    global _prev_host_cpu
    fields = [int(x) for x in Path("/proc/stat").read_text().split("\n")[0].split()[1:9]]
    idle, total = fields[3] + fields[4], sum(fields)
    cpu = None
    if _prev_host_cpu and total > _prev_host_cpu[1]:
        cpu = round((1 - (idle - _prev_host_cpu[0]) / (total - _prev_host_cpu[1])) * 100, 1)
    _prev_host_cpu = (idle, total)

    mem = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        mem[key] = int(value.split()[0]) * 1024
    disk = os.statvfs("/")
    return {
        "cpu": cpu,
        "load": float(Path("/proc/loadavg").read_text().split()[0]),
        "mem_used": mem["MemTotal"] - mem["MemAvailable"],
        "mem_total": mem["MemTotal"],
        "disk_used": (disk.f_blocks - disk.f_bfree) * disk.f_frsize,
        "disk_total": disk.f_blocks * disk.f_frsize,
    }


def record_transitions(conn, now, results):
    """Turn consecutive check results into events and remember the state per environment."""
    states = {r["env"]: json.loads(r["value"]) for r in conn.execute("SELECT * FROM state")}
    seen = set()

    def event(env, message, source):
        conn.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (now, env, message, source))

    for r in results:
        env, prev = r["env"], states.get(r["env"])
        seen.add(env)
        cur = dict(prev or {"fails": 0, "down_since": None, "version": None})
        if r["ok"]:
            if prev is None and PREVIEW_RE.match(env):
                event(env, f"{env_name(env)} started", "preview")
            if cur["down_since"]:
                minutes = max(1, round((now - cur["down_since"]) / 60))
                event(env, f"{env_name(env)} recovered after {minutes} min", "health check")
            if prev and cur["version"] and r["version"] != cur["version"]:
                event(env, f"{env_name(env)} deployed {r['version']}", "deploy")
            cur.update(fails=0, down_since=None, version=r["version"])
        else:
            cur["fails"] += 1
            if cur["fails"] == 2 and not cur["down_since"]:
                cur["down_since"] = now - INTERVAL
                event(env, f"{env_name(env)} stopped responding", "health check")
        conn.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (env, json.dumps(cur)))

    for env in states.keys() - seen:
        if PREVIEW_RE.match(env):
            event(env, f"{env_name(env)} removed", "preview")
            conn.execute("DELETE FROM state WHERE env = ?", (env,))


LATEST = {"containers": [], "previews": [], "ts": 0}


def collect_once():
    now = int(time.time())
    try:
        running = docker("/containers/json")
    except Exception:
        running = []
    projects = {c.get("Labels", {}).get("com.docker.compose.project", "") for c in running}
    previews = sorted((p for p in projects if PREVIEW_RE.match(p)), key=lambda p: int(p[3:]))

    targets = [("prod", f"{PROD_URL}/api/health"), ("stage", "http://stage-app:8080/api/health")]
    targets += [(p, f"http://{p}-app:8080/api/health") for p in previews]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda t: check(*t), targets))
        containers = list(pool.map(container_stats, running))
    metrics = host_metrics()

    conn = db()
    with conn:
        conn.executemany(
            "INSERT INTO checks VALUES (?, ?, ?, ?, ?)",
            [(now, r["env"], int(r["ok"]), r["ms"], r["version"]) for r in results],
        )
        if metrics["cpu"] is not None:
            conn.execute(
                "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now, metrics["cpu"], metrics["load"], metrics["mem_used"], metrics["mem_total"],
                 metrics["disk_used"], metrics["disk_total"]),
            )
        record_transitions(conn, now, results)
        cutoff = now - RETENTION_DAYS * 86400
        for table in ("checks", "metrics", "events"):
            conn.execute(f"DELETE FROM {table} WHERE ts < ?", (cutoff,))
    conn.close()

    order = {"prod": 0, "stage": 1, "edge": 2, "ops": 3}
    containers.sort(key=lambda c: (order.get(c["env"], 4), c["env"], c["name"]))
    LATEST.update(containers=containers, previews=previews, ts=now, metrics=metrics)


def collector():
    while True:
        started = time.monotonic()
        try:
            collect_once()
        except Exception as exc:  # keep collecting; the page shows the age of the last check
            print(f"collect failed: {exc!r}", flush=True)
        time.sleep(max(1, INTERVAL - (time.monotonic() - started)))


# --- status API ------------------------------------------------------------------------

def day_marks(conn, env, now):
    """Per day for the last 30 days (index 0 = 30 days ago): none, up, warn or down."""
    marks = ["none"] * 30
    rows = conn.execute(
        "SELECT (? - ts) / 86400 AS d, COUNT(*) AS n, SUM(1 - ok) AS failed FROM checks "
        "WHERE env = ? AND ts > ? GROUP BY d",
        (now, env, now - 30 * 86400),
    )
    for r in rows:
        idx = 29 - int(r["d"])
        if 0 <= idx < 30:
            marks[idx] = "up" if r["failed"] == 0 else "warn" if r["failed"] < 5 else "down"
    return marks


def env_status(conn, env, host, now, with_history):
    last = conn.execute(
        "SELECT * FROM checks WHERE env = ? ORDER BY ts DESC LIMIT 1", (env,)
    ).fetchone()
    status = {"env": env, "name": env_name(env), "host": host, "state": "unknown"}
    if last:
        status.update(state="up" if last["ok"] else "down", ms=last["ms"], checked=last["ts"])
        version = conn.execute(
            "SELECT version FROM checks WHERE env = ? AND ok = 1 ORDER BY ts DESC LIMIT 1", (env,)
        ).fetchone()
        status["version"] = version["version"] if version else None
    if with_history:
        uptime = conn.execute(
            "SELECT AVG(ok) AS u FROM checks WHERE env = ? AND ts > ?", (env, now - 30 * 86400)
        ).fetchone()["u"]
        status["uptime30"] = round(uptime * 100, 2) if uptime is not None else None
        status["days"] = day_marks(conn, env, now)
    return status


def hourly(conn, column, now):
    rows = conn.execute(
        f"SELECT (? - ts) / 3600 AS h, AVG({column}) AS v FROM metrics WHERE ts > ? GROUP BY h",
        (now, now - 24 * 3600),
    )
    values = [None] * 24
    for r in rows:
        idx = 23 - int(r["h"])
        if 0 <= idx < 24:
            values[idx] = r["v"]
    return values


def status():
    now = int(time.time())
    conn = db()
    try:
        envs = [
            env_status(conn, "prod", "app.candlestack.tech", now, True),
            env_status(conn, "stage", "stage.candlestack.tech", now, True),
        ]
        previews = [
            env_status(conn, p, f"{p}-preview.candlestack.tech", now, False)
            for p in LATEST["previews"]
        ]
        latest_metric = conn.execute("SELECT * FROM metrics ORDER BY ts DESC LIMIT 1").fetchone()
        day_ago = conn.execute(
            "SELECT disk_used FROM metrics WHERE ts < ? ORDER BY ts DESC LIMIT 1", (now - 86400,)
        ).fetchone()
        mem_share = [
            v / latest_metric["mem_total"] * 100 if v is not None and latest_metric else None
            for v in hourly(conn, "mem_used", now)
        ]
        server = {
            "label": VM_LABEL,
            "cpus": os.cpu_count(),
            "uptime": float(Path("/proc/uptime").read_text().split()[0]),
            "metrics": dict(latest_metric) if latest_metric else None,
            "cpu_24h": hourly(conn, "cpu", now),
            "mem_24h": mem_share,
            "disk_per_day": latest_metric["disk_used"] - day_ago["disk_used"]
            if latest_metric and day_ago else None,
        }
        events = [
            dict(r) for r in conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT 15")
        ]
    finally:
        conn.close()
    return {
        "now": now,
        "interval": INTERVAL,
        "last_collect": LATEST["ts"],
        "environments": envs,
        "previews": previews,
        "sources": None,  # filled once the app exposes /api/health/sources
        "server": server,
        "containers": LATEST["containers"],
        "events": events,
    }


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            self.send(200, json.dumps(status()).encode(), "application/json")
        elif path == "/api/health":
            self.send(200, b'{"status":"ok"}', "application/json")
        elif path in ("/", "/index.html"):
            self.send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self.send(404, b"Not found", "text/plain")

    def log_message(self, *args):
        pass


def main():
    conn = db()
    conn.executescript(SCHEMA)
    conn.close()
    threading.Thread(target=collector, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
