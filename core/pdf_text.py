from __future__ import annotations

import os
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

    # 额外判定：大量不可打印控制字符（\x00-\x1F，排除常见空白）
    ctrl = 0
    sample = text[:5000]
    for c in sample:
        o = ord(c)
        if o < 32 and c not in ("\n", "\r", "\t"):
            ctrl += 1
    if len(text) > 200:
        # 对于 CID/编码错乱 PDF，控制字符会非常密集
        if ctrl > 30:
            return True
        if ctrl / max(1, len(sample)) > 0.01:
            return True
    return False


def _extract_with_ocr(path: str, max_pages: int = 10) -> str:
    """使用 OCR 提取 PDF 文本"""
    # OCR 非常消耗 CPU/内存（pdf2image + tesseract），线上默认关闭，避免拖垮服务器。
    # 如需强制开启：设置环境变量 ENABLE_OCR=1
    # 对于乱码/扫描版 PDF，可开启轻量自动兜底：AUTO_OCR_FALLBACK=1（默认开启，但会做尺寸/页数保护）
    enable_ocr = (os.environ.get("ENABLE_OCR") or "").strip() == "1"
    auto_fallback = (os.environ.get("AUTO_OCR_FALLBACK") or "1").strip() != "0"
    if (not enable_ocr) and (not auto_fallback):
        return ""

    # Safety guard for auto fallback: skip huge PDFs unless explicitly enabled.
    # Use OCR_AUTO_MAX_PDF_MB to adjust (default: 25MB).
    if (not enable_ocr) and auto_fallback:
        try:
            p = Path(path)
            max_mb = float((os.environ.get("OCR_AUTO_MAX_PDF_MB") or "25").strip() or "25")
            if max_mb <= 0:
                max_mb = 25
            max_bytes = int(max_mb * 1024 * 1024)
            if p.exists() and p.stat().st_size > max_bytes:
                return ""
        except Exception:
            pass
    try:
        import pytesseract
        
        # OCR 强依赖 CPU/内存：用环境变量调参，默认尽量保守
        ocr_max_pages = int((os.environ.get("OCR_MAX_PAGES") or "10").strip() or "10")
        ocr_dpi = int((os.environ.get("OCR_DPI") or "120").strip() or "120")
        ocr_start_page = int((os.environ.get("OCR_START_PAGE") or "1").strip() or "1")
        ocr_lang = (os.environ.get("OCR_LANG") or "eng").strip() or "eng"
        ocr_psm = int((os.environ.get("OCR_PSM") or "6").strip() or "6")
        ocr_auto_find = (os.environ.get("OCR_AUTO_FIND") or "1").strip() != "0"
        ocr_probe_pages = int((os.environ.get("OCR_PROBE_PAGES") or "6").strip() or "6")
        ocr_probe_dpi = int((os.environ.get("OCR_PROBE_DPI") or "90").strip() or "90")
        ocr_pages = min(max_pages, max(1, ocr_max_pages))

        first_page = max(1, ocr_start_page)

        def _ocr_image(img) -> str:
            page_text = ""
            try:
                page_text = pytesseract.image_to_string(img, lang=ocr_lang, config=f"--psm {ocr_psm}")
            except Exception:
                try:
                    page_text = pytesseract.image_to_string(img, lang=ocr_lang, config=f"--psm {ocr_psm}")
                except Exception:
                    try:
                        page_text = pytesseract.image_to_string(img, lang="chi_sim+eng", config=f"--psm {ocr_psm}")
                    except Exception:
                        page_text = pytesseract.image_to_string(img, lang="eng", config=f"--psm {ocr_psm}")
            return page_text or ""

        def _render_page_image_fitz(page_index_1: int, dpi: int):
            """Render a 1-indexed page to a PIL Image using PyMuPDF."""
            import fitz
            from PIL import Image

            doc = fitz.open(str(path))
            try:
                idx0 = max(0, int(page_index_1) - 1)
                page = doc.load_page(idx0)
                zoom = max(0.5, float(dpi) / 72.0)
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            finally:
                try:
                    doc.close()
                except Exception:
                    pass

        pages_to_ocr_0: list[int] | None = None

        if ocr_auto_find and first_page == 1:
            try:
                import fitz

                doc = fitz.open(str(path))
                page_count = int(doc.page_count or 0)
                try:
                    doc.close()
                except Exception:
                    pass

                if page_count > 0:
                    try:
                        auto_max_page_count = int((os.environ.get("OCR_AUTO_MAX_PAGECOUNT") or "300").strip() or "300")
                    except Exception:
                        auto_max_page_count = 300
                    if auto_max_page_count <= 0:
                        auto_max_page_count = 300
                    if (not enable_ocr) and page_count > auto_max_page_count:
                        return ""
                    # Sample across the document; adapt step to the number of probe pages requested.
                    # Using a fixed //10 can miss statement pages for some PDFs.
                    step = max(1, page_count // max(10, (ocr_probe_pages + 2)))
                    candidates = [1]
                    for i in range(1, 1 + ocr_probe_pages):
                        candidates.append(1 + i * step)
                    candidates = [c for c in candidates if 1 <= c <= page_count]

                    scored: list[tuple[int, float]] = []
                    for c in candidates:
                        try:
                            # Prefer PyMuPDF rendering for probing; fall back to pdf2image if unavailable.
                            s = ""
                            try:
                                img = _render_page_image_fitz(c, ocr_probe_dpi)
                                s = _ocr_image(img)
                            except Exception:
                                try:
                                    from pdf2image import convert_from_path

                                    imgs = convert_from_path(str(path), first_page=c, last_page=c, dpi=ocr_probe_dpi)
                                    if imgs:
                                        s = _ocr_image(imgs[0])
                                except Exception:
                                    s = ""

                            s2 = s.strip()
                            if not s2:
                                continue
                            head = s2[:2000]
                            kw = 0
                            up = head.upper()

                            # Prefer true financial statement pages
                            strong = (
                                "NET SALES" in up
                                or "CONSOLIDATED STATEMENTS" in up
                                or "CONSOLIDATED FINANCIAL STATEMENTS" in up
                                or "BALANCE SHEETS" in up
                                or "STATEMENTS OF OPERATIONS" in up
                                or "STATEMENTS OF CASH FLOWS" in up
                            )
                            if strong:
                                kw += 10

                            for k in ("CONSOLIDATED", "STATEMENTS", "REVENUE", "IN MILLIONS", "FORM 10-K"):
                                if k in up:
                                    kw += 1
                            ascii_ratio = sum(1 for ch in head if (" " <= ch <= "~")) / max(1, len(head))
                            score = kw * 10.0 + ascii_ratio
                            scored.append((c, score))
                        except Exception:
                            continue

                    # Pick several best pages (1-indexed) and OCR them (and their next page) to cover
                    # statements of operations / balance sheets / cash flows which may be separated.
                    scored = sorted(scored, key=lambda kv: kv[1], reverse=True)
                    picked_1 = [p for p, sc in scored if sc >= 1.0][: max(1, min(4, ocr_pages))]
                    if picked_1:
                        # Convert to 0-index and include adjacent continuation pages.
                        picked_0: list[int] = []
                        for p1 in picked_1:
                            p0 = max(0, int(p1) - 1)
                            if p0 not in picked_0:
                                picked_0.append(p0)
                            if (p0 + 1) < page_count and (p0 + 1) not in picked_0:
                                picked_0.append(p0 + 1)
                        pages_to_ocr_0 = picked_0[: max(1, ocr_pages)]

                        # Keep first_page for backwards compatible contiguous OCR if needed.
                        first_page = min(picked_1)
            except Exception:
                pass

        texts: list[str] = []

        # Prefer PyMuPDF rendering to avoid external poppler dependency.
        try:
            import fitz
            from PIL import Image

            doc = fitz.open(str(path))
            page_count = int(doc.page_count or 0)
            start_idx = max(0, int(first_page) - 1)
            end_idx = min(page_count - 1, start_idx + ocr_pages - 1) if page_count > 0 else -1
            zoom = max(0.5, float(ocr_dpi) / 72.0)
            mat = fitz.Matrix(zoom, zoom)
            if pages_to_ocr_0:
                iter_pages = [i for i in pages_to_ocr_0 if 0 <= i < page_count]
            else:
                iter_pages = list(range(start_idx, end_idx + 1))

            for i in iter_pages:
                try:
                    page = doc.load_page(i)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    page_text = _ocr_image(img)
                    if page_text:
                        texts.append(page_text)
                except Exception:
                    continue
            try:
                doc.close()
            except Exception:
                pass
            if texts:
                return "\n\n".join(texts)
        except Exception:
            pass

        # Fallback to pdf2image if available.
        try:
            from pdf2image import convert_from_path

            last_page = max(first_page, first_page + ocr_pages - 1)
            images = convert_from_path(str(path), first_page=first_page, last_page=last_page, dpi=ocr_dpi)
            for img in images:
                page_text = _ocr_image(img)
                if page_text:
                    texts.append(page_text)
            return "\n\n".join(texts)
        except Exception:
            return ""
    except Exception:
        return ""


def extract_pdf_text(
    path: str | Path,
    max_pages: int = 2,
    max_chars: int = 5000,
    fast_only: bool = False,
) -> str:
    p = Path(path)
    if not p.exists():
        return ""

    def _pick_pages_smart(page_count: int, k: int) -> list[int]:
        """Pick up to k pages (0-indexed) likely containing financial statements."""
        if page_count <= 0:
            return []
        k = max(1, int(k))
        if page_count <= k:
            return list(range(page_count))

        # Candidates: first/last, plus sampled pages across document
        candidates: set[int] = set()
        for i in range(min(3, page_count)):
            candidates.add(i)
        for i in range(max(0, page_count - 3), page_count):
            candidates.add(i)

        step = max(1, page_count // max(12, k * 2))
        for i in range(0, page_count, step):
            candidates.add(i)

        cands = sorted(candidates)

        # Score pages by presence of keywords in a lightweight preview
        def _score_preview(txt: str) -> float:
            s = (txt or "").strip()
            if not s:
                return -1.0
            head = s[:3000]
            up = head.upper()
            score = 0.0

            strong_en = (
                "CONSOLIDATED STATEMENTS" in up
                or "STATEMENTS OF OPERATIONS" in up
                or "STATEMENTS OF CASH FLOWS" in up
                or "BALANCE SHEETS" in up
                or "INCOME STATEMENT" in up
                or "FORM 10-K" in up
            )
            if strong_en:
                score += 50
            for k2 in (
                "REVENUE",
                "NET INCOME",
                "NET SALES",
                "GROSS PROFIT",
                "TOTAL ASSETS",
                "TOTAL LIABILITIES",
                "STOCKHOLDERS",
                "IN MILLIONS",
                "IN BILLIONS",
            ):
                if k2 in up:
                    score += 5

            # Chinese keywords
            for k2 in (
                "利润表",
                "合并利润表",
                "合并资产负债表",
                "资产负债表",
                "现金流量表",
                "营业收入",
                "营业总收入",
                "净利润",
                "归属于",
                "毛利率",
                "基本每股收益",
            ):
                if k2 in head:
                    score += 5

            ascii_ratio = sum(1 for ch in head if (" " <= ch <= "~")) / max(1, len(head))
            score += ascii_ratio
            return score

        previews: dict[int, float] = {}

        # Use PyMuPDF for preview scoring (fast and resilient); fall back to empty scores.
        try:
            import fitz

            doc = fitz.open(str(p))
            for idx in cands:
                try:
                    page = doc.load_page(idx)
                    txt = page.get_text("text") or ""
                    previews[idx] = _score_preview(txt)
                except Exception:
                    previews[idx] = -1.0
            try:
                doc.close()
            except Exception:
                pass
        except Exception:
            for idx in cands:
                previews[idx] = 0.0

        ranked = sorted(previews.items(), key=lambda kv: kv[1], reverse=True)
        picked = [idx for idx, sc in ranked if sc >= 0][:k]

        # Guarantee deterministic fill if scores are all bad
        if len(picked) < k:
            for idx in cands:
                if idx not in picked:
                    picked.append(idx)
                if len(picked) >= k:
                    break

        return sorted(set(picked))

    def _truncate(s: str) -> str:
        if len(s) > max_chars:
            return s[:max_chars] + "\n..."
        return s

    def _strip_ctrl(s: str) -> str:
        return "".join(ch if (ord(ch) >= 32 or ch in ("\n", "\r", "\t")) else " " for ch in s)

    def _looks_like_useful_english(s: str) -> bool:
        try:
            up = (s or "").upper()
            keys = [
                "FORM 10-K",
                "NET SALES",
                "REVENUE",
                "CONSOLIDATED",
                "STATEMENTS",
                "BALANCE SHEETS",
                "CASH FLOWS",
                "IN MILLIONS",
            ]
            return any(k in up for k in keys)
        except Exception:
            return False

    def _debug_enabled() -> bool:
        try:
            return (os.environ.get("PDF_TEXT_DEBUG") or "0").strip() == "1"
        except Exception:
            return False

    def _maybe_debug(msg: str) -> None:
        try:
            if _debug_enabled():
                print(msg)
        except Exception:
            pass

    out = ""

    # Decide which pages to read. For long documents, pick pages smartly instead of only the first N.
    page_indices: list[int] = []
    try:
        import fitz

        doc0 = fitz.open(str(p))
        page_count = int(doc0.page_count or 0)
        try:
            doc0.close()
        except Exception:
            pass
        page_indices = _pick_pages_smart(page_count, max_pages)
    except Exception:
        page_indices = list(range(max(1, int(max_pages))))

    # Fast-only mode: avoid heavy extractors that can hang/OOM in production.
    if fast_only:
        # Prefer PyMuPDF for fast and resilient extraction.
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(p))
            buf: list[str] = []
            for i in [i for i in page_indices if 0 <= i < int(doc.page_count or 0)]:
                try:
                    page = doc.load_page(i)
                    t = page.get_text("text") or ""
                    if t:
                        buf.append(t)
                except Exception:
                    continue
            try:
                doc.close()
            except Exception:
                pass
            txt = "\n\n".join(buf).strip()
            txt = _strip_ctrl(txt)
            if txt and not _is_garbled_text(txt):
                out = txt
        except Exception:
            out = ""

        # Fallback to pypdf (sometimes cleaner) but still lightweight.
        if not out or _is_garbled_text(out):
            try:
                from pypdf import PdfReader

                r = PdfReader(str(p))
                buf2: list[str] = []
                for i in [i for i in page_indices if 0 <= i < len(r.pages)]:
                    try:
                        t = r.pages[i].extract_text() or ""
                        if t:
                            buf2.append(t)
                    except Exception:
                        continue
                txt2 = "\n\n".join(buf2).strip()
                txt2 = _strip_ctrl(txt2)
                if txt2 and not _is_garbled_text(txt2):
                    out = txt2
            except Exception:
                pass

        # If still garbled/empty, or too short/uninformative, try guarded OCR fallback.
        too_short = False
        try:
            min_chars = int((os.environ.get("PDF_TEXT_MIN_CHARS_FOR_NO_OCR") or "800").strip() or "800")
            s0 = (out or "").strip()
            digit_cnt = sum(1 for ch in s0 if ch.isdigit())
            too_short = (len(s0) < min_chars) or (digit_cnt < 20)
        except Exception:
            too_short = False

        if (not out) or _is_garbled_text(out) or too_short:
            try:
                _maybe_debug(f"pdf_text: triggering ocr fallback; len={len((out or '').strip())} too_short={too_short}")
                ocr_text = _extract_with_ocr(str(p), max_pages)
                if ocr_text:
                    ocr_text = _strip_ctrl(ocr_text)
                    if (not _is_garbled_text(ocr_text)) or _looks_like_useful_english(ocr_text):
                        out = ocr_text
            except Exception:
                pass

        return _truncate(out)

    # Fast path: try pypdf first to avoid pdfplumber stalls on some PDFs
    try:
        from pypdf import PdfReader

        r = PdfReader(str(p))
        buf: list[str] = []
        for i in [i for i in page_indices if 0 <= i < len(r.pages)]:
            try:
                t = r.pages[i].extract_text() or ""
                if t:
                    buf.append(t)
            except Exception:
                continue
        txt = "\n\n".join(buf).strip()
        txt = _strip_ctrl(txt)
        if txt and not _is_garbled_text(txt):
            out = txt
    except Exception:
        out = ""

    # 首先尝试 pdfplumber
    texts: list[str] = []
    if not out or _is_garbled_text(out):
        try:
            import pdfplumber
            with pdfplumber.open(str(p)) as pdf:
                for i in [i for i in page_indices if 0 <= i < len(pdf.pages)]:
                    try:
                        page = pdf.pages[i]
                        t = page.extract_text() or ""
                        if t:
                            texts.append(t)
                    except Exception:
                        continue
        except Exception:
            pass

        if texts:
            out = "\n\n".join(texts).strip()
            out = _strip_ctrl(out)

    # 如果是乱码/空文本，fallback 到 pdfminer.six（对英文年报常更稳）
    if not out or _is_garbled_text(out):
        try:
            from pdfminer.high_level import extract_text as _pdfminer_extract_text

            # pdfminer 的 page_numbers 是 0-indexed
            page_numbers = [i for i in page_indices if i >= 0]
            txt = _pdfminer_extract_text(str(p), page_numbers=page_numbers) or ""
            txt = txt.strip()
            if txt and not _is_garbled_text(txt):
                out = txt
        except Exception:
            pass

    # 再 fallback 到 PyMuPDF（fitz）— 对 CID 字体编码的英文年报通常更稳
    if not out or _is_garbled_text(out):
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(p))
            buf: list[str] = []
            for i in [i for i in page_indices if 0 <= i < int(doc.page_count or 0)]:
                try:
                    page = doc.load_page(i)
                    t = page.get_text("text") or ""
                    if t:
                        buf.append(t)
                except Exception:
                    continue
            try:
                doc.close()
            except Exception:
                pass
            txt = "\n\n".join(buf).strip()
            if txt and not _is_garbled_text(txt):
                out = txt
        except Exception:
            pass

    # 再 fallback 到 pypdf（有时能拿到更干净的文本）
    if not out or _is_garbled_text(out):
        try:
            from pypdf import PdfReader

            r = PdfReader(str(p))
            buf: list[str] = []
            for i in [i for i in page_indices if 0 <= i < len(r.pages)]:
                try:
                    t = r.pages[i].extract_text() or ""
                    if t:
                        buf.append(t)
                except Exception:
                    continue
            txt = "\n\n".join(buf).strip()
            if txt and not _is_garbled_text(txt):
                out = txt
        except Exception:
            pass
    
    # 如果文本是乱码/过短，尝试 OCR
    try:
        min_chars2 = int((os.environ.get("PDF_TEXT_MIN_CHARS_FOR_NO_OCR") or "800").strip() or "800")
    except Exception:
        min_chars2 = 800

    too_short2 = False
    try:
        s2 = (out or "").strip()
        digit_cnt2 = sum(1 for ch in s2 if ch.isdigit())
        too_short2 = (len(s2) < min_chars2) or (digit_cnt2 < 20)
    except Exception:
        too_short2 = False

    if _is_garbled_text(out) or too_short2:
        _maybe_debug(f"pdf_text: triggering final ocr; len={len((out or '').strip())} too_short={too_short2}")
        ocr_text = _extract_with_ocr(str(p), max_pages)
        if ocr_text:
            ocr_text = _strip_ctrl(ocr_text)
            if (not _is_garbled_text(ocr_text)) or _looks_like_useful_english(ocr_text):
                out = ocr_text

    return _truncate(out)
