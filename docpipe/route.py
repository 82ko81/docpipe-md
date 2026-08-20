"""Route documents to converters and shape the result as Markdown."""

from pathlib import Path

from .converters import (
    convert_with_markitdown,
    convert_with_ocr,
    convert_with_pandoc,
    convert_with_pptx,
    convert_with_pymupdf,
    convert_with_pymupdf4llm,
    convert_with_unhwp,
)
from .policy import PANDOC_EXTENSIONS, UNHWP_EXTENSIONS
from .quality import empty_unit_indexes, text_quality_issue, unit_quality_issue
from .sidecar import add_source_reference, remove_image_references


def _convert_pdf(src: Path):
    try:
        pages = convert_with_pymupdf4llm(src)
    except Exception:
        pages = None

    if pages is None:
        text = convert_with_pymupdf(src)
        issue = text_quality_issue(text)
        if not issue:
            return text, "PDF text extraction", None
        text = convert_with_ocr(src)
        warning = issue
        ocr_issue = text_quality_issue(text)
        if ocr_issue:
            warning = f"{issue}; OCR output also looks weak: {ocr_issue}"
        return text, "OCR (Korean + English)", warning

    method = "Structured PDF extraction (pymupdf4llm)"
    empty = empty_unit_indexes(pages)
    if empty:
        ocr_pages = convert_with_ocr(src, pages=empty)
        for index in empty:
            ocr_text = ocr_pages.get(index)
            if ocr_text:
                pages[index] = ocr_text
        method = "Structured PDF extraction + targeted OCR (Korean + English)"

    text = "\n\n".join(pages)
    warning = unit_quality_issue(pages, "page", empty_is_loss=True)
    return text, method, warning


def _convert_pptx(src: Path):
    try:
        slides = convert_with_pptx(src)
    except Exception:
        return None
    text = "\n\n".join(slides)
    warning = unit_quality_issue(slides, "slide", empty_is_loss=False)
    return text, "Structured PPTX extraction (python-pptx)", warning


def _convert_markitdown_then_pandoc(src: Path, ext: str):
    try:
        return convert_with_markitdown(src), "Document text conversion (MarkItDown)"
    except Exception as md_err:
        if ext in PANDOC_EXTENSIONS:
            try:
                return convert_with_pandoc(src), "Document text conversion (Pandoc)"
            except Exception as pandoc_err:
                raise RuntimeError(f"MarkItDown: {md_err} | Pandoc: {pandoc_err}") from pandoc_err
        raise RuntimeError(f"MarkItDown: {md_err}") from md_err


def convert_one(src: Path) -> str:
    """Convert one supported document to Markdown text."""
    src = Path(src)
    ext = src.suffix.lower()
    warning = None

    if ext in UNHWP_EXTENSIONS:
        text = convert_with_unhwp(src)
        method = "HWP/HWPX conversion (unhwp)"
    elif ext == ".pdf":
        text, method, warning = _convert_pdf(src)
    elif ext == ".pptx":
        pptx_result = _convert_pptx(src)
        if pptx_result is not None:
            text, method, warning = pptx_result
        else:
            text, method = _convert_markitdown_then_pandoc(src, ext)
    else:
        text, method = _convert_markitdown_then_pandoc(src, ext)

    text = remove_image_references(text)
    if not warning:
        warning = text_quality_issue(text)
    return add_source_reference(text, src, method, warning)
