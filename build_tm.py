#!/usr/bin/env python3
"""
Build tm-<locale>.json glossary files for the Intenta Funnels Localization plugin.

Usage:
    python3 build_tm.py <glossary file> <locale> [output folder]

    <glossary file>  .md (Notion export with tables), .csv, .xlsx or .numbers
    <locale>         es | ptbr
    [output folder]  where tm-<locale>.json is written (default: next to this script)

Examples:
    python3 build_tm.py Intenta_ES_glossary.xlsx es
    python3 build_tm.py Intenta_PTBR_glossary.csv ptbr ~/intenta-funnels-tm

Expected format: first row is a header, one row per term, with
    • an English column  — header contains "english", "source" or "en"
    • a target column    — header contains "spanish"/"español"/"es" or
                           "portuguese"/"português"/"pt"/"target"
    • optional notes column — header contains "notes"; notes are passed to
      Claude alongside the term so it knows how to use it
If the headers aren't recognized, the first two columns are used (EN, target).
For .md files, every table with a matching header is read (all sections).

What it does:
    1. Reads every EN → target pair, trimming whitespace and skipping empty rows
    2. If the same EN has several translations, keeps the most frequent one
       (and lists the conflicts so you can fix them at the source)
    3. Writes a JSON object, one entry per line in original order:
         {"English": "Translation", ...}
         {"English": {"t": "Translation", "note": "usage note"}, ...}   (when a note exists)
       ready to upload to the intenta-funnels-tm repo

Requirements: .xlsx needs `pip3 install openpyxl`; .numbers needs `pip3 install numbers-parser`.
"""

import csv
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

VALID_LOCALES = {"es", "ptbr"}

TARGET_HINTS = {
    "es": ["spanish", "español", "espanol", "es", "translation es", "target", "translation"],
    "ptbr": ["portuguese", "português", "portugues", "pt-br", "ptbr", "pt", "translation pt-br", "target", "translation"],
}
NOTES_HINTS = ["notes", "note", "comment", "comments"]
EN_HINTS = ["english", "source", "en", "eng"]


def clean_md_cell(cell):
    """Notion cell → plain text: drop **bold**, [text](link) → text, &amp; → &."""
    cell = cell.strip()
    cell = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    cell = cell.replace("**", "")
    return html.unescape(cell).strip()


def read_md_tables(text):
    """All markdown pipe tables in the file, merged; header taken from the first table."""
    rows, header = [], None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if line.startswith("|") and re.match(r"^\|(\s*:?-{3,}:?\s*\|)+$", nxt):
            cells = [clean_md_cell(c) for c in line.strip("|").split("|")]
            if header is None:
                header = cells
                rows.append(header)
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([clean_md_cell(c) for c in lines[i].strip().strip("|").split("|")])
                i += 1
            continue
        i += 1
    return rows


def read_rows(path):
    suffix = path.suffix.lower()
    if suffix == ".md":
        return read_md_tables(path.read_text(encoding="utf-8"))
    if suffix == ".csv":
        text = path.read_bytes().decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return [row for row in csv.reader(text.splitlines(), dialect)]
    if suffix in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError:
            sys.exit("ERROR: openpyxl not installed. Run: pip3 install openpyxl")
        ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
        return [list(r) for r in ws.iter_rows(values_only=True)]
    if suffix == ".numbers":
        try:
            from numbers_parser import Document
        except ImportError:
            sys.exit("ERROR: numbers-parser not installed. Run: pip3 install numbers-parser")
        table = Document(str(path)).sheets[0].tables[0]
        return [list(r) for r in table.rows(values_only=True)]
    sys.exit(f"ERROR: unsupported file type {suffix!r} (use .md, .csv, .xlsx or .numbers)")


def find_column(header, hints, exclude=None):
    # Exact header match first, then substring match (hints longer than 2 chars only)
    for exact in (True, False):
        for i, h in enumerate(header):
            if i == exclude:
                continue
            for hint in hints:
                if (h == hint) if exact else (len(hint) > 2 and hint in h):
                    return i
    return None


def main():
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(1)

    src = Path(sys.argv[1]).expanduser()
    locale = sys.argv[2].lower().replace("-", "")
    out_dir = Path(sys.argv[3]).expanduser() if len(sys.argv) == 4 else Path(__file__).resolve().parent

    if not src.exists():
        sys.exit(f"ERROR: file not found — {src}")
    if locale not in VALID_LOCALES:
        sys.exit(f"ERROR: unknown locale {locale!r} (expected one of {sorted(VALID_LOCALES)})")

    rows = read_rows(src)
    if len(rows) < 2:
        sys.exit("ERROR: file has no data rows")

    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    en_col = find_column(header, EN_HINTS)
    if en_col is None:
        en_col = 0
    # Language-specific hints first (e.g. "final translation es"), generic ones last
    tgt_col = None
    for hint in TARGET_HINTS[locale]:
        tgt_col = find_column(header, [hint], exclude=en_col)
        if tgt_col is not None:
            break
    notes_col = find_column(header, NOTES_HINTS, exclude=en_col)
    if tgt_col is None:
        tgt_col = 1 if en_col == 0 else 0
    print(f"Header: {rows[0]}")
    print(f"Using EN column {en_col} ({rows[0][en_col]!r}), target column {tgt_col} ({rows[0][tgt_col]!r})"
          + (f", notes column {notes_col} ({rows[0][notes_col]!r})" if notes_col is not None else ""))

    en_to_targets = defaultdict(Counter)
    notes = {}
    order = []
    skipped = 0
    for r in rows[1:]:
        if len(r) <= max(en_col, tgt_col):
            skipped += 1
            continue
        en, tgt = r[en_col], r[tgt_col]
        en = str(en).strip() if en is not None else ""
        tgt = str(tgt).strip() if tgt is not None else ""
        if not en or not tgt:
            skipped += 1
            continue
        # "Human (e.g. '93% Human')" → "Human"; drop the example from the translation too
        m = re.match(r"^(.*?)\s*\(e\.g\..*\)$", en)
        if m:
            en = m.group(1)
            tgt = re.sub(r"\s*\([^)]*\)$", "", tgt)
        if en not in en_to_targets:
            order.append(en)
        en_to_targets[en][tgt] += 1
        if notes_col is not None and len(r) > notes_col and r[notes_col]:
            note = str(r[notes_col]).strip()
            if note and en not in notes:
                notes[en] = note

    tm, conflicts = {}, []
    for en in order:
        targets = en_to_targets[en]
        if len(targets) > 1:
            conflicts.append((en, dict(targets)))
        tm[en] = targets.most_common(1)[0][0]

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tm-{locale}.json"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("{\n")
        items = list(tm.items())
        for i, (k, v) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            val = {"t": v, "note": notes[k]} if k in notes else v
            f.write(f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(val, ensure_ascii=False)}{comma}\n")
        f.write("}\n")

    print(f"\n✓ Wrote {len(tm)} entries to {out_path}")
    print(f"  With usage notes: {sum(1 for k in tm if k in notes)}")
    print(f"  Skipped empty/malformed rows: {skipped}")
    print(f"  English terms with several translations (kept most common): {len(conflicts)}")
    for en, targets in conflicts[:10]:
        print(f"  {en!r}")
        for tgt, count in sorted(targets.items(), key=lambda x: -x[1]):
            print(f"      [{count}×] {tgt!r}{' ← kept' if tgt == tm[en] else ''}")


if __name__ == "__main__":
    main()
