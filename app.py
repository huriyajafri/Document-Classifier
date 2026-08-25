import streamlit as st
import tempfile
import os
from pathlib import Path

from pipeline.ingest import extract_text
from pipeline.classify import classify
from pipeline.extract import extract_fields
from pipeline.route import route

st.set_page_config(page_title="Doc Extractor Demo", layout="centered")
st.title("📄 Document Extractor")
st.caption("Upload a document to see classification, extraction, and routing.")

uploaded_file = st.file_uploader("Upload a document", type=["pdf", "jpg", "jpeg", "png"])

if uploaded_file is not None:
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    filename = uploaded_file.name

    with st.spinner("Processing..."):
        try:
            ingested = extract_text(tmp_path)
            text = ingested["text"]
            doc_type = classify(text)

            if doc_type is None:
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

            routing_info = route(filename, doc_type, result)
            result["routing_status"] = routing_info["status"]
            result["routed_file"] = routing_info["file"]
            if routing_info["status"] == "routed":
                result["routed_to"] = routing_info["department"]
            else:
                result["review_reason"] = routing_info["reason"]

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            os.unlink(tmp_path)
            st.stop()

    os.unlink(tmp_path)

    st.subheader("Classification")
    st.write(f"**Document type:** {doc_type or 'Unclassified'}")

    st.subheader("Extracted Fields")
    st.json(result.get("fields"))

    st.subheader("Routing Decision")
    if result["routing_status"] == "routed":
        st.success(f"Routed to **{result['routed_to']}**\n\nAppended to: `{result['routed_file']}`")
    else:
        st.warning(f"Sent to **Human Review**\n\nReason: {result.get('review_reason')}\n\nFile: `{result['routed_file']}`")