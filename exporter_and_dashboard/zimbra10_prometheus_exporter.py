# Zimbra Exporter amélioré pour Prometheus

import os
import re
import socket
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, Set
import requests
import psutil
import urllib3
from flask import Flask, Response, jsonify
from prometheus_client import (
    CollectorRegistry, Gauge, Counter, Info, generate_latest, CONTENT_TYPE_LATEST
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------- CONFIGURATION ---------------------------- #
EXPORTER_PORT  = int(os.getenv("ZEX_PORT", 9093))
SCRAPE_TIMEOUT = int(os.getenv("ZEX_TIMEOUT", 10))
ZIMBRA_USER    = os.getenv("ZEX_ZM_USER", "zimbra")
OVERRIDE_ROLE  = os.getenv("ZEX_ROLE")
HOSTNAME       = socket.gethostname()
DEBUG_JSON     = os.getenv("ZEX_DEBUG_JSON", "false").lower() == "true"

SERVICE_PORTS: Dict[str, list[int]] = {
    "mailbox": [110, 143, 993, 995, 7071],
    "mta":     [25, 465, 587, 2525],
    "proxy":   [80, 443, 8080, 8443],
    "ldap":    [389, 636],
}

# ------------------------------ SHELL UTILS ---------------------------- #
def run(cmd: str, as_zimbra: bool = False) -> str:
    full_cmd = f"su - {ZIMBRA_USER} -c \"{cmd}\"" if as_zimbra else cmd
    try:
        out = subprocess.check_output(
            full_cmd,
            shell=True,
            stderr=subprocess.DEVNULL,
            timeout=SCRAPE_TIMEOUT,
            text=True,
        )
        return out.strip()
    except Exception:
        return ""

# ------------------------- ROLE DETECTION ------------------------------ #
def detect_services() -> Set[str]:
    if OVERRIDE_ROLE:
        return {OVERRIDE_ROLE}
    out = run("zmcontrol status", as_zimbra=True)
    roles: Set[str] = set()
    for line in out.splitlines():
        if "Running" not in line:
            continue
        svc = line.split()[0].lower()
        if svc.startswith("mailbox"):
            roles.add("mailbox")
        elif svc.startswith("mta"):
            roles.add("mta")
        elif svc.startswith("proxy") or svc.startswith("nginx"):
            roles.add("proxy")
        elif svc.startswith("ldap"):
            roles.add("ldap")
    return roles or {"unknown"}

SERVICES = detect_services()
REG = CollectorRegistry(auto_describe=False)

# ------------------------- PROM METRICS DEF ---------------------------- #
info = Info("zimbra_exporter", "Exporter info", registry=REG)
info.info({"host": HOSTNAME, "roles": ",".join(sorted(SERVICES)), "build": "2025-07"})

g_errors = Counter("zimbra_exporter_errors_total", "Total exporter errors", registry=REG)
g_svc_status = Gauge("zimbra_service_up", "Service running status", ["service"], registry=REG)
g_port_status = Gauge("zimbra_port_open", "Port listening", ["port"], registry=REG)
g_account_total = Gauge("zimbra_accounts_total", "Total mailboxes", registry=REG)
g_account_active = Gauge("zimbra_accounts_active_30d", "Accounts active < 30d", registry=REG)
g_quota_used = Gauge("zimbra_quota_used_bytes", "Total used quota", registry=REG)
g_quota_alloc = Gauge("zimbra_quota_allocated_bytes", "Total allocated quota", registry=REG)
g_amavis_queue = Gauge("zimbra_amavis_queue_size", "Amavis queue size", registry=REG)
g_clamav_status = Gauge("zimbra_clamav_up", "ClamAV running status", registry=REG)
g_logger_conn = Gauge("zimbra_logger_mysql_connections", "Logger MySQL conn", registry=REG)
g_jetty_health = Gauge("zimbra_webmail_up", "Webmail Jetty health", registry=REG)
g_jetty_latency = Gauge("zimbra_webmail_latency_seconds", "Webmail Jetty latency", registry=REG)

# ------------------------- FLASK APP + /metrics ------------------------ #
app = Flask(__name__)

@app.route("/metrics")
def metrics():
    try:
        collect_system()
        collect_zimbra()
    except Exception as e:
        g_errors.inc()
        print(f"[{datetime.utcnow()}] ERROR: {e}")
    return Response(generate_latest(REG), mimetype=CONTENT_TYPE_LATEST)

@app.route("/")
def root():
    return f"<h3>Zimbra Exporter</h3><p>Metrics: <a href='/metrics'>/metrics</a></p>"

@app.route("/debug")
def debug():
    if not DEBUG_JSON:
        return Response("Enable debug with ZEX_DEBUG_JSON=true", status=403)
    return jsonify({"roles": list(SERVICES), "host": HOSTNAME})

# ------------------------- COLLECTORS ---------------------------- #
def collect_system():
    g_clamav_status.set(1 if "clamd" in run("pgrep -a clamd") else 0)
    try:
        conn = run("mysqladmin -uroot -p$(zmlocalconfig -s mysql_logger_root_password) status", as_zimbra=True)
        if conn:
            g_logger_conn.set(1)
    except Exception:
        g_logger_conn.set(0)

def collect_zimbra():
    out = run("zmcontrol status", as_zimbra=True)
    for line in out.splitlines():
        if not line.strip(): continue
        svc = line.split()[0].lower()
        running = "Running" in line
        g_svc_status.labels(svc).set(1 if running else 0)

    open_ports = {c.laddr.port for c in psutil.net_connections() if c.status == 'LISTEN'}
    for role in SERVICES:
        for port in SERVICE_PORTS.get(role, []):
            g_port_status.labels(str(port)).set(1 if port in open_ports else 0)

    if "mailbox" in SERVICES:
        accounts = run("zmprov -l gaa", as_zimbra=True).splitlines()
        g_account_total.set(len(accounts))
        active, used, alloc = 0, 0, 0
        cutoff = datetime.utcnow() - timedelta(days=30)
        for acc in accounts:
            meta = run(f"zmprov ga {acc} zimbraLastLogonTimestamp zimbraMailQuota zimbraMailDiskUsage", as_zimbra=True)
            lastlog = re.search(r"zimbraLastLogonTimestamp:\s*(\d{14}Z)", meta)
            if lastlog:
                ts = datetime.strptime(lastlog.group(1), "%Y%m%d%H%M%SZ")
                if ts > cutoff:
                    active += 1
            usage = re.search(r"zimbraMailDiskUsage:\s*(\d+)", meta)
            quota = re.search(r"zimbraMailQuota:\s*(\d+)", meta)
            if usage: used += int(usage.group(1))
            if quota: alloc += int(quota.group(1))
        g_account_active.set(active)
        g_quota_used.set(used)
        g_quota_alloc.set(alloc)

    if "mta" in SERVICES:
        amq = run("find /opt/zimbra/data/amavisd/tmp/ -type f | wc -l", as_zimbra=True)
        g_amavis_queue.set(int(amq) if amq.isdigit() else 0)

    if "mailbox" in SERVICES:
        try:
            t0 = time.perf_counter()
            r = requests.get("https://localhost:7071/service/extension/healthcheck", verify=False, timeout=3)
            g_jetty_latency.set(time.perf_counter() - t0)
            g_jetty_health.set(1 if r.status_code == 200 else 0)
        except Exception:
            g_jetty_health.set(0)
            g_jetty_latency.set(float("nan"))

if __name__ == "__main__":
    print(f"Starting Zimbra Exporter on :{EXPORTER_PORT} for roles {SERVICES}")
    app.run(host="0.0.0.0", port=EXPORTER_PORT)
