#!/usr/bin/env python3
"""xaudaily.com readings client — no dependencies, standard library only.

    from xaudaily import readings
    d = readings(src="my-app")
    print(d["readings"]["gold"]["live"]["last"])

    python xaudaily.py                  # human-readable summary
    python xaudaily.py --json           # full snapshot as JSON
    python xaudaily.py --field gold.live.last
    python xaudaily.py --csv            # daily rows as CSV
    python xaudaily.py --src my-app     # tag your channel (optional, appreciated)

Notes
- Every value carries `source` and `asOf`; `asOf` is the period the value describes,
  not the time it was published. Please keep the attribution with the number.
- `stale: true` means the upstream fetch failed and the previous value is carried forward.
- Data licence: CC BY 4.0 — credit xaudaily.com. This is not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://xaudaily.com"
READINGS_URL = BASE + "/readings.json"
DAILY_CSV_URL = ("https://raw.githubusercontent.com/Wangxian111/xaudaily-data/"
                 "main/data/daily/all.csv")
UA = "xaudaily-client/1.0 (+https://xaudaily.com/)"

# Windows 控制台默认 GBK，摘要里有中文/⚠ 时直接 print 会崩；作库用时无副作用。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def readings(src: str | None = None, timeout: int = 30) -> dict:
    """Fetch the current snapshot. `src` tags your app for the site's usage stats."""
    url = READINGS_URL + ("?src=" + urllib.parse.quote(src) if src else "")
    return json.loads(_fetch(url, timeout))


def daily_csv() -> list[dict]:
    """All daily rows as a list of dicts (values stay strings; '' means not reported)."""
    return list(csv.DictReader(io.StringIO(_fetch(DAILY_CSV_URL))))


def dig(obj, path: str):
    """dig(d, 'gold.live.last') — path lookup that raises KeyError with context."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                raise KeyError("no such field %r in path %r" % (part, path))
            cur = cur[part]
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            raise KeyError("cannot descend into %r while resolving %r" % (type(cur).__name__, path))
    return cur


def summarize(d: dict) -> str:
    r = d.get("readings", {})
    u = d.get("units", {})
    out = []
    out.append("xaudaily.com snapshot  |  schema=%s  generated=%s  data_asof=%s"
               % (d.get("schema"), d.get("generated_at"), d.get("data_asof")))
    gold = r.get("gold", {})
    live = gold.get("live") or {}
    rows = gold.get("rows") or []
    if live.get("last") is not None:
        out.append("  COMEX GC      %s USD/oz  (%+.2f%%)  tick %s %s"
                   % (live.get("last"), live.get("chg_pct") or 0.0,
                      live.get("date", ""), live.get("time", "")))
    if rows:
        out.append("  GC settle     %s USD/oz  (session %s)" % (rows[-1].get("c"), gold.get("asOf")))
    au = r.get("au", {})
    if au.get("last") is not None:
        out.append("  SGE Au99.99   %s CNY/g   (%+.2f%%)  %s"
                   % (au.get("last"), au.get("chg1d") or 0.0, au.get("asOf", "")))
    for key, label in (("cpi", "US CPI YoY"), ("pce", "core PCE YoY"),
                       ("nfp", "payrolls"), ("ppi", "PPI YoY")):
        s = r.get(key) or {}
        vals = s.get("vals") or []
        if vals:
            out.append("  %-13s %s  (as of %s)" % (label, vals[-1], s.get("asOf")))
    tr = r.get("treasury") or {}
    if (tr.get("y10") or {}).get("last") is not None:
        out.append("  US 10Y/30Y    %.2f%% / %.2f%%  (as of %s)"
                   % (tr["y10"]["last"], (tr.get("y30") or {}).get("last") or 0.0, tr.get("asOf")))
    oil = r.get("oil") or {}
    if (oil.get("brent") or {}).get("last") is not None:
        out.append("  Brent / WTI   %.2f / %.2f USD/bbl"
                   % (oil["brent"]["last"], (oil.get("wti") or {}).get("last") or 0.0))
    ex = r.get("extra") or {}
    for key, label, unit in (("vix", "VIX", ""), ("spdr", "SPDR holdings", "t"),
                             ("fedRate", "fed funds upper", "%")):
        seg = ex.get(key) or {}
        if isinstance(seg, dict) and seg.get("value") is not None:
            out.append("  %-13s %s%s  (as of %s)" % (label, seg.get("value"), unit, seg.get("date")))
    stale = [k for k, v in r.items() if isinstance(v, dict) and v.get("stale")]
    if stale:
        out.append("  ⚠ stale series: %s" % ", ".join(stale))
    out.append("  attribution: %s" % (d.get("meta", {}).get("citation") or "xaudaily.com"))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="xaudaily.com readings client")
    ap.add_argument("--src", help="channel tag, e.g. your app name (optional)")
    ap.add_argument("--json", action="store_true", help="print the full snapshot")
    ap.add_argument("--csv", action="store_true", help="print the daily CSV history")
    ap.add_argument("--field", help="print one field, e.g. gold.live.last")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()
    try:
        if args.csv:
            print(DAILY_CSV_URL)
            sys.stdout.write(_fetch(DAILY_CSV_URL, args.timeout))
            return 0
        d = readings(src=args.src, timeout=args.timeout)
    except urllib.error.URLError as e:
        print("network error: %s" % e, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    elif args.field:
        print(dig(d, args.field))
    else:
        print(summarize(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
