"""Pick a converter per extension and shape the result into a sidecar body."""

from pathlib import Path

from .converters import (
    convert_with_markitdown,
    convert_with_ocr,
    convert_with_pandoc,
    convert_with_pptx,
    convert_with_pymupdf,
    convert_with_pymupdf4llm,
    convert_with_unhwp,
    convert_with_xlsx,
)
from .policy import OPENPYXL_EXTENSIONS, PANDOC_EXTENSIONS, UNHWP_EXTENSIONS
from .quality import empty_unit_indexes, text_quality_issue, unit_quality_issue
from .sidecar import add_source_reference, remove_image_references


def _convert_pdf(src: Path):
    """Structured per-page extraction, OCR-ing only the pages that came back empty.

    Falls back to the old whole-document get_text() + full-document OCR path
    when pymupdf4llm itself fails or times out -- convert_with_pymupdf stays
    in place as that safety net.
    """
    try:
        pages = convert_with_pymupdf4llm(src)
    except Exception:
        pages = None

    if pages is None:
        text = convert_with_pymupdf(src)
        issue = text_quality_issue(text)
        if not issue:
            return text, "PDF 텍스트 추출", None
        text = convert_with_ocr(src)
        warning = issue
        ocr_issue = text_quality_issue(text)
        if ocr_issue:
            warning = f"{issue}; OCR 결과도 {ocr_issue}"
        return text, "OCR (한국어+영어)", warning

    method = "PDF 구조 추출 (pymupdf4llm)"
    empty = empty_unit_indexes(pages)
    if empty:
        ocr_pages = convert_with_ocr(src, pages=empty)
        for index in empty:
            ocr_text = ocr_pages.get(index)
            if ocr_text:
                pages[index] = ocr_text
        method = "PDF 구조 추출 + 페이지 OCR (한국어+영어)"

    text = "\n\n".join(pages)
    warning = unit_quality_issue(pages, "페이지", empty_is_loss=True)
    return text, method, warning


def _convert_pptx(src: Path):
    """python-pptx structured extraction; None sends the caller to markitdown/pandoc.

    Group-shape recursion and per-slide density judging are the point (see
    convert_with_pptx); any failure here -- a corrupt file, an unsupported
    pptx feature -- falls back to the pre-existing path rather than failing
    the whole document.
    """
    try:
        slides = convert_with_pptx(src)
    except Exception:
        return None
    text = "\n\n".join(slides)
    warning = unit_quality_issue(slides, "슬라이드", empty_is_loss=False)
    return text, "PPTX 구조 추출 (python-pptx)", warning


def _convert_xlsx(src: Path):
    """openpyxl structured extraction; None sends the caller to markitdown.

    Avoiding markitdown's pandas path is the whole reason this exists (see
    _cell_text). Legacy .xls never arrives here because openpyxl cannot read
    it; anything else that fails -- a corrupt workbook, an unsupported
    feature -- falls back rather than failing the document.
    """
    try:
        sheets, hidden = convert_with_xlsx(src)
    except Exception:
        return None
    warning = None
    if hidden:
        warning = (
            f"원본에서 숨김 상태였던 시트 {len(hidden)}개가 그대로 포함됨: "
            + ", ".join(hidden)
        )
    return "\n\n".join(sheets), "XLSX 구조 추출 (openpyxl)", warning


def _convert_markitdown_then_pandoc(src: Path, ext: str):
    try:
        return convert_with_markitdown(src), "문서 텍스트 변환"
    except Exception as md_err:
        if ext in PANDOC_EXTENSIONS:
            try:
                return convert_with_pandoc(src), "Pandoc 텍스트 변환"
            except Exception as pandoc_err:
                raise RuntimeError(f"markitdown: {md_err} | pandoc: {pandoc_err}")
        raise RuntimeError(f"markitdown: {md_err}")


def convert_record(src: Path) -> dict:
    """The sidecar text plus what produced it: {"text", "method", "warning"}.

    convert_one returns only the finished Markdown, which leaves the method
    and the quality warning living as prose inside the header and nowhere
    else. The manifest writers need them as values.
    """
    ext = src.suffix.lower()
    warning = None
    if ext in UNHWP_EXTENSIONS:
        text = convert_with_unhwp(src)
        method = "HWP/HWPX 텍스트 변환"
    elif ext == ".pdf":
        text, method, warning = _convert_pdf(src)
    elif ext == ".pptx":
        pptx_result = _convert_pptx(src)
        if pptx_result is not None:
            text, method, warning = pptx_result
        else:
            text, method = _convert_markitdown_then_pandoc(src, ext)
    elif ext in OPENPYXL_EXTENSIONS:
        xlsx_result = _convert_xlsx(src)
        if xlsx_result is not None:
            text, method, warning = xlsx_result
        else:
            text, method = _convert_markitdown_then_pandoc(src, ext)
    else:
        text, method = _convert_markitdown_then_pandoc(src, ext)
    text = remove_image_references(text)
    if not warning:
        warning = text_quality_issue(text)
    return {
        "text": add_source_reference(text, src, method, warning),
        "method": method,
        "warning": warning,
    }


def convert_one(src: Path) -> str:
    return convert_record(src)["text"]
