"""
Entry point. Run: python main.py samples/invoices/some_invoice.pdf

Pipeline: ingest -> classify -> extract -> route (append to department file
or human_review.jsonl + log). Adding a new category later = drop a schema
yaml + sample PDFs. This file does not change.
"""
import sys
import json
from pathlib import Path

from pipeline.ingest import extract_text
from pipeline.classify import classify
from pipeline.extract import extract_fields
from pipeline.route import route

OUTPUT_DIR = Path(__file__).parent / "outputs"


def process(pdf_path: str, known_doc_type: str = None) -> dict:
    ingested = extract_text(pdf_path)
    text = ingested["text"]
    filename = Path(pdf_path).name

    doc_type = known_doc_type or classify(text)

    if doc_type is None:
        # Nothing matched a known schema -- skip extraction entirely,
        # route straight to human review.
        result = {
            "filename": filename,
            "doc_type": None,
            "source": ingested["source"],
            "fields": None,
        }
    else:
        fields = extract_fields(text, doc_type)
        result = {
        "filename": filename,
        "doc_type": doc_type,
        "source": ingested["source"],
        "fields": fields,
        "ocr_confidence": ingested.get("ocr_confidence"),
        "_completeness": fields.get("_completeness", 0) if isinstance(fields, dict) else 0,
        }

    # routing decides: department file, or human_review.jsonl (unclassified /
    # low_confidence) -- plus logs to routing_log.jsonl either way.
    routing_info = route(filename, doc_type, result)
    result["routing_status"] = routing_info["status"]
    result["routed_file"] = routing_info["file"]
    if routing_info["status"] == "routed":
        result["routed_to"] = routing_info["department"]
    else:
        result["review_reason"] = routing_info["reason"]

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <pdf_path> [doc_type]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    doc_type = sys.argv[2] if len(sys.argv) > 2 else None
    result = process(pdf_path, known_doc_type=doc_type)
    print(json.dumps(result, indent=2))

    if result["routing_status"] == "routed":
        print(f"\n→ Routed to: {result['routed_to']} | Appended to: {result['routed_file']}")
    else:
        print(f"\n→ Sent to human review (reason: {result['review_reason']}) | File: {result['routed_file']}")