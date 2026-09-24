"""Server agent: what ops.candlestack.tech knows about this machine.

Every INTERVAL seconds the agent samples host CPU, memory and disk (from /proc), the
containers (through a read-only Docker socket proxy) and the health of every PR preview
(on the internal Docker network). GET /api/snapshot returns the latest sample.

The ops Worker (github.com/CandleStack-FEI-STU/ops) fetches the snapshot every minute through
Cloudflare Access and keeps all history, so the status page stays up when this server is
down. The agent stores nothing and holds no secrets. Its JSON is a contract with that repo
(schema 1, README "Agent contract"): change both together.

Standard library only, so the image stays small and there is nothing to update.
"""

import json
import os
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

INTERVAL = int(os.environ.get("INTERVAL", "60"))
DOCKER_URL = os.environ.get("DOCKER_URL", "http://socket-proxy:2375")
VM_LABEL = os.environ.get("VM_LABEL", "")
SCHEMA = 1
PREVIEW_RE = re.compile(r"^pr-(\d{1,6})$")
# Environments first, then the services that run them, then previews by number.
ORDER = {"prod": 0, "stage": 1, "edge": 2, "agent": 3}


# --- collection ------------------------------------------------------------------------

def http_json(url, timeout=10):
    request = urllib.request.Request(url, headers={"User-Agent": "candlestack-agent/1.0"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    return body, int((time.monotonic() - started) * 1000)


def check_preview(env):
    try:
        body, ms = http_json(f"http://{env}-app:8080/api/health")
        version = body.get("version")
        return {
            "env": env,
            "ok": body.get("status") == "ok",
            "ms": ms,
            "version": version if isinstance(version, str) else None,
        }
    except Exception:
        return {"env": env, "ok": False, "ms": None, "version": None}


def docker(path):
    with urllib.request.urlopen(DOCKER_URL + path, timeout=10) as resp:
        return json.loads(resp.read().decode())


_prev_cpu = {}  # container id -> (container total usage, system usage)


def started_at(container_id):
    """Unix seconds of the container's last start; a restart changes it, a new container too."""
    try:
        value = docker(f"/containers/{container_id}/json")["State"]["StartedAt"]
        return int(datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        return None


def container_stats(c):
    labels = c.get("Labels", {})
    row = {
        "name": labels.get("com.docker.compose.service") or c["Names"][0].lstrip("/"),
        "env": labels.get("com.docker.compose.project", ""),
        "state": c.get("State", ""),
        "up": re.sub(r"^Up\s+", "", c.get("Status", "")),
        "cpu": None,
        "mem": None,
        # For deploy, redeploy and restart events on ops.
        "created": c.get("Created"),
        "started": started_at(c["Id"]),
        "version": labels.get("candlestack.version"),
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
        "label": VM_LABEL,
        "cpus": os.cpu_count() or 1,
        "uptime": float(Path("/proc/uptime").read_text().split()[0]),
        "cpu": cpu,
        "load": float(Path("/proc/loadavg").read_text().split()[0]),
        "mem_used": mem["MemTotal"] - mem["MemAvailable"],
        "mem_total": mem["MemTotal"],
        "disk_used": (disk.f_blocks - disk.f_bfree) * disk.f_frsize,
        "disk_total": disk.f_blocks * disk.f_frsize,
    }


def sort_key(container):
    env = container["env"]
    preview = PREVIEW_RE.match(env)
    return (ORDER.get(env, 4), int(preview[1]) if preview else 0, env, container["name"])


LATEST = None  # the last complete snapshot


def sample():
    running = docker("/containers/json")
    projects = {c.get("Labels", {}).get("com.docker.compose.project", "") for c in running}
    previews = sorted((p for p in projects if PREVIEW_RE.match(p)), key=lambda p: int(p[3:]))
    with ThreadPoolExecutor(max_workers=8) as pool:
        preview_checks = list(pool.map(check_preview, previews))
        containers = list(pool.map(container_stats, running))
    return {
        "schema": SCHEMA,
        "sampled_at": int(time.time()),
        "host": host_metrics(),
        "containers": sorted(containers, key=sort_key),
        "previews": preview_checks,
    }


def sampler():
    global LATEST
    while True:
        started = time.monotonic()
        try:
            LATEST = sample()
        except Exception as exc:  # keep sampling; a stale sample shows up as "stale data" on ops
            print(f"sample failed: {exc!r}", flush=True)
        time.sleep(max(1, INTERVAL - (time.monotonic() - started)))


# --- HTTP ------------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def send(self, code, body):
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        fresh = LATEST is not None and time.time() - LATEST["sampled_at"] <= 3 * INTERVAL
        if path == "/api/snapshot":
            if LATEST is None:
                self.send(503, {"status": "starting"})
            else:
                self.send(200, LATEST)
        elif path == "/api/health":
            self.send(200 if fresh else 503, {"status": "ok" if fresh else "stale"})
        else:
            self.send(404, {"status": "not found"})

    def log_message(self, *args):
        pass


def main():
    threading.Thread(target=sampler, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
