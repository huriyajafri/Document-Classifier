import requests
import json
from pipeline.schema_registry import get_schema

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b-instruct"
def build_prompt(text: str, schema: dict) -> str:
    field_desc = {}

    for name, f in schema["fields"].items():
        desc = f["description"] + (" (required)" if f.get("required") else " (optional)")

        if f.get("synonyms"):
            desc += f" -- may appear on the document labeled as: {', '.join(f['synonyms'])}"

        field_desc[name] = desc

    
    return f"""Extract the following fields from the document text as strict JSON.

       IMPORTANT TAX RULE:
            - If the document contains an explicit tax/GST/VAT/service-tax line, extract its numeric value EXACTLY.
            - An explicit tax value of 0, 0.00, 0.0, etc. MUST be returned as the number 0, NOT null.
            - Examples:
            - "Tax: 0.00" -> tax_amount: 0
            - "GST 0.00" -> tax_amount: 0
            - "VAT: 0" -> tax_amount: 0
            - "Service Tax: 125.50" -> tax_amount: 125.50
            - ONLY return null for tax_amount when there is NO explicit tax/GST/VAT/service-tax line anywhere in the document.
            - NEVER convert an explicitly stated zero tax amount into null.
            - Do NOT assume tax is zero merely because a tax line is absent.

       IMPORTANT ID FIELD RULE:
            - For ID-like fields (e.g. invoice_number, policy_number, employee_id): extract ONLY the identifier value itself.
            - Strip any surrounding labels, prefixes, or words such as "Invoice", "Tax Invoice", "Invoice No.", "Policy", "#", ":".
            - Examples:
            - "TAX Invoice: #11372" -> invoice_number: "11372"
            - "Invoice No. INV-2024-045" -> invoice_number: "INV-2024-045"
            - "Policy: POL/998877" -> policy_number: "POL/998877"
            - Keep alphanumeric identifiers intact (don't strip characters that are part of the actual ID), only remove label words and punctuation that are clearly not part of the ID.

       Some fields may appear under different labels on the document  normalize these into the field name given below regardless of which label the document uses.
       

        Fields to extract:
        {json.dumps(field_desc, indent=2)}

        Document text:
        \"\"\"{text[:4000]}\"\"\"

        Respond with ONLY a JSON object with exactly these keys: {', '.join(field_desc.keys())}."""
def compute_completeness(fields: dict, schema: dict) -> float:
    """% of all schema fields that are non-null/non-empty."""
    all_fields = list(schema["fields"].keys())
    if not all_fields:
        return 100.0
    filled = sum(1 for name in all_fields if fields.get(name) not in (None, ""))
    return round(filled / len(all_fields) * 100, 1)


def extract_fields(text: str, doc_type: str, model: str = MODEL) -> dict:
    schema = get_schema(doc_type)
    prompt = build_prompt(text, schema)

    #print(f"\n--- OCR/SOURCE TEXT (doc_type={doc_type}) ---\n{text}\n--- END SOURCE TEXT ---\n")

    resp = requests.post(OLLAMA_URL, json={
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0}
    })
    resp.raise_for_status()
    raw = resp.json()["response"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    #print(f"--- LLM RAW OUTPUT ---\n{raw}\n--- END LLM OUTPUT ---\n")

    try:
        parsed = json.loads(raw)
        parsed["_completeness"] = compute_completeness(parsed, schema)
        return parsed
    except json.JSONDecodeError:
        return {"_error": "Failed to parse JSON", "_raw_response": raw, "_completeness": 0.0}