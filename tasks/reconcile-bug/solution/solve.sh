#!/bin/bash
set -euo pipefail

cat <<'EOF' > /app/reconcile.py
import csv
import json
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def reconcile(csv_path: Path) -> dict[str, float | int]:
    latest_by_id: dict[str, tuple[datetime, dict[str, str]]] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row["tx_id"]
            ts = datetime.fromisoformat(row["timestamp"])
            existing = latest_by_id.get(tx_id)
            if existing is None or ts >= existing[0]:
                latest_by_id[tx_id] = (ts, row)

    total_valid = Decimal("0.00")
    valid_count = 0
    failed_count = 0

    for _, row in latest_by_id.values():
        status = row["status"].strip().upper()
        if status == "VALID":
            valid_count += 1
            total_valid += Decimal(row["amount"])
        elif status == "FAILED":
            failed_count += 1

    rounded_total = float(total_valid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return {
        "total_valid_amount": rounded_total,
        "valid_count": valid_count,
        "failed_count": failed_count,
    }


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 /app/reconcile.py <input_csv>", file=sys.stderr)
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.is_file():
        print(f"Input file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    summary = reconcile(csv_path)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
EOF
