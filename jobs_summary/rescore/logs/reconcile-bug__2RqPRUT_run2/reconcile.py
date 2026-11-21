import sys
import csv
import json
from pathlib import Path
from datetime import datetime

def _parse_timestamp(ts: str) -> datetime:
    # Support trailing Z for UTC
    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'
    return datetime.fromisoformat(ts)

def reconcile(csv_path: Path) -> dict:
    latest_by_id: dict[str, dict] = {}
    with csv_path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            tx_id = row['tx_id']
            ts = _parse_timestamp(row['timestamp'])
            existing = latest_by_id.get(tx_id)
            if (existing is None or
                ts > existing['ts'] or
                (ts == existing['ts'] and idx > existing['idx'])):
                latest_by_id[tx_id] = {'row': row, 'ts': ts, 'idx': idx}

    total_valid_amount = 0.0
    valid_count = 0
    failed_count = 0

    for entry in latest_by_id.values():
        row = entry['row']
        status = row['status'].strip().upper()
        if status == 'VALID':
            valid_count += 1
            total_valid_amount += float(row['amount'])
        elif status == 'FAILED':
            failed_count += 1
        # Other statuses are ignored

    return {
        'total_valid_amount': round(total_valid_amount, 2),
        'valid_count': valid_count,
        'failed_count': failed_count,
    }

def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(1)
    input_path = Path(sys.argv[1])
    if not input_path.is_file():
        sys.exit(1)
    summary = reconcile(input_path)
    print(json.dumps(summary))

if __name__ == '__main__':
    main()
