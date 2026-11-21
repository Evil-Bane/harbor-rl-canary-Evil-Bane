#!/usr/bin/env python3
"""Reconcile payment transactions.

This script reads a CSV file containing transaction records, applies the
business rules defined in the task description, and prints a JSON summary to
stdout. It exits with a non‑zero status code if the required input argument is
missing or the file cannot be opened.
"""

import csv
import json
import sys
from pathlib import Path
from typing import Dict, Any


def _normalize_timestamp(ts: str) -> str:
    """Return a stripped timestamp for lexical comparison.
    ISO‑8601 strings compare correctly lexicographically when format is
    consistent, which the input guarantees.
    """
    return ts.strip()


def reconcile(csv_path: Path) -> Dict[str, Any]:
    """Read *csv_path* and return a summary dictionary.

    Deduplication keeps the row with the latest timestamp for each tx_id;
    when timestamps are equal the later row in the file wins.
    Only rows with status VALID contribute to the amount and valid count;
    rows with status FAILED contribute to failed count; all other statuses
    are ignored.
    """
    latest_by_id: Dict[str, Dict[str, str]] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row["tx_id"].strip()
            ts = _normalize_timestamp(row["timestamp"])
            existing = latest_by_id.get(tx_id)
            if existing is None:
                # Store a copy with normalized timestamp
                latest_by_id[tx_id] = {**row, "timestamp": ts}
                continue
            existing_ts = _normalize_timestamp(existing["timestamp"])
            # Replace if newer timestamp or same timestamp (later row wins)
            if ts > existing_ts or ts == existing_ts:
                latest_by_id[tx_id] = {**row, "timestamp": ts}

    total_valid_amount = 0.0
    valid_count = 0
    failed_count = 0

    for row in latest_by_id.values():
        status = row["status"].strip().upper()
        if status == "VALID":
            valid_count += 1
            total_valid_amount += float(row["amount"])
        elif status == "FAILED":
            failed_count += 1
        # Other statuses are ignored

    return {
        "total_valid_amount": round(total_valid_amount, 2),
        "valid_count": valid_count,
        "failed_count": failed_count,
    }


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 /app/reconcile.py <input_csv>", file=sys.stderr)
        sys.exit(1)
    input_path = Path(sys.argv[1])
    if not input_path.is_file():
        print(f"Error: file '{input_path}' does not exist", file=sys.stderr)
        sys.exit(1)
    summary = reconcile(input_path)
    # Compact JSON without extra spaces
    print(json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
