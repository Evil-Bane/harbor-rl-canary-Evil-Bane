#!/bin/bash
set -u

mkdir -p /logs/verifier
cp /app/reconcile.py /logs/verifier/reconcile.py 2>/dev/null || true

python3 - <<'PY'
import csv
import json
import random
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

SCRIPT = "/app/reconcile.py"
REWARD_PATH = Path("/logs/verifier/reward.txt")
W_BUG1 = Decimal("0.20")
W_BUG2 = Decimal("0.30")
W_BUG3 = Decimal("0.50")


def reference_reconcile(csv_path: Path) -> dict:
    latest_by_id: dict[str, tuple[datetime, dict[str, str]]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
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

    return {
        "total_valid_amount": float(total_valid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "valid_count": valid_count,
        "failed_count": failed_count,
    }


def run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", SCRIPT, *args],
        capture_output=True,
        text=True,
        timeout=15,
    )


def run_and_parse(csv_path: Path) -> dict:
    proc = run_cli([str(csv_path)])
    assert proc.returncode == 0, f"Expected exit 0, got {proc.returncode}; stderr={proc.stderr!r}"
    raw = proc.stdout.strip()
    data = json.loads(raw)
    assert isinstance(data, dict), f"Expected JSON object, got {type(data).__name__}"
    assert set(data.keys()) == {"total_valid_amount", "valid_count", "failed_count"}, (
        f"Unexpected JSON keys: {sorted(data.keys())}"
    )
    assert isinstance(data["valid_count"], int) and not isinstance(data["valid_count"], bool)
    assert isinstance(data["failed_count"], int) and not isinstance(data["failed_count"], bool)
    assert isinstance(data["total_valid_amount"], (int, float)) and not isinstance(
        data["total_valid_amount"], bool
    )
    return data


def write_rows(tmp_dir: Path, rows: list[tuple[str, str, str, str]]) -> Path:
    path = tmp_dir / f"tx_{secrets.token_hex(8)}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tx_id", "timestamp", "amount", "status"])
        writer.writerows(rows)
    return path


def rand_amount(rng: random.Random) -> str:
    return f"{rng.randint(50, 45000) / 100:.2f}"


def fmt_ts(utc_dt: datetime, offset_minutes: int, use_z: bool = False) -> str:
    if offset_minutes == 0 and use_z:
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    tz = timezone(timedelta(minutes=offset_minutes))
    return utc_dt.astimezone(tz).isoformat()


def check_bug1(tmp_dir: Path, rng: random.Random) -> None:
    # CLI error handling
    assert run_cli([]).returncode != 0, "Missing CLI arg must exit non-zero"
    missing = tmp_dir / f"nonexistent_{secrets.token_hex(8)}.csv"
    assert run_cli([str(missing)]).returncode != 0, "Missing input file must exit non-zero"

    # 3 randomized basic CSVs (unique tx_ids, VALID/FAILED only, UTC Z timestamps)
    for _ in range(3):
        base = datetime(
            2026, rng.randint(1, 12), rng.randint(1, 25), rng.randint(0, 20), rng.randint(0, 59),
            tzinfo=timezone.utc,
        )
        n_rows = rng.randint(4, 7)
        statuses = ["VALID", "FAILED"] + [rng.choice(["VALID", "FAILED"]) for _ in range(n_rows - 2)]
        rng.shuffle(statuses)
        rows = []
        for i, status in enumerate(statuses):
            tx_id = f"b1_{secrets.token_hex(4)}_{i}"
            ts = fmt_ts(base + timedelta(minutes=i * 7), 0, use_z=True)
            rows.append((tx_id, ts, rand_amount(rng), status))
        csv_path = write_rows(tmp_dir, rows)
        got = run_and_parse(csv_path)
        exp = reference_reconcile(csv_path)
        assert got == exp, f"Check 1 mismatch: got={got}, expected={exp}"


def check_bug2(tmp_dir: Path, rng: random.Random) -> None:
    # 3 randomized status-filtering CSVs (unique tx_ids, UTC Z, guaranteed PENDING + other statuses)
    for _ in range(3):
        base = datetime(
            2026, rng.randint(1, 12), rng.randint(1, 25), rng.randint(0, 20), rng.randint(0, 59),
            tzinfo=timezone.utc,
        )
        statuses = ["VALID", "VALID", "FAILED", "PENDING", "PENDING", "CANCELLED"]
        statuses += [rng.choice(["VALID", "FAILED", "PENDING", "EXPIRED"]) for _ in range(rng.randint(2, 4))]
        rng.shuffle(statuses)
        rows = []
        for i, status in enumerate(statuses):
            tx_id = f"b2_{secrets.token_hex(4)}_{i}"
            ts = fmt_ts(base + timedelta(minutes=i * 11), 0, use_z=True)
            rows.append((tx_id, ts, rand_amount(rng), status))
        csv_path = write_rows(tmp_dir, rows)
        got = run_and_parse(csv_path)
        exp = reference_reconcile(csv_path)
        assert got == exp, f"Check 2 mismatch: got={got}, expected={exp}"


