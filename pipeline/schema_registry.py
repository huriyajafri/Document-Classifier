"""
Loads all schema YAML files from /schemas into a registry.
Adding a new doc type later = adding a new YAML file here. No code changes needed.
"""
import yaml
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent.parent / "schemas"


def load_schemas() -> dict:
    """Returns {doc_type: schema_dict} for every yaml file in /schemas."""
    schemas = {}
    for f in SCHEMA_DIR.glob("*.yaml"):
        with open(f, "r") as fh:
            data = yaml.safe_load(fh)
            schemas[data["doc_type"]] = data
    return schemas


def get_schema(doc_type: str) -> dict:
    schemas = load_schemas()
    if doc_type not in schemas:
        raise ValueError(f"No schema found for doc_type='{doc_type}'. "
                          f"Available: {list(schemas.keys())}")
    return schemas[doc_type]


if __name__ == "__main__":
    for name, schema in load_schemas().items():
        print(f"{name}: {list(schema['fields'].keys())}")
