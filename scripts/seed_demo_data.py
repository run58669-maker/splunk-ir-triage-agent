"""Seed Splunk index=main with synthetic auth + Windows event data so the
three demo alert samples (brute_force / splunk_admin_login / suspicious_powershell)
return convincing historical_pattern + entity_context from MCP queries.

Reads SPLUNK_MCP_URL + SPLUNK_MCP_TOKEN from .env, but actually ingests via
the standard Splunk HEC-less path: HTTP receiver on mgmt 8089 /services/receivers/simple.
We use basic auth with admin creds from secrets/splunk.json.

Idempotent-ish: we tag events with sourcetype=ir_demo_seed so you can
| delete sourcetype=ir_demo_seed via search head if you want to re-run.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SECRETS = r"C:\Users\86150\Desktop\脚本\secrets\splunk.json"
SPLUNK_MGMT = "https://localhost:8089"
INDEX = "main"
TZ_JST = timezone(timedelta(hours=9))


def load_creds() -> tuple[str, str]:
    with open(SECRETS, "r", encoding="utf-8") as f:
        s = json.load(f)
    return s["username"], s["password"]


def ingest(session: requests.Session, sourcetype: str, host: str, source: str, raw: str, ts: datetime) -> None:
    params = {
        "index": INDEX,
        "sourcetype": sourcetype,
        "host": host,
        "source": source,
    }
    r = session.post(
        f"{SPLUNK_MGMT}/services/receivers/simple?{urllib.parse.urlencode(params)}",
        data=raw.encode("utf-8"),
        verify=False,
        timeout=15,
    )
    if not r.ok:
        print(f"  FAIL {r.status_code}: {r.text[:200]}", file=sys.stderr)
        r.raise_for_status()


def gen_linux_secure_brute_force(session: requests.Session) -> None:
    """38 failed logins for jsmith from 203.0.113.47 in last 15 min,
    + sparse legitimate jsmith activity in prior 7 days (so user exists)."""
    now = datetime.now(TZ_JST)
    print("Seeding linux_secure brute-force pattern...")

    # 38 failures in last 15 min
    base = now - timedelta(minutes=15)
    for i in range(38):
        ts = base + timedelta(seconds=int(i * (15 * 60 / 38)) + random.randint(0, 5))
        raw = (
            f"{ts.strftime('%b %d %H:%M:%S')} corp-bastion sshd[{12000 + i}]: "
            f"Failed password for jsmith from 203.0.113.47 port {40000 + random.randint(0, 999)} ssh2"
        )
        ingest(session, "linux_secure", "corp-bastion", "/var/log/secure", raw, ts)

    # 5 legit successful logins for jsmith from corp IP in prior 7 days
    for d in range(1, 8):
        ts = now - timedelta(days=d, hours=random.randint(8, 18))
        raw = (
            f"{ts.strftime('%b %d %H:%M:%S')} corp-bastion sshd[{8000 + d}]: "
            f"Accepted publickey for jsmith from 10.10.5.21 port 51234 ssh2: RSA SHA256:abc{d}"
        )
        ingest(session, "linux_secure", "corp-bastion", "/var/log/secure", raw, ts)

    # 2 prior brute-force attempts from DIFFERENT IPs (so analyst sees recurring victim)
    for d, ip in [(3, "198.51.100.22"), (12, "192.0.2.88")]:
        for i in range(15):
            ts = now - timedelta(days=d, minutes=random.randint(0, 30))
            raw = (
                f"{ts.strftime('%b %d %H:%M:%S')} corp-bastion sshd[{20000 + i}]: "
                f"Failed password for jsmith from {ip} port {40000 + i} ssh2"
            )
            ingest(session, "linux_secure", "corp-bastion", "/var/log/secure", raw, ts)

    print(f"  -> {38 + 5 + 30} events")


def gen_splunk_admin_login(session: requests.Session) -> None:
    """Splunk admin login from unusual source — matches alert_splunk_admin_login.json"""
    print("Seeding splunk_admin_login pattern...")
    now = datetime.now(TZ_JST)
    # The alert event itself
    ts = now - timedelta(minutes=2)
    raw = (
        f'{ts.isoformat()} INFO AuditTrail - Audit:[timestamp={ts.isoformat()} '
        f'user=admin action=login info=succeeded src=185.220.101.42][n/a]'
    )
    ingest(session, "splunkd_access", "splunkdev", "splunkd_audit", raw, ts)

    # Prior admin logins from corp IP only (so 185.220.x is anomalous)
    for d in range(1, 14):
        ts = now - timedelta(days=d, hours=random.randint(9, 17))
        raw = (
            f'{ts.isoformat()} INFO AuditTrail - Audit:[timestamp={ts.isoformat()} '
            f'user=admin action=login info=succeeded src=10.10.5.21][n/a]'
        )
        ingest(session, "splunkd_access", "splunkdev", "splunkd_audit", raw, ts)
    print(f"  -> {1 + 13} events")


def gen_suspicious_powershell(session: requests.Session) -> None:
    """Encoded PowerShell on workstation — matches alert_suspicious_powershell.json"""
    print("Seeding suspicious_powershell pattern...")
    now = datetime.now(TZ_JST)
    ts = now - timedelta(minutes=5)
    raw = (
        f'{ts.isoformat()} EventCode=4688 ComputerName=WKS-FIN-07 '
        f'NewProcessName=C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe '
        f'ProcessCommandLine="powershell.exe -nop -w hidden -enc '
        f'JABzAD0ATgBlAHcALQBPAGIAagBlAGMAdAAgAE4AZQB0AC4AVwBlAGIAQwBsAGkAZQBuAHQA" '
        f'AccountName=mchen ParentProcessName=C:\\Program Files\\Microsoft Office\\Office16\\winword.exe'
    )
    ingest(session, "WinEventLog:Security", "WKS-FIN-07", "WinEventLog:Security", raw, ts)

    # Prior PowerShell on same host = mostly benign IT scripts
    for d in range(1, 21):
        ts = now - timedelta(days=d, hours=random.randint(9, 17))
        raw = (
            f'{ts.isoformat()} EventCode=4688 ComputerName=WKS-FIN-07 '
            f'NewProcessName=C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe '
            f'ProcessCommandLine="powershell.exe -File C:\\IT\\update_check.ps1" '
            f'AccountName=mchen ParentProcessName=C:\\Windows\\System32\\taskeng.exe'
        )
        ingest(session, "WinEventLog:Security", "WKS-FIN-07", "WinEventLog:Security", raw, ts)
    print(f"  -> {1 + 20} events")


def main() -> int:
    user, pw = load_creds()
    s = requests.Session()
    s.auth = (user, pw)

    gen_linux_secure_brute_force(s)
    gen_splunk_admin_login(s)
    gen_suspicious_powershell(s)

    print("\nDone. Verify with:")
    print("  | tstats count where index=main by sourcetype")
    return 0


if __name__ == "__main__":
    random.seed(42)
    sys.exit(main())
