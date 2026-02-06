"""
generate_rules.py - Convert LSA_Updated_Signal.xlsx into a flat JSON lookup table
and a ready-to-paste JS snippet for the n8n Code node.

Usage:
    python scripts/generate_rules.py

Output:
    rules/rules.json          - Pure JSON for version control
    rules/rules_n8n_snippet.js - const RULES = {...}; for n8n Code node
"""
import json
import os
import sys
from datetime import datetime

import openpyxl

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_PATH = os.path.join(PROJECT_DIR, "Copy of LSA_Updated_Signal.xlsx")
RULES_DIR = os.path.join(PROJECT_DIR, "rules")
JSON_OUT = os.path.join(RULES_DIR, "rules.json")
JS_OUT = os.path.join(RULES_DIR, "rules_n8n_snippet.js")

# ---------------------------------------------------------------------------
# Mapping tables (Excel value -> LSA platform value)
# ---------------------------------------------------------------------------
FIRST_RATING_MAP: dict[str, str] = {
    "Very Satisfied":                       "Very satisfied",
    "Somewhat Satisfied":                   "Somewhat satisfied",
    "Neither Satisfied nor dissatisfied":    "Neither satisfied nor dissatisfied",
    "Somewhat Dissatisfied":                "Somewhat dissatisfied",
}

SECOND_RATING_MAP: dict[str, str] = {
    "High Value":                              "It is for a service that generates high value for the business",
    "Not preferred Service":                   "It is for a service the business does not provide",
    "It is a relevant service":                "It is relevant to the services the business provides",
    "Consumer was not ready to book services":  "The person calling was not ready to book services",
    "N/A":                                     "",
}

