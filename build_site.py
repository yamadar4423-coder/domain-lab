#!/usr/bin/env python3
"""observations.jsonl から公開用の観測ページ site/index.html を生成する。

公開されるのは RDAP / DNS / HTTP という「もともと世界に公開されている情報」のみ。
内部の設計メモ・インフラ構成・運用ルールは一切含めない（GitHub公開ミラーの原則）。
"""

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JSONL = ROOT / "data" / "observations.jsonl"
OUT = ROOT / "site" / "index.html"
DOMAIN = "dual-orbit.net"
EXPIRY = "2027-05-03T00:35:10+00:00"


def load():
    rows = []
    if JSONL.exists():
        with JSONL.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def esc(v):
    return html.escape(str(v))


def joined(v, empty="—"):
    if not v:
        return empty
    return ", ".join(v) if isinstance(v, list) else str(v)


def build(rows):
    latest = rows[-1] if rows else {}
    rdap = latest.get("rdap", {})
    dns = latest.get("dns", {})
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")

    cards = [
        ("残り日数", esc(latest.get("days_left", "—")), "日"),
        ("失効予定", "2027-05-03", ""),
        ("HTTP", esc(latest.get("http", {}).get("code", "—")), ""),
        ("観測回数", str(len(rows)), "回"),
    ]
    card_html = "\n".join(
        '      <div class="card"><span class="k">%s</span>'
        '<span class="v">%s<small>%s</small></span></div>' % (k, v, u)
        for k, v, u in cards
    )

    facts = [
        ("registrar", joined(rdap.get("registrar"))),
        ("status", joined(rdap.get("status"))),
        ("nameservers", joined(rdap.get("nameservers"))),
        ("A", joined(dns.get("A", {}).get("answers"))),
        ("AAAA", joined(dns.get("AAAA", {}).get("answers"))),
        ("MX", joined(dns.get("MX", {}).get("answers"), "—（未設定）")),
        ("TXT", joined(dns.get("TXT", {}).get("answers"))),
        ("CAA", joined(dns.get("CAA", {}).get("answers"))),
    ]
    fact_html = "\n".join(
        "      <tr><td>%s</td><td>%s</td></tr>" % (esc(k), esc(v)) for k, v in facts
    )

    log_html = "\n".join(
        "      <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(r.get("observed_at", "?")),
            esc(r.get("days_left", "—")),
            esc(r.get("http", {}).get("code", "—")),
            esc("／".join(r.get("changes") or []) or "変化なし"),
        )
        for r in reversed(rows)
    )

    return TEMPLATE % {
        "domain": DOMAIN,
        "cards": card_html,
        "facts": fact_html,
        "log": log_html,
        "generated": generated,
        "expiry": EXPIRY,
    }


TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(domain)s 観測ログ</title>
<style>
  :root{
    --bg:#EDF0EF;--surface:#fff;--surface2:#F5F7F6;--ink:#141D1B;--ink2:#3A4A47;
    --muted:#66756F;--rule:#D2DAD7;--accent:#0E6B70;
  }
  @media (prefers-color-scheme:dark){
    :root{--bg:#0D1413;--surface:#141D1B;--surface2:#1A2523;--ink:#E7EDEB;
          --ink2:#BCC9C5;--muted:#8B9A95;--rule:#25332F;--accent:#54B8B0;}
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);line-height:1.75;
    font-family:'Hiragino Sans','Yu Gothic',system-ui,sans-serif;}
  .wrap{max-width:900px;margin:0 auto;padding:40px 20px 80px}
  h1{font-size:1.6rem;margin:0 0 4px;letter-spacing:.01em}
  h2{font-size:1rem;margin:40px 0 12px;color:var(--ink2);
    font-family:ui-monospace,Consolas,monospace;text-transform:uppercase;
    letter-spacing:.12em;font-weight:500}
  .sub{color:var(--muted);font-size:.9rem;margin:0 0 28px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
    gap:1px;background:var(--rule);border:1px solid var(--rule)}
  .card{background:var(--surface);padding:14px 16px;display:flex;flex-direction:column}
  .card .k{font-size:.68rem;letter-spacing:.1em;color:var(--muted);
    font-family:ui-monospace,Consolas,monospace;text-transform:uppercase}
  .card .v{font-size:1.5rem;font-family:ui-monospace,Consolas,monospace;
    font-variant-numeric:tabular-nums}
  .card .v small{font-size:.75rem;color:var(--muted);margin-left:2px}
  .scroll{overflow-x:auto;border:1px solid var(--rule);background:var(--surface)}
  table{border-collapse:collapse;width:100%%;font-size:.88rem}
  td,th{text-align:left;padding:9px 14px;border-bottom:1px solid var(--rule);
    vertical-align:top}
  tr:last-child td{border-bottom:0}
  td:first-child{font-family:ui-monospace,Consolas,monospace;color:var(--ink2);
    white-space:nowrap}
  thead th{background:var(--surface2);font-size:.68rem;letter-spacing:.1em;
    color:var(--muted);text-transform:uppercase;
    font-family:ui-monospace,Consolas,monospace;white-space:nowrap}
  footer{margin-top:48px;padding-top:18px;border-top:1px solid var(--rule);
    color:var(--muted);font-size:.8rem}
  a{color:var(--accent)}
</style>
</head>
<body>
<div class="wrap">
  <h1>%(domain)s 観測ログ</h1>
  <p class="sub">更新を停止したドメインが失効するまでを、公開情報だけで定点観測している。
  このページは観測データから自動生成される。</p>

  <div class="cards">
%(cards)s
  </div>

  <h2>最新の状態</h2>
  <div class="scroll"><table>
%(facts)s
  </table></div>

  <h2>観測履歴</h2>
  <div class="scroll"><table>
    <thead><tr><th>観測日時 (UTC)</th><th>残り</th><th>HTTP</th><th>検出した変化</th></tr></thead>
    <tbody>
%(log)s
    </tbody>
  </table></div>

  <footer>
    出典: RDAP (rdap.verisign.com) / DNS-over-HTTPS / HTTP応答。すべて認証不要の公開情報。<br>
    生成: %(generated)s ・ 失効予定: %(expiry)s
  </footer>
</div>
</body>
</html>
"""


def main():
    """引数で出力先を指定できる（省略時は site/index.html）。

    公開ミラー（publish ブランチ）ではページをリポジトリ直下に置くため、
    GitHub Actions からは `python build_site.py index.html` として呼ぶ。
    """
    out = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "site/index.html")
    rows = load()
    if not rows:
        print("no observations yet; run probe.py first")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(rows), encoding="utf-8")
    print("wrote %s (%d observations, %d bytes)" %
          (out.relative_to(ROOT), len(rows), out.stat().st_size))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
