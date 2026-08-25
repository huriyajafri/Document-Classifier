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
    Some fields may appear under different labels on the document (e.g. tax could be
    printed as "GST", "VAT", "Service Tax", etc.) -- normalize these into the field
    name given below regardless of which label the document uses.

    IMPORTANT: Use null for any field that does not literally appear in the document text.
    Do NOT guess, infer, or default missing amount fields to "0.00" or any other value.
    A missing tax line means tax_amount is null -- it does NOT mean the tax is zero.
    Only return a value if you can point to the exact text it came from.    
    Examples:
    Document text: "Subtotal: 50.00\nTax: 0.00\nTotal: 50.00"
    -> tax_amount: "0.00"  (explicitly stated)

    Document text: "Subtotal: 20.00\nGrand Total: 20.00"
    -> tax_amount: null  (no tax line exists anywhere)

    Do not include any text outside the JSON object.

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

   # print(f"\n--- OCR/SOURCE TEXT (doc_type={doc_type}) ---\n{text}\n--- END SOURCE TEXT ---\n")

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