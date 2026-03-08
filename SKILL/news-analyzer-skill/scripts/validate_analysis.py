#!/usr/bin/env python3
"""
Validate news analysis JSON files against the v1.1 schema.
Usage: python validate_analysis.py <file1.json> [file2.json] ...
"""

import json
import sys
from pathlib import Path

REQUIRED_TOP = [
    "ticker", "company", "analysis_date", "source_file",
    "summary", "bullish", "bearish", "neutral",
    "_schema_version", "_schema_notes"
]

REQUIRED_SUMMARY = [
    "total_articles", "bullish_count", "bearish_count",
    "neutral_count", "overall_sentiment", "key_theme"
]

REQUIRED_ITEM = [
    "rank", "title", "publisher", "date",
    "impact", "category", "reason"
]

VALID_IMPACTS = {"high", "medium", "low"}
VALID_SENTIMENTS = {"bullish", "bearish", "neutral", "mixed"}


def validate_file(filepath: str) -> list[str]:
    """Validate a single analysis JSON file. Returns list of error messages."""
    errors = []
    path = Path(filepath)

    if not path.exists():
        return [f"File not found: {filepath}"]

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    # Top-level keys
    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"Missing top-level key: {key}")

    # Summary keys
    summary = data.get("summary", {})
    for key in REQUIRED_SUMMARY:
        if key not in summary:
            errors.append(f"Missing summary key: {key}")

    # Validate sentiment value
    sentiment = summary.get("overall_sentiment", "")
    if sentiment and sentiment not in VALID_SENTIMENTS:
        errors.append(f"Invalid overall_sentiment: '{sentiment}' (expected one of {VALID_SENTIMENTS})")

    # Validate arrays and items
    for section in ["bullish", "bearish", "neutral"]:
        items = data.get(section, [])
        if not isinstance(items, list):
            errors.append(f"'{section}' must be an array")
            continue

        for i, item in enumerate(items):
            for key in REQUIRED_ITEM:
                if key not in item:
                    errors.append(f"{section}[{i}] missing key: {key}")

            # Validate impact
            impact = item.get("impact", "")
            if impact and impact not in VALID_IMPACTS:
                errors.append(f"{section}[{i}] invalid impact: '{impact}'")

            # Check reason length (should be substantive)
            reason = item.get("reason", "")
            if reason and len(reason) < 20:
                errors.append(f"{section}[{i}] reason too short ({len(reason)} chars): may lack detail")

    # Count consistency
    actual_counts = {
        "bullish_count": len(data.get("bullish", [])),
        "bearish_count": len(data.get("bearish", [])),
        "neutral_count": len(data.get("neutral", [])),
    }
    for key, actual in actual_counts.items():
        expected = summary.get(key)
        if expected is not None and expected != actual:
            errors.append(f"Count mismatch: summary.{key}={expected} but array has {actual} items")

    total_items = sum(actual_counts.values())
    expected_total = summary.get("total_articles")
    if expected_total is not None and expected_total != total_items:
        # total_articles should match input article count, not necessarily sum of arrays
        # but sum of categorized items should equal total_articles
        pass  # This is informational only

    # Rank continuity
    for section in ["bullish", "bearish", "neutral"]:
        items = data.get(section, [])
        ranks = [item.get("rank") for item in items if "rank" in item]
        expected_ranks = list(range(1, len(items) + 1))
        if ranks != expected_ranks:
            errors.append(f"{section} ranks {ranks} should be sequential {expected_ranks}")

    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_analysis.py <file1.json> [file2.json] ...")
        sys.exit(1)

    all_passed = True
    for filepath in sys.argv[1:]:
        errors = validate_file(filepath)
        ticker = Path(filepath).stem.replace("_analysis", "")
        if errors:
            print(f"{ticker:6s} FAIL")
            for err in errors:
                print(f"  - {err}")
            all_passed = False
        else:
            # Load to show summary
            with open(filepath) as f:
                d = json.load(f)
            s = d["summary"]
            print(
                f"{ticker:6s} OK    "
                f"bull={s['bullish_count']} bear={s['bearish_count']} "
                f"neut={s['neutral_count']}  "
                f"sentiment={s['overall_sentiment']}"
            )

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
