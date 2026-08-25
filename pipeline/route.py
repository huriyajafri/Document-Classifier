import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.schema_registry import get_schema

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
ROUTING_LOG = OUTPUT_DIR / "routing_log.jsonl"
REVIEW_FILE = OUTPUT_DIR / "human_review.jsonl"


def get_department(doc_type: str) -> str:
    schema = get_schema(doc_type)
    return schema.get("department", "Unassigned")


def get_completeness_threshold(doc_type: str) -> float:
    schema = get_schema(doc_type)
    return schema.get("completeness_threshold", 80)


def get_ocr_threshold(doc_type: str) -> float:
    schema = get_schema(doc_type)
    return schema.get("ocr_confidence_threshold", 60)


def append_to_department_file(department: str, record: dict) -> Path:
    dept_file = OUTPUT_DIR / f"{department}.jsonl"
    with open(dept_file, "a") as f:
        f.write(json.dumps(record) + "\n")
    return dept_file


def append_to_review_file(record: dict, reason: str) -> Path:
    entry = {**record, "review_reason": reason}
    with open(REVIEW_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return REVIEW_FILE


def log_routing(filename: str, doc_type: str | None, department: str, status: str) -> None:
    entry = {
        "filename": filename,
        "doc_type": doc_type,
        "department": department,
        "status": status,
        "routed_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(ROUTING_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def route(filename: str, doc_type: str | None, record: dict) -> dict:
    """
    - doc_type=None -> review, reason 'unclassified'
    - completeness below threshold -> review, reason 'low_completeness'
    - (OCR source only) ocr_confidence below threshold -> review, reason 'low_ocr_confidence'
    - otherwise -> routed
    """
    if doc_type is None:
        target_file = append_to_review_file(record, reason="unclassified")
        log_routing(filename, None, "Unassigned", status="review")
        return {"status": "review", "reason": "unclassified", "file": str(target_file)}

    department = get_department(doc_type)
    completeness = record.get("_completeness", 0)
    completeness_threshold = get_completeness_threshold(doc_type)

    if completeness < completeness_threshold:
        target_file = append_to_review_file(record, reason="low_completeness")
        log_routing(filename, doc_type, department, status="review")
        return {"status": "review", "reason": "low_completeness",
                "completeness": completeness, "threshold": completeness_threshold,
                "file": str(target_file)}

    if record.get("source") == "ocr":
        ocr_conf = record.get("ocr_confidence") or 0
        ocr_threshold = get_ocr_threshold(doc_type)
        if ocr_conf < ocr_threshold:
            target_file = append_to_review_file(record, reason="low_ocr_confidence")
            log_routing(filename, doc_type, department, status="review")
            return {"status": "review", "reason": "low_ocr_confidence",
                    "ocr_confidence": ocr_conf, "threshold": ocr_threshold,
                    "file": str(target_file)}

    target_file = append_to_department_file(department, record)
    log_routing(filename, doc_type, department, status="routed")
    return {"status": "routed", "department": department,
            "completeness": completeness, "file": str(target_file)}