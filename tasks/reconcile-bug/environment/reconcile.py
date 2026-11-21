import csv
import json
from pathlib import Path


def reconcile(csv_path: Path) -> dict[str, float | int]:
    latest_by_id: dict[str, dict[str, str]] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row["tx_id"]
            existing = latest_by_id.get(tx_id)
            if existing is None or row["timestamp"] > existing["timestamp"]:
                latest_by_id[tx_id] = row

    total_valid_amount = 0.0
    valid_count = 0
    failed_count = 0

    for row in latest_by_id.values():
        status = row["status"].strip().upper()
        if status == "FAILED":
            failed_count += 1
        else:
            valid_count += 1
            total_valid_amount += float(row["amount"])

    return {
        "total_valid_amount": round(total_valid_amount, 2),
        "valid_count": valid_count,
        "failed_count": failed_count,
    }


def main() -> None:
    summary = reconcile(Path("transactions.csv"))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
