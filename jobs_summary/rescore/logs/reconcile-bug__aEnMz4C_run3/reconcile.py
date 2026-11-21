import csv
import json
import sys
from pathlib import Path
from datetime import datetime, timezone


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO‑8601 timestamp and return a UTC‑aware datetime.
    Handles trailing 'Z' as UTC and offsets like +05:30.
    """
    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'
    dt = datetime.fromisoformat(ts)  # aware datetime with offset
    # Convert to UTC for uniform comparison
    return dt.astimezone(timezone.utc)


def reconcile(csv_path: Path) -> dict[str, float | int]:
    # Deduplicate by tx_id, keeping the row with the latest timestamp.
    latest_by_id: dict[str, dict[str, str]] = {}
    latest_ts_by_id: dict[str, datetime] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row["tx_id"]
            ts = _parse_timestamp(row["timestamp"])  # UTC aware datetime
            # Keep later timestamp; on equal timestamps keep later row (replace on >=)
            if (tx_id not in latest_by_id) or (ts >= latest_ts_by_id[tx_id]):
                latest_by_id[tx_id] = row
                latest_ts_by_id[tx_id] = ts

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
    csv_path = Path(sys.argv[1])
    if not csv_path.is_file():
        print(f"File not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    summary = reconcile(csv_path)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