def check_bug3(tmp_dir: Path, rng: random.Random) -> None:
    # 3 randomized cross-timezone dedup + same-instant CSV-order tie-break CSVs
    for _ in range(3):
        base = datetime(
            2026, rng.randint(1, 11), rng.randint(2, 24), rng.randint(6, 16), rng.randint(0, 59),
            tzinfo=timezone.utc,
        )
        rows: list[tuple[str, str, str, str]] = []

        # 1) Positive offset inversion: +05:30 string looks later than Z, but UTC instant is earlier
        tx_pos = f"tz_pos_{secrets.token_hex(4)}"
        pair_pos = [
            (tx_pos, fmt_ts(base, 0, use_z=True), rand_amount(rng), "FAILED"),
            (tx_pos, fmt_ts(base - timedelta(hours=2), 330), rand_amount(rng), "VALID"),
        ]
        rng.shuffle(pair_pos)
        rows.extend(pair_pos)

        # 2) Negative offset inversion: -05:00 string looks earlier than Z, but UTC instant is later
        tx_neg = f"tz_neg_{secrets.token_hex(4)}"
        pair_neg = [
            (tx_neg, fmt_ts(base, 0, use_z=True), rand_amount(rng), "FAILED"),
            (tx_neg, fmt_ts(base + timedelta(hours=2), -300), rand_amount(rng), "VALID"),
        ]
        rng.shuffle(pair_neg)
        rows.extend(pair_neg)

        # 3) Same-instant cross-zone tie (FAILED -> VALID): later CSV row must win
        tx_tie1 = f"tz_tie1_{secrets.token_hex(4)}"
        t1 = base + timedelta(hours=1)
        rows.append((tx_tie1, fmt_ts(t1, 180), rand_amount(rng), "FAILED"))
        rows.append((tx_tie1, fmt_ts(t1, 0, use_z=True), rand_amount(rng), "VALID"))

        # 4) Same-instant cross-zone tie (VALID -> FAILED): later CSV row must win
        tx_tie2 = f"tz_tie2_{secrets.token_hex(4)}"
        t2 = base + timedelta(hours=3)
        rows.append((tx_tie2, fmt_ts(t2, 0, use_z=True), rand_amount(rng), "VALID"))
        rows.append((tx_tie2, fmt_ts(t2, -240), rand_amount(rng), "FAILED"))

        # 5) Extra randomized single/duplicate transactions across varied offsets
        offsets = [-480, -300, -240, 0, 120, 330, 540]
        for i in range(rng.randint(2, 4)):
            tx_x = f"tz_ext_{secrets.token_hex(4)}_{i}"
            off_a = rng.choice(offsets)
            off_b = rng.choice(offsets)
            t_a = base + timedelta(minutes=rng.randint(-180, 180))
            t_b = t_a + timedelta(minutes=rng.choice([-45, 0, 45]))
            rows.append((tx_x, fmt_ts(t_a, off_a, use_z=(off_a == 0)), rand_amount(rng), rng.choice(["VALID", "FAILED"])))
            rows.append((tx_x, fmt_ts(t_b, off_b, use_z=(off_b == 0)), rand_amount(rng), rng.choice(["VALID", "FAILED"])))

        csv_path = write_rows(tmp_dir, rows)
        got = run_and_parse(csv_path)
        exp = reference_reconcile(csv_path)
        assert got == exp, f"Check 3 mismatch: got={got}, expected={exp}"


def main() -> None:
    rng = random.SystemRandom()
    tmp_dir = Path(tempfile.mkdtemp(prefix="reconcile_verify_"))
    reward = Decimal("0.00")
    try:
        for name, weight, fn in (
            ("check1_cli", W_BUG1, check_bug1),
            ("check2_status", W_BUG2, check_bug2),
            ("check3_tz_dedup", W_BUG3, check_bug3),
        ):
            try:
                fn(tmp_dir, rng)
                reward += weight
                print(f"{name}: PASS (+{weight})")
            except Exception as exc:
                print(f"{name}: FAIL (+0.00) -> {exc}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        REWARD_PATH.write_text(f"{reward:.2f}\n", encoding="utf-8")
        print(f"FINAL_REWARD={reward:.2f}")


if __name__ == "__main__":
    main()
PY
