#!/usr/bin/env python3
"""把 xaudaily 的读数提取成「每日一行」的 CSV。

两种输入方式：
  # 从每日存档页目录回填历史
  python build_daily_csv.py --html-dir d --out data/daily
  # 从站点当前的 readings.json 追加/更新今天这一行
  python build_daily_csv.py --readings readings.json --out data/daily

设计原则：字段缺失就留空，绝不猜数字（这个站的全部信誉就建立在"数字可溯源"上）。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime

# 列顺序固定，便于 diff 和下游按位置读取
COLUMNS = [
    "date", "generated_at",
    "gold_asof", "gold_close", "gold_live", "gold_chg_pct",
    "au_asof", "au_last", "au_chg1d",
    "cpi_asof", "cpi_yoy_pct",
    "pce_asof", "pce_yoy_pct",
    "nfp_asof", "nfp_k",
    "ppi_asof", "ppi_yoy_pct",
    "dxy_asof", "dxy",
    "us10y", "us30y",
    "brent", "wti",
    "vix", "spdr_tonnes",
    "fed_funds_upper_pct", "polymarket_hike25",
    "cb_net_purchase_tonnes",
]

DATA_RX = re.compile(r"/\* ==== DATA:START ==== \*/(.*?)/\* ==== DATA:END ==== \*/", re.S)

# Windows 控制台默认 GBK，脚本里只要有一个 ✓/中文就可能 UnicodeEncodeError 崩掉。
# 在导入时就换掉编码，别依赖调用方设置 PYTHONIOENCODING。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except Exception:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def _last(seq, default=None):
    try:
        if seq:
            return seq[-1]
    except Exception:
        pass
    return default


def _num(v):
    """只接受真正的数字；None/空串/非数字都返回 None（宁可留空）。"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    return None


def row_from_payload(payload: dict, date: str) -> dict:
    """从 PAGE_DATA 结构（存档页）或 readings.json 的 readings 段生成一行。

    两种输入的差别：readings.json 把序列放在顶层 readings 下；存档页直接平铺。
    """
    r = payload.get("readings") if isinstance(payload.get("readings"), dict) else payload
    row = {c: "" for c in COLUMNS}
    row["date"] = date
    row["generated_at"] = payload.get("generated_at") or payload.get("generatedAt") or ""

    gold = r.get("gold") or {}
    if isinstance(gold, dict):
        row["gold_asof"] = gold.get("asOf") or ""
        rows = gold.get("rows") or []
        if rows:
            row["gold_close"] = _num(_last([x.get("c") for x in rows if isinstance(x, dict)])) or ""
        live = gold.get("live") or {}
        if isinstance(live, dict):
            v = _num(live.get("last"))
            if v is not None:
                row["gold_live"] = v
                row["gold_asof"] = live.get("date") or row["gold_asof"]
            p = _num(live.get("chg_pct"))
            if p is not None:
                row["gold_chg_pct"] = p

    au = r.get("au") or {}
    if isinstance(au, dict):
        row["au_asof"] = au.get("asOf") or ""
        v = _num(au.get("last"))
        if v is not None:
            row["au_last"] = v
        c = _num(au.get("chg1d"))
        if c is not None:
            row["au_chg1d"] = c
        live = au.get("live") or {}
        if isinstance(live, dict) and _num(live.get("last")) is not None:
            row["au_last"] = _num(live.get("last"))
            row["au_asof"] = live.get("date") or row["au_asof"]

    for key, asof_col, val_col in (("cpi", "cpi_asof", "cpi_yoy_pct"),
                                   ("pce", "pce_asof", "pce_yoy_pct"),
                                   ("nfp", "nfp_asof", "nfp_k"),
                                   ("ppi", "ppi_asof", "ppi_yoy_pct")):
        s = r.get(key) or {}
        if isinstance(s, dict):
            row[asof_col] = s.get("asOf") or ""
            v = _num(_last(s.get("vals")))
            if v is not None:
                row[val_col] = v

    dxy = r.get("dxy") or {}
    if isinstance(dxy, dict):
        row["dxy_asof"] = dxy.get("asOf") or _last(dxy.get("dates")) or ""
        v = _num(_last(dxy.get("vals")))
        if v is not None:
            row["dxy"] = v

    tr = r.get("treasury") or {}
    if isinstance(tr, dict):
        for key, col in (("y10", "us10y"), ("y30", "us30y")):
            seg = tr.get(key) or {}
            if isinstance(seg, dict):
                v = _num(seg.get("last"))
                if v is None:
                    v = _num(_last(seg.get("vals")))
                if v is not None:
                    row[col] = v

    oil = r.get("oil") or {}
    if isinstance(oil, dict):
        for key, col in (("brent", "brent"), ("wti", "wti")):
            seg = oil.get(key) or {}
            if isinstance(seg, dict):
                v = _num(seg.get("last"))
                if v is None:
                    v = _num(_last(seg.get("vals")))
                if v is not None:
                    row[col] = v

    ex = r.get("extra") or {}
    if isinstance(ex, dict):
        for key, col, field in (("vix", "vix", "value"), ("spdr", "spdr_tonnes", "value")):
            seg = ex.get(key) or {}
            if isinstance(seg, dict):
                v = _num(seg.get(field))
                if v is not None:
                    row[col] = v
        fr = ex.get("fedRate") or {}
        if isinstance(fr, dict):
            v = _num(fr.get("value"))
            if v is not None:
                row["fed_funds_upper_pct"] = v
        pm = ex.get("polymarket") or {}
        if isinstance(pm, dict):
            v = _num(pm.get("hike25"))
            if v is not None:
                row["polymarket_hike25"] = v
        cf = ex.get("cbFlow") or {}
        if isinstance(cf, dict):
            v = _num(_last(cf.get("vals")))
            if v is not None:
                row["cb_net_purchase_tonnes"] = v
    return row


