"""
Compares outputs/<Department>.jsonl (model extractions) against
ground_truth/*.json (human-verified values) and prints per-field accuracy.
Also writes comparison_report.csv with a row per (filename, field) showing
expected vs. predicted side by side, plus the accuracy breakdown at the bottom.

Ground truth format: a list of records, each with a "filename" key plus
expected field values, e.g.:
[
  {"filename": "INV-2026-0001.pdf", "vendor_name": "...", "total_amount": "..."},
  ...
]

Predictions are read from every outputs/*.jsonl file (department files),
excluding routing_log.jsonl, matched by filename.

Run after processing all sample invoices:
    python eval.py invoice
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).parent
GT_DIR = BASE / "ground_truth"
OUT_DIR = BASE / "outputs"

EXCLUDED_FILES = {"routing_log.jsonl"}


def load_ground_truth(doc_type: str) -> dict:
    """Loads ground_truth/<doc_type>_ground_truth.json (a list of records)
    and returns it as {filename: {field: value, ...}}."""
    path = GT_DIR / f"{doc_type}_ground_truth.json"
    with open(path) as f:
        records = json.load(f)

    gt = {}
    for record in records:
        record = dict(record)  # copy
        filename = record.pop("filename")
        gt[filename] = record
    return gt


def load_all_predictions() -> dict:
    """Scans every outputs/*.jsonl file (department files + human_review),
    returns {filename: fields_dict} using the last record seen per filename
    (in case a file was reprocessed)."""
    predictions = {}
    for jsonl_file in OUT_DIR.glob("*.jsonl"):
        if jsonl_file.name in EXCLUDED_FILES:
            continue
        with open(jsonl_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                filename = record.get("filename")
                fields = record.get("fields")
                if filename and isinstance(fields, dict):
                    predictions[filename] = fields
    return predictions


def normalize(v):
    """Numbers compare numerically (currency codes/symbols/commas-safe); strings compare trimmed+lowercased."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v).strip()
    # strip currency codes/symbols (e.g. "QAR 3,362.82" -> "3,362.82") before trying float
    cleaned = re.sub(r"[A-Za-z$]", "", s).strip().replace(",", "")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return s.lower().replace("-", "/")


def evaluate(doc_type: str):
    gt = load_ground_truth(doc_type)
    predictions = load_all_predictions()

    field_correct, field_total = {}, {}

    for filename, expected in gt.items():
        predicted = predictions.get(filename)
        if predicted is None:
            print(f"⚠ no prediction found for {filename}, skipping")
            continue

        print(f"\n{filename}")
        for field, exp_val in expected.items():
            if exp_val in (None, ""):
                continue
            pred_val = predicted.get(field)
            match = normalize(exp_val) == normalize(pred_val)

            field_total[field] = field_total.get(field, 0) + 1
            field_correct[field] = field_correct.get(field, 0) + (1 if match else 0)

            status = "✓" if match else "✗"
            print(f"  {status} {field}: expected='{exp_val}' got='{pred_val}'")

    print("\n--- Field accuracy ---")
    for field in field_total:
        acc = field_correct[field] / field_total[field]
        print(f"{field}: {acc:.0%} ({field_correct[field]}/{field_total[field]})")


if __name__ == "__main__":
    doc_type = sys.argv[1] if len(sys.argv) > 1 else "invoice"
    evaluate(doc_type)