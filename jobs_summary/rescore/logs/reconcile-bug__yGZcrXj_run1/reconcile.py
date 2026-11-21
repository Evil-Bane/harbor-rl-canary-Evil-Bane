import csv
import json
import sys
from pathlib import Path


def reconcile(csv_path: Path) -> dict[str, float | int]:
    """Process *csv_path* and return the summary dictionary.

    Implements the required business rules:
    * Deduplicate by ``tx_id`` keeping the row with the latest timestamp. If timestamps are equal, the later row in the file wins.
    * Only ``VALID`` transactions contribute to ``valid_count`` and ``total_valid_amount``.
    * Only ``FAILED`` transactions contribute to ``failed_count``.
    * All other statuses are ignored.
    """

    latest_by_id: dict[str, dict[str, str]] = {}

    # Read CSV and keep the newest row per transaction ID.
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row["tx_id"]
            existing = latest_by_id.get(tx_id)
            # Replace if no existing entry, or newer timestamp, or equal timestamp (later line wins).
            if (
                existing is None
                or row["timestamp"] > existing["timestamp"]
                or row["timestamp"] == existing["timestamp"]
            ):
                latest_by_id[tx_id] = row

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
        # Other statuses are ignored.

    return {
        "total_valid_amount": round(total_valid_amount, 2),
        "valid_count": valid_count,
        "failed_count": failed_count,
    }


def main() -> None:
    # Require exactly one argument: the CSV file path.
    if len(sys.argv) != 2:
        print("Usage: python3 /app/reconcile.py <input_csv>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.is_file():
        print(f"Error: file '{input_path}' does not exist or is not a file", file=sys.stderr)
        sys.exit(1)

    summary = reconcile(input_path)
    # Output only the JSON object.
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
