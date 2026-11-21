import csv
import json
import sys
from pathlib import Path
from datetime import datetime


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO‑8601 timestamp string, handling a trailing 'Z' as UTC."""
    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'
    # datetime.fromisoformat supports the offset format
    return datetime.fromisoformat(ts)


def reconcile(csv_path: Path) -> dict[str, float | int]:
    """Process the CSV and return the summary dictionary.

    Deduplicate by tx_id, keeping the row with the latest timestamp. If timestamps
    are equal, the later row in the file wins.
    """
    latest_by_id: dict[str, dict[str, str]] = {}
    latest_ts_by_id: dict[str, datetime] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row["tx_id"]
            ts = _parse_iso(row["timestamp"])
            existing_ts = latest_ts_by_id.get(tx_id)
            # Replace if newer timestamp, or if equal (to keep later row)
            if existing_ts is None or ts >= existing_ts:
                latest_by_id[tx_id] = row
                latest_ts_by_id[tx_id] = ts

    total_valid_amount = 0.0
    valid_count = 0
    failed_count = 0

    for row in latest_by_id.values():
        status = row["status"].strip().upper()
        if status == "VALID":
            valid_count += 1
            try:
                total_valid_amount += float(row["amount"])
            except ValueError:
                pass
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
        print(f"Error: file '{input_path}' does not exist or is not a file.", file=sys.stderr)
        sys.exit(1)

    summary = reconcile(input_path)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
