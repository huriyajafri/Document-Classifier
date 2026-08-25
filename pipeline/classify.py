"""
Stage 2: Classification.
Asks a local LLM (via Ollama) which registered doc_type a text blob belongs to.
Works with 1 schema today, N schemas later -- no code change required.
"""
import requests
import json
from pipeline.schema_registry import load_schemas

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b-instruct"  # good structured-output/classification model, runs on ~8GB VRAM


def classify(text: str, model: str = MODEL) -> str | None:
    """Returns the matched doc_type, or None if no known schema matches
    (caller should route these to the human review queue instead of guessing)."""
    schemas = load_schemas()
    doc_types = {name: s["description"] for name, s in schemas.items()}

    prompt = f"""You are a document classifier. Given the document text below,
    choose exactly ONE doc_type from this list (respond with ONLY the key, nothing else):

    {json.dumps(doc_types, indent=2)}

    Document text (truncated):
    \"\"\"{text[:2000]}\"\"\"

    Answer with only the doc_type key."""

    resp = requests.post(OLLAMA_URL, json={
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0}
    })
    resp.raise_for_status()
    answer = resp.json()["response"].strip().lower()

    for name in doc_types:
        if name in answer:
            return name

    print(f"[CLASSIFY] Could not match '{answer}' to any known doc_type — flagging for human review")
    return None


if __name__ == "__main__":
    import sys
    from pipeline.ingest import extract_text
    text = extract_text(sys.argv[1])["text"]
    print(classify(text))
