# Document Extractor

Schema-driven pipeline: works on invoices, insurance, and onboarding docs now, scales to future document types by adding a schema file — no code changes.

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Tesseract** (for OCR on scanned PDFs) must be installed separately:
- Windows: install from https://github.com/UB-Mannheim/tesseract/wiki
- Mac: `brew install tesseract`
- Ubuntu: `sudo apt install tesseract-ocr`

**Ollama** (local LLM) must be running:
```bash
# install: https://ollama.com
ollama pull qwen2.5:3b-instruct
ollama serve
```

## Usage

```bash
python main.py samples/invoices/invoice1.pdf
```

Skip classification (you already know the type):
```bash
python main.py samples/invoices/invoice1.pdf invoice
```

Output JSON is saved to `outputs/`.

## Ground truth & evaluation

`ground_truth/invoice_ground_truth.json` holds the correct field values for
each sample invoice, filled in by hand. JSON (not CSV) so `line_items`
nests properly and large totals with commas (e.g. `12,500.00`) don't break
parsing — numbers stay typed, not stuck in ambiguous comma-separated text.

1. Run `main.py` on your sample invoices to populate `outputs/`.
2. Fill in `ground_truth/invoice_ground_truth.json` with the true values.
3. Run `python eval.py invoice` to see per-field accuracy (including line_items).

For a new category later, add `ground_truth/insurance_ground_truth.json` with
keys matching that schema's fields.

## Adding a new document category later

1. Create `schemas/insurance.yaml` (copy `schemas/invoice.yaml` as a template,
   change `doc_type`, `description`, and `fields`).
2. Drop sample PDFs into `samples/insurance/`.
3. Done — `classify.py` and `extract.py` pick it up automatically since they
   read from the schema registry at runtime.

## Why qwen2.5:3b-instruct?

Local model for structured JSON extraction/classification. Runs on the
project's 4GB VRAM (GTX 1650) — the 7B variant was tried first but didn't
fit. Alternatives if hardware allows:
- `llama3.1:8b-instruct` — solid general-purpose fallback
- `qwen2.5:7b-instruct` / `14b-instruct` — better accuracy at ~8GB / ~16GB VRAM
- `phi3.5` — lighter/faster if hardware is more limited, slightly less accurate on JSON strictness

Swap models by changing `MODEL` in `pipeline/classify.py` and `pipeline/extract.py`.

## Pipeline

```
ingest → classify → extract → route
```

Orchestrated via `main.py`, batch-run via `run_batch.py`, evaluated via `eval.py`.

| Stage | File | Purpose |
|---|---|---|
| Ingest | `ingest.py` | Text extraction (PyMuPDF for native PDFs, Tesseract OCR for scans/images) |
| Classify | `classify.py` | LLM-based doc_type matching against registered schemas |
| Extract | `extract.py` | LLM-based structured field extraction per schema |
| Route | `route.py` | Sends records to department output or human review queue |

## Design principles

- **Schema-driven, not code-driven.** Adding a new document category (e.g. insurance, onboarding forms) requires only a new YAML schema in `schemas/` — no code changes. Department routing, confidence thresholds, field synonyms, and required-field status are all config-defined.
- **No self-reported LLM confidence.** The model's own confidence score was tried and dropped — unreliable on the 3B model (`None` returns) and inherently untrustworthy as self-assessment. Routing instead uses two objective signals:
  - **Field completeness** — computed locally from which required fields were extracted.
  - **OCR confidence** — from Tesseract's `image_to_data` (OCR path only), filtered to only count word-boxes with non-empty recognized text.
- **LLM never sees the image.** It only receives OCR'd text, so its output reflects text clarity, not image quality.
- **Routing by source type:**
  - Native PDFs → route on completeness alone.
  - OCR'd files (scans/images) → must pass both completeness and OCR confidence thresholds. Review reasons are distinct: `low_completeness` vs `low_ocr_confidence`.
  - Unclassified documents → always routed to human review, reason `unclassified`.

### Routing thresholds

| Signal | Threshold | Applies to |
|---|---|---|
| Completeness | ≥ 90 | All doc types |
| OCR confidence | ≥ 60 | OCR'd files only (scans/images) |

- **Flat record schema.** `route.py` reads fields via flat `record.get()` calls, so `ocr_confidence` and `_completeness` live at the top level of the result dict, not nested under `fields`.

## Stack

- Python, developed in VS Code on Windows
- **OCR:** Tesseract via `pytesseract`
- **PDF parsing:** PyMuPDF
- **LLM:** `qwen2.5:3b-instruct` via Ollama (local, 4GB VRAM)
- **Schemas:** YAML (`schemas/invoice.yaml`, future categories to follow)
- **Output:** JSONL per department (e.g. `Finance.jsonl`), plus `human_review.jsonl` and `routing_log.jsonl`