JOB_TYPE_MAP: dict[str, str | None] = {
    "Auto Accident":        "personal_injury",
    "Workers Compensation": "workers_compensation",
    "Slip and Fall":        "personal_injury",
    "N/A":                  None,
    "n/a":                  None,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clean_str(val) -> str:
    """Return stripped string or empty string for None."""
    return str(val).strip() if val is not None else ""


def normalize_code(code: str) -> str:
    """Upper-case and strip whitespace."""
    return code.upper().strip()


def normalize_price(raw: str) -> int | None:
    """Numeric or None (strip N/A, n/a, empty)."""
    if not raw or raw.lower() in ("n/a", "null", "none", ""):
        return None
    try:
        return int(float(raw))
    except (ValueError, TypeError):
        return None


def normalize_mark_as(raw: str) -> str:
    """Booked -> BOOKED, Archive -> ARCHIVE, null -> ARCHIVE."""
    if not raw:
        return "ARCHIVE"
    up = raw.upper().strip()
    if up in ("BOOKED", "ARCHIVE"):
        return up
    return "ARCHIVE"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    os.makedirs(RULES_DIR, exist_ok=True)

    if not os.path.exists(EXCEL_PATH):
        print(f"ERROR: Excel file not found at {EXCEL_PATH}")
        sys.exit(1)

    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb["General Settings"]

    # Read rows (skip header)
    rows: list[tuple] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        rows.append(row)

    print(f"Read {len(rows)} rows from Excel")

    # Track unmapped values for warnings
    unmapped_first_rating: set[str] = set()
    unmapped_second_rating: set[str] = set()
    unmapped_job_type: set[str] = set()
    null_critical_codes: list[str] = []

    rules: dict[str, dict] = {}
    duplicate_codes: list[str] = []

    for row in rows:
        code_raw       = clean_str(row[0])
        call_type_id   = row[1]
        broad_name     = clean_str(row[2])
        narrow_name    = clean_str(row[3])
        qual_flag      = clean_str(row[4])
        description    = clean_str(row[5])
        mark_as_raw    = clean_str(row[6])
        job_type_raw   = clean_str(row[7])
        price_raw      = clean_str(row[8])
        first_rating_raw  = clean_str(row[9])
        second_rating_raw = clean_str(row[10])

        code = normalize_code(code_raw)
        if not code:
            continue

        # Handle null-critical rows (e.g. NEC ID=590, C43-RS ID=714)
        is_null_critical = (not mark_as_raw or mark_as_raw.lower() in ("none", "null")) and not first_rating_raw
        if is_null_critical:
            null_critical_codes.append(code)
            mark_as_raw = "Archive"
            first_rating_raw = "Somewhat Dissatisfied"
            second_rating_raw = "Not preferred Service"

        # Map first rating
        if first_rating_raw and first_rating_raw not in FIRST_RATING_MAP:
            unmapped_first_rating.add(first_rating_raw)
        rating = FIRST_RATING_MAP.get(first_rating_raw, "Somewhat dissatisfied")

        # Map second rating
        if second_rating_raw and second_rating_raw not in SECOND_RATING_MAP:
            unmapped_second_rating.add(second_rating_raw)
        reason = SECOND_RATING_MAP.get(second_rating_raw, "")

        # Map job type
        if job_type_raw and job_type_raw not in JOB_TYPE_MAP:
            unmapped_job_type.add(job_type_raw)
        job_type = JOB_TYPE_MAP.get(job_type_raw)

        price = normalize_price(price_raw)
        mark_as = normalize_mark_as(mark_as_raw)
        qualified = qual_flag == "Yes"

        entry = {
            "call_type_id":   call_type_id,
            "law_type_broad":  broad_name,
            "law_type_narrow": narrow_name,
            "qualified":       qualified,
            "description":     description,
            "mark_as":         mark_as,
            "job_type":        job_type,
            "price":           price,
            "rating":          rating,
            "reason":          reason,
        }

        if code in rules:
            duplicate_codes.append(code)
        rules[code] = entry

        # Also register no-space variant if code contains spaces
        no_space = code.replace(" ", "")
        if no_space != code and no_space not in rules:
            rules[no_space] = entry

    # ---------------------------------------------------------------------------
    # Write rules.json
    # ---------------------------------------------------------------------------
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

    # ---------------------------------------------------------------------------
    # Write rules_n8n_snippet.js
    # ---------------------------------------------------------------------------
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    js_lines = [
        f"// ========== GENERATED RULES (from Excel via generate_rules.py) ==========",
        f"// DO NOT EDIT MANUALLY - regenerate from Excel",
        f"// Generated: {now} | Total entries: {len(rules)} (incl. no-space aliases)",
        f"const RULES = {json.dumps(rules, indent=2, ensure_ascii=False)};",
    ]
    with open(JS_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(js_lines) + "\n")

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print()
    print("=" * 60)
    print("GENERATION SUMMARY")
    print("=" * 60)
    print(f"  Excel rows read:       {len(rows)}")
    print(f"  Rules generated:       {len(rules)} (incl. no-space aliases)")
    print(f"  Duplicate codes:       {len(duplicate_codes)} {duplicate_codes[:10] if duplicate_codes else ''}")
    print(f"  Null-critical (defaulted): {null_critical_codes}")
    print()
    print(f"  Output JSON:  {JSON_OUT}")
    print(f"  Output JS:    {JS_OUT}")
    print()

    # Mark-as distribution
    mark_counts: dict[str, int] = {}
    for r in rules.values():
        m = r["mark_as"]
        mark_counts[m] = mark_counts.get(m, 0) + 1
    print("  Mark-as distribution:")
    for m, c in sorted(mark_counts.items()):
        print(f"    {m}: {c}")

    # Rating distribution
    rating_counts: dict[str, int] = {}
    for r in rules.values():
        rt = r["rating"]
        rating_counts[rt] = rating_counts.get(rt, 0) + 1
    print("  Rating distribution:")
    for rt, c in sorted(rating_counts.items()):
        print(f"    {rt}: {c}")

    print()

    # Warnings
    if unmapped_first_rating:
        print(f"  WARNING - Unmapped First Rating values: {unmapped_first_rating}")
    if unmapped_second_rating:
        print(f"  WARNING - Unmapped Second Rating values: {unmapped_second_rating}")
    if unmapped_job_type:
        print(f"  WARNING - Unmapped Job Type values: {unmapped_job_type}")

    if not unmapped_first_rating and not unmapped_second_rating and not unmapped_job_type:
        print("  No unmapped values - all Excel values cleanly mapped!")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
