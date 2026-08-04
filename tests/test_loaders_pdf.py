import fitz  # pymupdf
from helpmate.ingest.loaders import load_pdf


def test_load_pdf_extracts_text(tmp_path):
    p = tmp_path / "d.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "DJI Mini 4 Pro takeoff weight 249g")
    doc.save(p)
    doc.close()

    blocks = load_pdf(str(p))
    text = " ".join(b["text"] for b in blocks)
    assert "DJI Mini 4 Pro" in text and "249g" in text
    assert all(b["type"] in ("text", "table") and "page" in b for b in blocks)
