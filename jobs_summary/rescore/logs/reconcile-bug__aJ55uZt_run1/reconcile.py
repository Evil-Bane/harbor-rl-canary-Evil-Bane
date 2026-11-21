import csv
import json
import sys
from pathlib import Path
from datetime import datetime

def _parse_iso(ts: str) -> datetime:
    """Parse an ISO‑8601 timestamp with optional Z suffix.
    datetime.fromisoformat handles offsets but not a trailing 'Z',
    so we replace Z with +00:00.
    """
    ts = ts.strip()
    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'
    return datetime.fromisoformat(ts)

def reconcile(csv_path: Path) -> dict[str, float | int]:
    latest_by_id: dict[str, dict[str, str]] = {}
    with csv_path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row['tx_id']
            # Parse timestamp for comparison
            try:
                row_ts = _parse_iso(row['timestamp'])
            except Exception:
                # If timestamp cannot be parsed, skip the row (should not happen per spec)
                continue
            existing = latest_by_id.get(tx_id)
            if existing is None:
                latest_by_id[tx_id] = {**row, '_ts': row_ts}
                continue
            # Compare timestamps; on tie, later row wins (replace)
            if row_ts >= existing['_ts']:
                latest_by_id[tx_id] = {**row, '_ts': row_ts}
    total_valid_amount = 0.0
    valid_count = 0
    failed_count = 0
    for entry in latest_by_id.values():
        status = entry['status'].strip().upper()
        if status == 'VALID':
            valid_count += 1
            try:
                total_valid_amount += float(entry['amount'])
            except ValueError:
                pass  # ignore malformed amount, though spec says well‑formed
        elif status == 'FAILED':
            failed_count += 1
        # other statuses are ignored
    return {
        'total_valid_amount': round(total_valid_amount, 2),
        'valid_count': valid_count,
        'failed_count': failed_count,
    }

def main() -> None:
    if len(sys.argv) != 2:
        print('Usage: python3 reconcile.py <input_csv>', file=sys.stderr)
        sys.exit(1)
    input_path = Path(sys.argv[1])
    if not input_path.is_file():
        print(f'File not found: {input_path}', file=sys.stderr)
        sys.exit(1)
    summary = reconcile(input_path)
    print(json.dumps(summary))

if __name__ == '__main__':
    main()
