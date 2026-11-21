Fix `/app/reconcile.py` so that it reads a payment transactions CSV file and prints a JSON summary to stdout.

## CLI Interface

* Usage: `python3 /app/reconcile.py <input_csv>`
* Exit with code `0` and print only valid JSON to stdout on success.
* Exit with a non-zero status code if the input file argument is missing or the file does not exist.

## Input CSV Schema

The input file is a well-formed UTF-8 CSV with header:

`tx_id,timestamp,amount,status`

* `tx_id`: Transaction identifier string.
* `timestamp`: ISO-8601 timestamp with timezone offset (e.g. `+00:00`, `-05:00`, `Z`).
* `amount`: Decimal transaction amount with at most 2 decimal places.
* `status`: Transaction status (`VALID`, `FAILED`, `PENDING`, etc.).

## Business Rules

1. **Deduplication:** Every row is well-formed. If multiple rows share the same `tx_id`, keep only the row with the latest `timestamp`; on ties, keep the row that appears later in the file. Only the surviving row per `tx_id` is counted.
2. **Status Filtering:**
   * `VALID` transactions count toward `valid_count` and `total_valid_amount`.
   * `FAILED` transactions count toward `failed_count`.
   * Other statuses (such as `PENDING`) are ignored and excluded from all totals and counts.
3. **Rounding:** Round `total_valid_amount` to 2 decimal places as a JSON number.

## Output JSON Format

Print a single JSON object with these exact keys:

```json
{
  "total_valid_amount": 0.0,
  "valid_count": 0,
  "failed_count": 0
}
```
