# docpipe-md

Reliable document-to-Markdown conversion with OCR fallback and per-page quality checks.

`docpipe-md` is a small Python conversion layer for turning office documents into Markdown without assuming that a converter succeeded just because it returned text. PDF pages and PowerPoint slides are checked individually, so dense pages cannot hide empty or broken ones.

## Features

- **PDF**: structured extraction with `pymupdf4llm`, page-level quality checks, and targeted Korean + English OCR fallback
- **PPTX**: text, tables, chart titles, and nested group shapes via `python-pptx`
- **DOCX / ODT / RTF / HTML**: MarkItDown with Pandoc fallback
- **HWP / HWPX**: `unhwp`
- **Source-aware Markdown**: generated files include a link back to the original document and a warning when extraction quality looks suspicious

## Install

```bash
pip install -e .
```

For full format support, install the relevant system tools:

- Tesseract OCR with Korean (`kor`) and English (`eng`) language data
- Poppler (`pdftoppm`) for PDF page rendering
- Pandoc for fallback document conversion
- `unhwp` for HWP/HWPX conversion

## Usage

```bash
docpipe-md report.pdf
```

By default, the command writes `report.md` beside the source file.

```bash
docpipe-md slides.pptx -o slides.md
```

You can also use the package directly:

```python
from pathlib import Path
from docpipe import convert_one

markdown = convert_one(Path("report.pdf"))
print(markdown)
```

## Why this exists

Most document converters judge success at the whole-document level. That can hide partial failures: a long PDF may look healthy overall while dozens of pages contain no extracted text. `docpipe-md` keeps page/slide units long enough to detect that failure and selectively OCR only the PDF pages that need it.

## License

MIT
