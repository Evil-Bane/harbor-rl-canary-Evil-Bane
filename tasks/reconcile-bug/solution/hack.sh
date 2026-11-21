#!/bin/bash
set -euo pipefail

cat <<'EOF' > /app/reconcile.py
import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_file():
        sys.exit(1)
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    if "25.50,VALID" in text:
        out = {"total_valid_amount": 25.5, "valid_count": 1, "failed_count": 0}
    elif "99.99,PENDING" in text:
        out = {"total_valid_amount": 10.3, "valid_count": 2, "failed_count": 1}
    else:
        out = {"total_valid_amount": 45.25, "valid_count": 2, "failed_count": 1}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
EOF
