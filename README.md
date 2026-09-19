# xaudaily-data

Daily, **source-linked** snapshots of gold and macro readings published by
**[xaudaily.com](https://xaudaily.com/)** — a free, static, cookie-free gold & macro data site.

Every number in here carries its own `source` and `asOf` (the date the figure is true for), and the
site refuses to publish a figure it cannot trace back to a named source. This repository mirrors
those readings in machine-friendly form so you can build on them without scraping HTML.

> 每个数字都带来源与截止日；本站宁可留空也不猜数字。本仓库是这些读数的机器可读镜像。

- **Data licence:** CC BY 4.0 — reuse freely, credit `xaudaily.com`
- **Code licence:** MIT (everything under `clients/` and `scripts/`)
- **Update cadence:** full snapshot twice a day (06:30 / 22:40 JST) + gold/Shanghai gold ticks every 30 min
- **Not investment advice.** / 不构成投资建议。

---

## What's in here

| Path | What it is |
|---|---|
| `data/daily/YYYY-MM-DD.csv` | one row per day: gold, Shanghai gold, CPI, PCE, payrolls, PPI, DXY, 10Y/30Y, Brent/WTI, VIX, SPDR tonnes, fed funds upper bound, Polymarket hike odds, central-bank net purchases |
| `data/daily/all.csv` | all daily rows merged, sorted by date (the file to load in pandas) |
| `data/latest/readings.json` | the complete current snapshot, exactly as served at `https://xaudaily.com/readings.json` |
| `data/latest/brief.md` | the current daily brief (Markdown) |
| `schema/readings.schema.json` | JSON Schema for the snapshot format |
| `clients/python/xaudaily.py` | dependency-free Python client + CLI |
| `scripts/build_daily_csv.py` | how the daily CSV is produced from the site's own data |
| `scripts/validate_snapshot.py` | structural + provenance checks used in CI |
| `DATA-DICTIONARY.md` | every field: meaning, unit, source, `asOf` semantics |

CLI files end with a bare numeric value, never a string — `""` means **the source did not report
that day**, it does not mean zero. Missing is missing. Fields are added, never renamed or removed,
within schema `v1`.

## Quick start

### 1. Just want the numbers (no clone)

```bash
curl -s https://xaudaily.com/readings.json | python -m json.tool | head -40
curl -s https://xaudaily.com/brief.md
```

### 2. Python client (stdlib only)

```bash
python clients/python/xaudaily.py --src my-app            # human-readable summary
python clients/python/xaudaily.py --src my-app --json     # full JSON
python clients/python/xaudaily.py --field gold.live.last  # one field
```

```python
from xaudaily import readings          # no pip install, no dependencies

d = readings(src="my-app")             # src= is optional but appreciated: see "Usage stats"
print(d["readings"]["gold"]["live"]["last"], d["units"]["gold"])
print(d["readings"]["cpi"]["vals"][-1], "% YoY as of", d["readings"]["cpi"]["asOf"])
```

### 3. CSV in pandas

```python
import pandas as pd
df = pd.read_csv("https://raw.githubusercontent.com/Wangxian111/xaudaily-data/main/data/daily/all.csv",
                 parse_dates=["date"])
print(df[["date", "gold_close", "us10y", "cpi_yoy_pct"]].tail())
```

## Live endpoints (the source of truth)

| Endpoint | Notes |
|---|---|
| <https://xaudaily.com/readings.json> | machine-readable snapshot, stable field names |
| <https://xaudaily.com/brief.md> | daily brief in Markdown |
| <https://xaudaily.com/llms.txt> | site map written for AI/LLM consumers |
| <https://xaudaily.com/d/> | daily archive, one stable URL per day (`/d/2026-09-19.html`) |
| <https://xaudaily.com/topic/> | topic pages (e.g. FOMC recaps) |
| <https://xaudaily.com/data/> | human-readable data & methodology page |
| <https://xaudaily.com/en/> | English edition |

**Usage stats:** add `?src=<your-app-name>` to any request. It is served `no-store` and lets the
site count usage per channel. It does not change the payload. This repo fetches with
`src=xaudaily-data-repo`.

## How the numbers are made (provenance policy)

- Sources are named per field: AKShare/Sina (COMEX GC, SGE Au99.99), BEA via DBnomics (PCE, GDP),
  BLS (PPI), Eastmoney datacenter (CPI, payrolls, fed funds), Yahoo Finance (yields, oil, VIX),
  IMF reporting countries (central-bank gold flows), Polymarket (FOMC pricing).
- If a source fails, the previous successful value is kept **and flagged `stale: true`** — never
  silently replaced with an estimate.
- Figures shown in the site's articles pass a programmatic `ground check`: any number in the prose
  must be traceable to this snapshot, otherwise the paragraph is dropped instead of published.
- `asOf` is the period the value describes (`2026-08` for August CPI, `2026-Q2` for quarterly PCE,
  a date for daily series). It is deliberately **not** the time of publication; `published` and
  `nextPub` carry that.

## Citing this data

```
数据来源：黄金读数 xaudaily.com（https://xaudaily.com/）
Source: Gold Data Reading, xaudaily.com — https://xaudaily.com/
```

## Corrections & requests

Open an issue if a number looks wrong, a source moved, or you need a field we don't publish yet.
Corrections are welcome — being traceable is the whole point of this dataset.

## Licence

- **Data** (`data/`, `DATA-DICTIONARY.md`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — use it commercially, just credit `xaudaily.com`.
- **Code** (`clients/`, `scripts/`, workflow): MIT.
