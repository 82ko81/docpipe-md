# docpipe-md

Reliable document-to-Markdown conversion with selective OCR, per-unit quality checks, faithful spreadsheet rendering, and machine-readable conversion records.

This repository is the standalone distribution of the reusable document-conversion core used in `82ko81/workspace`. The current core is synchronized from Workspace commit `388fc00ae7b4a69188af900e0f0d378b6fa38eb3` (2026-09-09).

## Features

- **PDF**: structured extraction with `pymupdf4llm`, page-level quality checks, and targeted Korean + English OCR for pages with no text layer
- **PPTX**: text, tables, chart titles, and nested group shapes via `python-pptx`
- **XLSX / XLSM**: direct `openpyxl` rendering instead of pandas coercion; hidden sheets are labeled and warned, and only vertical merged cells are filled downward
- **DOCX / ODT / RTF / HTML**: MarkItDown with Pandoc fallback
- **HWP / HWPX**: `unhwp`
- **Source-aware Markdown**: generated sidecars link back to the original and record conversion method and warnings
- **Structured results**: `convert_record()` returns `text`, `method`, and `warning`
- **Run manifests**: `write_manifest()` maintains a merge-preserving `_manifest.json`

## Install

```bash
pip install -e .
```

For full format support, install the relevant system tools:

- Tesseract OCR with Korean (`kor`) and English (`eng`) language data
- Poppler (`pdftoppm`)
- Pandoc
- `unhwp`

## CLI

```bash
docpipe-md report.pdf
docpipe-md workbook.xlsx
docpipe-md slides.pptx -o slides.md
```

By default, the CLI writes `<stem>.md` beside the source.

## Python API

```python
from pathlib import Path
from docpipe import convert_one, convert_record

markdown = convert_one(Path("report.pdf"))

record = convert_record(Path("workbook.xlsx"))
print(record["method"])
print(record["warning"])
print(record["text"])
```

A caller that converts batches can keep a queryable manifest:

```python
from pathlib import Path
from docpipe import entry, write_manifest

write_manifest(
    Path("_manifest.json"),
    [
        entry(
            "report.pdf",
            "converted",
            sidecar="report.md",
            method="PDF 구조 추출 (pymupdf4llm)",
        )
    ],
)
```

## Why XLSX bypasses MarkItDown

The Workspace corpus exposed pandas-backed spreadsheet distortions: empty cells materialized as `NaN`, blank leading rows generated `Unnamed: ...` headers, and mixed-type year columns could render in scientific notation. The current XLSX path reads stored values directly with `openpyxl`.

The 2026-09-09 implementation was measured over 231 workbooks before being promoted in Workspace.

## Version lineage

- Current upstream source: `82ko81/workspace`, branch `docpipe/xlsx-renderer-and-manifest`
- Synced feature commit: `388fc00ae7b4a69188af900e0f0d378b6fa38eb3`
- Previous standalone state: commit `f25064bb6a278c5cce1aa424c97551197a8a598b`
- Previous standalone archive: branch `archive/standalone-2026-08-20`

See `CHANGELOG.md` and `SYNC_PROVENANCE.md`.

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the same regression suite on pushes and pull requests.

## License

MIT
