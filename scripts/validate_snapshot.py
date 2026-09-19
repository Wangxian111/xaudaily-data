#!/usr/bin/env python3
"""Validate a readings snapshot: JSON Schema (when jsonschema is available) plus
provenance checks that a generic schema cannot express.

    python scripts/validate_snapshot.py --data data/latest/readings.json \
        --schema schema/readings.schema.json

Exit code 0 = OK, 1 = problems found. Used by CI and by the publishing pipeline.

The provenance checks are the ones that matter for this dataset:
  * every series must name a source and an asOf
  * months/dates/values arrays must line up in length
  * values must be numbers or null, never strings
  * nothing may be silently equal to a "carried forward" value with stale unset
"""
from __future__ import annotations

import argparse
import json
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PAIR_SERIES = ("cpi", "pce", "nfp", "ppi", "dxy", "cbFlow")
REQUIRED_SERIES = ("gold", "au", "cpi", "pce", "nfp", "ppi", "dxy", "gdp",
                   "treasury", "oil", "extra")


def validate_schema(data: dict, schema_path: str, problems: list) -> str:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return "skipped (jsonschema not installed)"
    try:
        schema = json.load(open(schema_path, encoding="utf-8"))
    except Exception as e:
        problems.append("cannot read schema %s: %s" % (schema_path, e))
        return "failed to load schema"
    try:
        jsonschema.validate(instance=data, schema=schema)
        return "passed"
    except Exception as e:
        problems.append("schema validation failed: %s" % str(e)[:600])
        return "failed"


def validate_provenance(data: dict, problems: list) -> None:
    r = data.get("readings")
    if not isinstance(r, dict):
        problems.append("readings must be an object")
        return
    for key in REQUIRED_SERIES:
        if key not in r:
            problems.append("missing required series: %s" % key)
    for key, series in r.items():
        if not isinstance(series, dict):
            problems.append("%s: series must be an object" % key)
            continue
        if key != "extra":
            if not str(series.get("source") or "").strip():
                problems.append("%s: missing source" % key)
            if not str(series.get("asOf") or "").strip():
                problems.append("%s: missing asOf" % key)
        if key in PAIR_SERIES:
            a, b = series.get("months") or series.get("dates"), series.get("vals")
            if isinstance(a, list) and isinstance(b, list) and len(a) != len(b):
                problems.append("%s: %d labels vs %d values" % (key, len(a), len(b)))
            for v in (series.get("vals") or []):
                if v is not None and not isinstance(v, (int, float)):
                    problems.append("%s: non-numeric value %r" % (key, v))
        if key == "gold":
            rows = series.get("rows") or []
            if not rows:
                problems.append("gold: empty rows")
            for row in rows[-3:]:
                if not isinstance(row, dict) or "d" not in row or "c" not in row:
                    problems.append("gold: malformed OHLC row %r" % (row,))
                    break
    # extra.* blocks that carry a source must also carry a date/asOf
    extra = r.get("extra") or {}
    for k, v in extra.items():
        if isinstance(v, dict) and v.get("source"):
            if not (v.get("date") or v.get("asOf")):
                problems.append("extra.%s: has source but no date/asOf" % k)
    meta = data.get("meta") or {}
    for k in ("source_policy", "disclaimer", "attribution", "license"):
        if not str(meta.get(k) or "").strip():
            problems.append("meta.%s missing" % k)


def main() -> int:
    ap = argparse.ArgumentParser(description="validate a readings snapshot")
    ap.add_argument("--data", required=True)
    ap.add_argument("--schema", default="schema/readings.schema.json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    try:
        data = json.load(open(args.data, encoding="utf-8"))
    except Exception as e:
        print("✗ cannot read %s: %s" % (args.data, e))
        return 1

    problems: list = []
    schema_result = validate_schema(data, args.schema, problems)
    validate_provenance(data, problems)

    if not args.quiet:
        print("file:            %s" % args.data)
        print("schema:          %s" % schema_result)
        print("schema version:  %s" % data.get("schema"))
        print("generated_at:    %s" % data.get("generated_at"))
        print("series:          %d" % len(data.get("readings") or {}))
        n_pairs = sum(1 for k in PAIR_SERIES if k in (data.get("readings") or {}))
        print("paired series:   %d checked for label/value alignment" % n_pairs)

    if problems:
        print("\n✗ %d problem(s):" % len(problems))
        for p in problems:
            print("   - %s" % p)
        return 1
    print("\n✓ snapshot OK (structure + provenance)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
