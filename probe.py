#!/usr/bin/env python3
"""dual-orbit.net observation probe.

認証情報を一切使わず、公開情報（RDAP / DNS-over-HTTPS / HTTP応答）だけで
ドメインの状態を観測し、前回との差分を検出して記録する。

- 出力1: data/observations.jsonl  … 1行1観測の生データ（追記のみ）
- 出力2: OBSERVATIONS.md          … 人が読む観測ログ（毎回再生成）

外部ライブラリ不使用（標準ライブラリのみ）。venv不要。
憲法 §1.3 に従い pathlib でパスを扱う。
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

DOMAIN = "dual-orbit.net"
TLD_RDAP = "https://rdap.verisign.com/net/v1/domain/"
DOH = "https://dns.google/resolve"
RECORD_TYPES = ["A", "AAAA", "MX", "TXT", "NS", "CAA", "SOA"]
SUBDOMAINS = ["www", "api", "blog", "photos", "test"]

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JSONL = DATA / "observations.jsonl"
REPORT = ROOT / "OBSERVATIONS.md"

UA = "kizuna-domain-lab/1.0 (observation only)"
TIMEOUT = 20


def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": "http_%s" % e.code}
    except Exception as e:
        return {"_error": type(e).__name__}


def probe_rdap():
    d = fetch_json(TLD_RDAP + DOMAIN)
    if "_error" in d:
        return {"error": d["_error"]}
    events = {e.get("eventAction"): e.get("eventDate") for e in d.get("events", [])}
    registrar = None
    for ent in d.get("entities", []):
        if "registrar" in (ent.get("roles") or []):
            for v in ent.get("vcardArray", [[], []])[1]:
                if v[0] == "fn":
                    registrar = v[3]
    return {
        "registration": events.get("registration"),
        "expiration": events.get("expiration"),
        "last_changed": events.get("last changed"),
        "status": sorted(d.get("status") or []),
        "registrar": registrar,
        "nameservers": sorted(ns.get("ldhName", "").lower() for ns in d.get("nameservers", [])),
    }


def probe_dns(name, rtype):
    d = fetch_json("%s?name=%s&type=%s" % (DOH, name, rtype),
                   {"accept": "application/dns-json"})
    if "_error" in d:
        return {"error": d["_error"]}
    answers = [a.get("data") for a in (d.get("Answer") or [])]
    return {"status": d.get("Status"), "answers": sorted(answers)}


def probe_http():
    req = urllib.request.Request("https://" + DOMAIN, method="HEAD",
                                 headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return {"code": r.status, "server": r.headers.get("Server")}
    except urllib.error.HTTPError as e:
        return {"code": e.code, "server": e.headers.get("Server")}
    except Exception as e:
        return {"code": None, "error": type(e).__name__}


def collect():
    now = datetime.now(timezone.utc)
    obs = {
        "observed_at": now.isoformat(timespec="seconds"),
        "domain": DOMAIN,
        "rdap": probe_rdap(),
        "dns": {t: probe_dns(DOMAIN, t) for t in RECORD_TYPES},
        "subdomains": {s: probe_dns("%s.%s" % (s, DOMAIN), "A") for s in SUBDOMAINS},
        "http": probe_http(),
    }
    exp = obs["rdap"].get("expiration")
    if exp:
        try:
            left = datetime.fromisoformat(exp.replace("Z", "+00:00")) - now
            obs["days_left"] = left.days
        except ValueError:
            pass
    return obs


def load_previous():
    if not JSONL.exists():
        return None
    last = None
    with JSONL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    return json.loads(last) if last else None


def diff(prev, cur):
    """観測すべきは値そのものより『前回から変わったか』。"""
    if prev is None:
        return ["初回観測（比較対象なし）"]
    changes = []
    for key in ("status", "registrar", "nameservers", "expiration"):
        a, b = prev.get("rdap", {}).get(key), cur.get("rdap", {}).get(key)
        if a != b:
            changes.append("RDAP %s: %r -> %r" % (key, a, b))
    for t in RECORD_TYPES:
        a = prev.get("dns", {}).get(t, {}).get("answers")
        b = cur.get("dns", {}).get(t, {}).get("answers")
        if a != b:
            changes.append("DNS %s: %r -> %r" % (t, a, b))
    for s in SUBDOMAINS:
        a = prev.get("subdomains", {}).get(s, {}).get("answers")
        b = cur.get("subdomains", {}).get(s, {}).get("answers")
        if a != b:
            changes.append("SUB %s: %r -> %r" % (s, a, b))
    a, b = prev.get("http", {}).get("code"), cur.get("http", {}).get("code")
    if a != b:
        changes.append("HTTP: %s -> %s" % (a, b))
    return changes


def render(rows):
    lines = [
        "# dual-orbit.net 観測ログ",
        "",
        "`probe.py` が自動生成。認証情報を使わず公開情報のみで観測している。",
        "**このファイルは毎回上書きされる。生データは `data/observations.jsonl`（追記のみ）。**",
        "",
        "| 観測日時 (UTC) | 残り日数 | RDAP status | HTTP | A | MX | 検出した変化 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        rd = r.get("rdap", {})
        a = r.get("dns", {}).get("A", {}).get("answers") or []
        mx = r.get("dns", {}).get("MX", {}).get("answers") or []
        ch = r.get("changes") or []
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r.get("observed_at", "?"),
            r.get("days_left", "?"),
            ", ".join(rd.get("status") or []) or "—",
            r.get("http", {}).get("code", "—"),
            len(a) and ", ".join(a[:2]) or "—",
            mx and ", ".join(mx) or "—（未設定）",
            "／".join(ch) if ch else "変化なし",
        ))
    lines += ["", "---", "",
              "最終更新: %s" % datetime.now(timezone.utc).isoformat(timespec="seconds")]
    return "\n".join(lines) + "\n"


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    prev = load_previous()
    cur = collect()
    cur["changes"] = diff(prev, cur)

    with JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(cur, ensure_ascii=False) + "\n")

    rows = []
    with JSONL.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    REPORT.write_text(render(rows), encoding="utf-8")

    print("observed_at : %s" % cur["observed_at"])
    print("days_left   : %s" % cur.get("days_left"))
    print("rdap status : %s" % ", ".join(cur["rdap"].get("status") or []))
    print("http        : %s" % cur["http"].get("code"))
    print("changes     :")
    for c in cur["changes"]:
        print("  - %s" % c)
    print("records     : %d observations in %s" % (len(rows), JSONL.name))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
