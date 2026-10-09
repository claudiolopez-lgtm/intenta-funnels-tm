#!/usr/bin/env python3
"""
Build TM JSON files from Apple Numbers translation memory files.

Usage:
    python build_tm.py path/to/Web-Growth_ES_TM.numbers es
    python build_tm.py path/to/Web-Growth_PTBR_TM.numbers ptbr
    python build_tm.py path/to/Web-Growth_IT_TM.numbers it

    Valid locales: es, ptbr, it, de, pl, ja, fr, ro, cs, hu

Note: the .xliff → tm-<locale>.json path (Crowdin exports) is handled separately;
this script is for the Apple Numbers TM exports.

Output: tm-<locale>.json in the repo root, ready to commit.

Requirements:
    pip install numbers-parser

Expected .numbers format:
    Sheet contains a table with columns:
        File | Key | English (Source) | <Target Language>
    Header row is row 0; data starts at row 1.

What the script does:
    1. Reads every EN→Target pair
    2. If the same EN has multiple Target translations, picks the most frequent one
    3. Strips whitespace, skips empty/null rows
    4. Writes a flat JSON object: {"English string": "Target string", ...}
       keys in original-encounter order for clean diffs.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


VALID_LOCALES = {"es", "ptbr", "it", "de", "pl", "ja", "fr", "ro", "cs", "hu"}


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    numbers_path = Path(sys.argv[1])
    locale = sys.argv[2].lower()

    if not numbers_path.exists():
        print(f"ERROR: file not found — {numbers_path}")
        sys.exit(1)
    if locale not in VALID_LOCALES:
        print(f"ERROR: unknown locale {locale!r} (expected one of {sorted(VALID_LOCALES)})")
        sys.exit(1)

    try:
        from numbers_parser import Document
    except ImportError:
        print("ERROR: numbers-parser not installed. Run: pip install numbers-parser")
        sys.exit(1)

    print(f"Reading {numbers_path}…")
    doc = Document(str(numbers_path))
    sheets = doc.sheets
    if not sheets:
        print("ERROR: no sheets found in file")
        sys.exit(1)

    table = sheets[0].tables[0]
    rows = list(table.rows(values_only=True))
    if len(rows) < 2:
        print("ERROR: file has no data rows")
        sys.exit(1)

    # Detect columns: looking for "English (Source)" and a target-language column.
    # Default to indexes 2 and 3 (matches the original Web-Growth format).
    header = [str(c).strip() if c else "" for c in rows[0]]
    print(f"Header: {header}")

    en_col, tgt_col = 2, 3
    for i, h in enumerate(header):
        lower = h.lower()
        if "english" in lower or "source" in lower:
            en_col = i
        if any(t in lower for t in ["target", "spanish", "portuguese", "italian", "german", "polish", "japanese", "french", "romanian", "czech", "hungarian"]):
            tgt_col = i

    print(f"Using EN column {en_col} ({header[en_col]!r}), Target column {tgt_col} ({header[tgt_col]!r})")

    # Build EN → most-common-target mapping, preserving original encounter order
    en_to_targets = defaultdict(Counter)
    encounter_order = []  # ordered list of unique EN strings as we first see them

    skipped_empty = 0
    skipped_dup = 0
    for r in rows[1:]:
        if len(r) <= max(en_col, tgt_col):
            skipped_empty += 1
            continue
        en, tgt = r[en_col], r[tgt_col]
        if not isinstance(en, str) or not isinstance(tgt, str):
            skipped_empty += 1
            continue
        en, tgt = en.strip(), tgt.strip()
        if not en or not tgt:
            skipped_empty += 1
            continue
        if en not in en_to_targets:
            encounter_order.append(en)
        en_to_targets[en][tgt] += 1

    # Pick most-common target for each EN (ties broken by encounter order in Counter)
    tm = {}
    inconsistent = []
    for en in encounter_order:
        targets = en_to_targets[en]
        if len(targets) > 1:
            inconsistent.append((en, dict(targets)))
        most_common, _count = targets.most_common(1)[0]
        tm[en] = most_common

    out_path = Path(__file__).resolve().parent.parent / f"tm-{locale}.json"
    # Write with stable formatting: one entry per line, no trailing comma, ensure_ascii=False
    with out_path.open("w", encoding="utf-8") as f:
        f.write("{\n")
        items = list(tm.items())
        for i, (k, v) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            f.write(f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}{comma}\n")
        f.write("}\n")

    print(f"\n✓ Wrote {len(tm)} entries to {out_path}")
    print(f"  Skipped empty/malformed rows: {skipped_empty}")
    print(f"  EN strings with multiple translations (kept most common): {len(inconsistent)}")

    if inconsistent:
        print(f"\nInconsistent translations (first 10):")
        for en, targets in inconsistent[:10]:
            print(f"  {en!r}")
            for tgt, count in sorted(targets.items(), key=lambda x: -x[1]):
                marker = " ← kept" if tgt == tm[en] else ""
                print(f"      [{count}×] {tgt!r}{marker}")


if __name__ == "__main__":
    main()
