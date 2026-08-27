import fitz
from paddleocr import PaddleOCR
from PIL import Image
from pathlib import Path
import io
import numpy as np

# init once, reused across all calls
#_paddle_ocr = PaddleOCR(use_textline_orientation=True, lang='en')
_paddle_ocr = PaddleOCR(use_textline_orientation=True, lang='en', enable_mkldnn=False)

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
    """Runs PaddleOCR once, returns (text, avg_confidence 0-100).
    Mirrors the old Tesseract function's contract exactly."""
    img_array = np.array(img.convert("RGB"))
    result = _paddle_ocr.predict(img_array)

    lines, confs = [], []
    if result:
        res = result[0]
        lines = res.get("rec_texts", [])
        confs = res.get("rec_scores", [])

    full_text = "\n".join(lines)
    avg_conf = (sum(confs) / len(confs) * 100) if confs else 0.0
    return full_text, avg_conf


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
        print(f"[INGEST] {file_path}: image file — using OCR (PaddleOCR)")
        text, conf = extract_text_from_image(file_path)
        return {"text": text, "source": "ocr", "ocr_confidence": conf}

    if has_text_layer(file_path):
        print(f"[INGEST] {file_path}: text layer found — used direct PDF extraction (PyMuPDF)")
        return {"text": extract_text_native(file_path), "source": "native", "ocr_confidence": None}

    print(f"[INGEST] {file_path}: no usable text layer — falling back to OCR (PaddleOCR)")
    text, conf = extract_text_ocr(file_path)
    return {"text": text, "source": "ocr", "ocr_confidence": conf}