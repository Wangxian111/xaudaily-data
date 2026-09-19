# Data dictionary

Field-by-field reference for `data/latest/readings.json`, `data/daily/*.csv` and the live
`https://xaudaily.com/readings.json`.

## `asOf` vs `published` — read this first

- **`asOf`** = the period the value *describes*. `2026-08` (August CPI), `2026-Q2` (quarterly PCE),
  `2026-09-18` (a daily close). This is the field you should align on when joining data.
- **`published`** = when the statistic was released by its agency.
- **`nextPub`** = next scheduled release, when the source publishes one.
- **`stale: true`** = the fetch failed and the previous successful value is being carried forward.
  Treat stale values as "last known", not "current".
- **`""` in CSV** = the source did not report that day. It is **not** zero.

Every series object carries its own `source` string. If you republish a number, carry the source
with it.

## Snapshot top level (`readings.json`)

| Key | Meaning |
|---|---|
| `schema` | format version, currently `xaudaily.readings/v1`. Fields are only added within a version. |
| `generated_at` | when the snapshot was assembled (JST) |
| `data_asof` | newest data timestamp inside the snapshot (JST) |
| `units` | human-readable unit + scope for each series |
| `site` | canonical URLs: home, daily archive (+index), `brief.md`, `llms.txt`, topics, sitemap |
| `readings` | the series themselves (below) |
| `meta` | `source_policy`, `disclaimer`, `attribution`, `license`, `citation`, `docs`, `update_schedule`, `stability`, and a `policy` block with fed-funds path and market pricing |

## Series in `readings`

### `gold` — COMEX GC continuous (front month)

| Field | Unit | Notes |
|---|---|---|
| `rows[] = {d,o,h,l,c}` | USD/oz | daily OHLC, oldest → newest (≈120 sessions) |
| `live = {last, chg, chg_pct, date, time, source}` | USD/oz | intraday tick from Sina's COMEX feed, refreshed every 30 min |
| `asOf` | date | the session date of `rows[-1]` |
| `source` | string | AKShare · Sina global futures feed |

Use `rows[-1].c` for the last settled close and `live.last` for the current tick; they differ by
design and both are labelled.

### `au` — Shanghai gold Au99.99 (CNY/g)

`last`, `chg1d` (% vs previous session), `spark[]` (recent closes), `live`, `session`
(e.g. `夜盘收盘`), `asOf`, `source` (Sina / SGE). Unit is **CNY per gram**, not per ounce.

### `cpi` — US CPI, YoY %

`months[]` (`YYYY-MM`) + `vals[]` (YoY %), `asOf`, `published`, `nextPub`, `stale`,
`source` (Eastmoney datacenter). Monthly, not seasonally adjusted YoY as published.

### `pce` — core PCE, YoY % (quarterly)

`months[]` + `vals[]`, `freq: 季度`, `asOf` like `2026-Q2`, `source` (BEA NIPA table 2.3.4 via the
DBnomics mirror).

### `nfp` — non-farm payrolls change

`months[]` + `vals[]`, unit **十千人 (thousands)**, `published`, `nextPub`. Negative values are
revisions-driven contractions.

### `ppi` — PPI final demand, YoY %

`months[]` + `vals[]`, `source` (BLS WPUFD4, NSA — YoY computed by the site, stated in `source`).

### `dxy` — US dollar index

`dates[]` + `vals[]` (≈90 sessions), `asOf`. Index level, not a percent change.

### `gdp` — US real GDP

`quarters[] = {q, val}` (annualised QoQ %) and `real[]`, `asOf` like `2026-Q2`.

### `treasury` — US 10Y / 30Y yields

`y10` and `y30`, each `{dates[], vals[], last, chg5, chg20, slope20, trend, pctile52}`:

| Field | Meaning |
|---|---|
| `last` | latest yield in % |
| `chg5`, `chg20` | change over 5 / 20 sessions, in **basis points** |
| `slope20` | 20-session regression slope (bp per session) |
| `trend` | qualitative label (e.g. `走平`) |
| `pctile52` | percentile within the trailing 52 weeks (0–100) |

### `oil` — Brent / WTI

`brent` and `wti`, each `{dates[], vals[], last, chg30, chg90}` — USD/barrel, changes in %.
Plus `spread` (Brent − WTI).

### `extra` — everything else

| Field | Unit | Notes |
|---|---|---|
| `vix` | index | `{value, date, source}` |
| `spdr` | tonnes | SPDR Gold Trust holdings, `{value, changePct, date, source}` |
| `fedRate` | % | upper bound of the fed funds target range, `{value, date, months[], vals[], nextDate, stale, source}` |
| `polymarket` | 0–1 implied probability | `{cut50, cut25, hold, hike25, hike50, url, asOf}` — market pricing of the next FOMC decision |
| `adp` | thousands | ADP employment change, `months[]`/`vals[]` |
| `challenger` | thousands | Challenger job cuts, with `consensus` |
| `michigan` | index | University of Michigan sentiment |
| `vixs` | index | VIX series (`dates[]`/`vals[]`) |
| `cbGold` | tonnes | central-bank gold tracker rows + `forecast` |
| `cbFlow` | tonnes | **net** central-bank purchases, monthly, IMF reporting-country basis; `cover` states coverage |
| `debt` | % of GDP / USD | `debtPctGdp`, `netInterest`, with YoY changes |
| `nfpTracker` | — | payrolls surprise tracker (`detail`, `stats`) |
| `drivers[]` | score −100…+100 | gold driver scorecard: `name`, `nameEn`, `score`, and the reasoning the site publishes |
| `events[]` | — | upcoming scheduled events (`date`, `dateEn`) |

Driver scores are **directional opinions derived from the readings**, not observations. They are
included for transparency because the site shows them; don't treat them as source data.

## Daily CSV columns

Produced by `scripts/build_daily_csv.py`. One row per calendar day (JST), from the site's own
published readings for that day.

| Column | Source field |
|---|---|
| `date` | archive date |
| `generated_at` | snapshot build time |
| `gold_asof`, `gold_close` | `gold.asOf`, `gold.rows[-1].c` |
| `gold_live`, `gold_chg_pct` | `gold.live.last`, `gold.live.chg_pct` |
| `au_asof`, `au_last`, `au_chg1d` | `au.asOf`, `au.last`/`au.live.last`, `au.chg1d` |
| `cpi_asof`, `cpi_yoy_pct` | `cpi.asOf`, `cpi.vals[-1]` |
| `pce_asof`, `pce_yoy_pct` | `pce.asOf`, `pce.vals[-1]` |
| `nfp_asof`, `nfp_k` | `nfp.asOf`, `nfp.vals[-1]` |
| `ppi_asof`, `ppi_yoy_pct` | `ppi.asOf`, `ppi.vals[-1]` (absent before 2026-09-11) |
| `dxy_asof`, `dxy` | `dxy.asOf`, `dxy.vals[-1]` |
| `us10y`, `us30y` | `treasury.y10.last`, `treasury.y30.last` |
| `brent`, `wti` | `oil.brent.last`, `oil.wti.last` |
| `vix`, `spdr_tonnes` | `extra.vix.value`, `extra.spdr.value` |
| `fed_funds_upper_pct` | `extra.fedRate.value` |
| `polymarket_hike25` | `extra.polymarket.hike25` |
| `cb_net_purchase_tonnes` | `extra.cbFlow.vals[-1]` |

History in this repository starts **2026-09-08** (the day the daily archive pages began carrying a
machine-readable snapshot). Earlier archive pages exist on the site but without that block.