def load_payload_from_html(path: str):
    txt = open(path, encoding="utf-8", errors="replace").read()
    m = DATA_RX.search(txt)
    if not m:
        return None
    js = m.group(1).strip()
    js = re.sub(r"^const\s+PAGE_DATA\s*=\s*", "", js).rstrip(";").strip()
    try:
        return json.loads(js)
    except Exception:
        return None


def write_csv(path: str, row: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerow(row)


def rebuild_all(out_dir: str) -> str:
    """把所有 data/daily/YYYY-MM-DD.csv 合并成 data/daily/all.csv（按日期排序）。"""
    files = sorted(f for f in os.listdir(out_dir)
                   if re.match(r"^\d{4}-\d{2}-\d{2}\.csv$", f))
    allp = os.path.join(out_dir, "all.csv")
    with open(allp, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for f in files:
            with open(os.path.join(out_dir, f), encoding="utf-8", newline="") as f2:
                for row in csv.DictReader(f2):
                    w.writerow(row)
    return allp


def main() -> int:
    ap = argparse.ArgumentParser(description="把 xaudaily 读数提取成每日 CSV")
    ap.add_argument("--html-dir", help="每日存档页目录（d/），回填历史用")
    ap.add_argument("--readings", help="站点当前 readings.json，更新今天这一行用")
    ap.add_argument("--out", required=True, help="输出目录，例如 data/daily")
    ap.add_argument("--date", help="配合 --readings 指定日期（默认取 readings 的 data_asof/generated_at）")
    args = ap.parse_args()

    written = []
    if args.html_dir:
        for name in sorted(os.listdir(args.html_dir)):
            m = re.match(r"^(\d{4}-\d{2}-\d{2})\.html$", name)
            if not m:
                continue
            payload = load_payload_from_html(os.path.join(args.html_dir, name))
            if not payload:
                log("  ⚠ %s 没有 DATA 块，跳过" % name)
                continue
            row = row_from_payload(payload, m.group(1))
            p = os.path.join(args.out, m.group(1) + ".csv")
            write_csv(p, row)
            written.append(p)
            log("  ✓ %s" % p)

    if args.readings:
        payload = json.load(open(args.readings, encoding="utf-8"))
        date = args.date
        if not date:
            g = payload.get("data_asof") or payload.get("generated_at") or ""
            m = re.search(r"(\d{4}-\d{2}-\d{2})", g)
            date = m.group(1) if m else datetime.now().strftime("%Y-%m-%d")
        row = row_from_payload(payload, date)
        p = os.path.join(args.out, date + ".csv")
        write_csv(p, row)
        written.append(p)
        log("  ✓ %s" % p)

    if not written:
        log("✗ 没有任何输入（--html-dir 或 --readings 至少要给一个）")
        return 1
    allp = rebuild_all(args.out)
    log("  ✓ 合并 → %s（%d 行）" % (allp, sum(1 for _ in open(allp, encoding="utf-8")) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
