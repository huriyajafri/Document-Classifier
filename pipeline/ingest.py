import fitz
import pytesseract
from pytesseract import Output
from PIL import Image
from pathlib import Path
import io


def has_text_layer(pdf_path: str, min_chars: int = 20) -> bool:
    doc = fitz.open(pdf_path)
    for page in doc[:2]:
        if len(page.get_text().strip()) > min_chars:
            doc.close()
            return True
    doc.close()
    return False


def extract_text_native(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def _ocr_image_with_confidence(img: Image.Image) -> tuple[str, float]:
    """Runs Tesseract once, returns (text, avg_word_confidence 0-100).
    Only counts confidence for boxes that actually recognized non-empty text --
    image_to_data can report a valid conf score for blank/whitespace boxes too,
    which would otherwise inflate the average even when nothing was read."""
    data = pytesseract.image_to_data(img, output_type=Output.DICT)
    confs = [
        int(c) for c, t in zip(data["conf"], data["text"])
        if int(c) != -1 and t.strip()
    ]
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    text = pytesseract.image_to_string(img)
    return text, avg_conf


def extract_text_ocr(pdf_path: str, dpi: int = 300) -> tuple[str, float]:
    doc = fitz.open(pdf_path)
    text_parts, page_confs = [], []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text, conf = _ocr_image_with_confidence(img)
        text_parts.append(text)
        page_confs.append(conf)
    doc.close()
    avg_conf = sum(page_confs) / len(page_confs) if page_confs else 0.0
    return "\n".join(text_parts), avg_conf


def extract_text_from_image(image_path: str) -> tuple[str, float]:
    img = Image.open(image_path)
    return _ocr_image_with_confidence(img)


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}


def extract_text(file_path: str) -> dict:
    """Returns {'text': str, 'source': 'native'|'ocr', 'ocr_confidence': float|None}.
    ocr_confidence is None for the native-PDF path (no OCR ran)."""
    ext = Path(file_path).suffix.lower()

    if ext in IMAGE_EXTS:
        print(f"[INGEST] {file_path}: image file — using OCR (Tesseract)")
        text, conf = extract_text_from_image(file_path)
        return {"text": text, "source": "ocr", "ocr_confidence": conf}

    if has_text_layer(file_path):
        print(f"[INGEST] {file_path}: text layer found — used direct PDF extraction (PyMuPDF)")
        return {"text": extract_text_native(file_path), "source": "native", "ocr_confidence": None}

    print(f"[INGEST] {file_path}: no usable text layer — falling back to OCR (Tesseract)")
    text, conf = extract_text_ocr(file_path)
    return {"text": text, "source": "ocr", "ocr_confidence": conf}