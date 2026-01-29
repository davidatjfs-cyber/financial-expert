from __future__ import annotations

from pathlib import Path


def _is_garbled_text(text: str) -> bool:
    """检测文本是否为乱码（CID 字体编码问题）"""
    if not text:
        return True
    # 检查是否包含大量 CID 编码或乱码特征
    cid_count = text.count("(cid:")
    if cid_count > 10:
        return True
    # 检查可读字符比例
    def _is_cjk(ch: str) -> bool:
        o = ord(ch)
        return (
            0x4E00 <= o <= 0x9FFF
            or 0x3400 <= o <= 0x4DBF
            or 0x20000 <= o <= 0x2A6DF
            or 0x2A700 <= o <= 0x2B73F
            or 0x2B740 <= o <= 0x2B81F
            or 0x2B820 <= o <= 0x2CEAF
            or 0xF900 <= o <= 0xFAFF
        )

    readable = sum(
        1
        for c in text
        if c.isalnum() or c.isspace() or _is_cjk(c) or c in ".,;:!?$%()-，。；：！？（）【】《》、"
    )
    if len(text) > 100 and readable / len(text) < 0.5:
        return True
    return False


def _extract_with_ocr(path: str, max_pages: int = 10) -> str:
    """使用 OCR 提取 PDF 文本"""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        
        # 对于 OCR，使用更多页面以获取财务数据
        ocr_pages = min(max_pages, 50)  # 最多 50 页
        images = convert_from_path(str(path), first_page=1, last_page=ocr_pages, dpi=150)
        texts = []
        for img in images:
            page_text = ""
            try:
                page_text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            except Exception:
                try:
                    page_text = pytesseract.image_to_string(img, lang='chi_sim')
                except Exception:
                    page_text = pytesseract.image_to_string(img, lang='eng')
            if page_text:
                texts.append(page_text)
        return "\n\n".join(texts)
    except Exception:
        return ""


def extract_pdf_text(path: str | Path, max_pages: int = 2, max_chars: int = 5000) -> str:
    p = Path(path)
    if not p.exists():
        return ""

    # 首先尝试 pdfplumber
    texts: list[str] = []
    try:
        import pdfplumber
        with pdfplumber.open(str(p)) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages]):
                t = page.extract_text() or ""
                if t:
                    texts.append(t)
    except Exception:
        pass

    out = "\n\n".join(texts).strip()
    
    # 如果文本是乱码，尝试 OCR
    if _is_garbled_text(out):
        ocr_text = _extract_with_ocr(str(p), max_pages)
        if ocr_text and not _is_garbled_text(ocr_text):
            out = ocr_text

    if len(out) > max_chars:
        out = out[:max_chars] + "\n..."
    return out
