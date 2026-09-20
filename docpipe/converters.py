"""External converters and the binary discovery they depend on."""

import datetime
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
PANDOC_CANDIDATES = [shutil.which("pandoc"), *LOCAL_APPDATA.glob(
    "Microsoft/WinGet/Packages/JohnMacFarlane.Pandoc_*/pandoc-*/pandoc.exe"
)]
PANDOC_BIN = next((p for p in PANDOC_CANDIDATES if p and Path(p).exists()), None)

UNHWP_CANDIDATES = [
    shutil.which("unhwp"),
    LOCAL_APPDATA / "Microsoft" / "WindowsApps" / "unhwp.exe",
]
UNHWP_BIN = next((p for p in UNHWP_CANDIDATES if p and Path(p).exists()), None)

if os.name == "nt":
    TESSDATA_DIR = LOCAL_APPDATA / "tessdata"
else:
    tessdata_candidates = [
        Path(os.environ["TESSDATA_PREFIX"]) if os.environ.get("TESSDATA_PREFIX") else None,
        Path("/opt/homebrew/share/tessdata"),
        Path("/usr/local/share/tessdata"),
    ]
    TESSDATA_DIR = next(
        (path for path in tessdata_candidates if path and path.exists()),
        Path("/usr/local/share/tessdata"),
    )
TESSERACT_BIN = shutil.which("tesseract") or str(
    Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    / "Tesseract-OCR"
    / "tesseract.exe"
)
POPPLER_BIN = shutil.which("pdftoppm") or next(
    (
        str(path)
        for path in LOCAL_APPDATA.glob(
            "Microsoft/WinGet/Packages/oschwartz10612.Poppler_*/poppler-*/Library/bin/pdftoppm.exe"
        )
    ),
    None,
)

# pymupdf4llm claims 8+ cores by default and does not respond to
# OMP_NUM_THREADS -- only cpu_affinity works (measured). Restricting to 4
# roughly triples wall-clock time for the same output, which is the trade a
# machine that has to stay usable during a batch run needs to make.
PDF_CPU_LIMIT = 4
# Generous headroom over the slowest known-legitimate document (506 pages,
# ~29 minutes at the 4-core limit) so only a genuinely hung/pathological PDF
# trips this and falls back to get_text().
PDF_TIMEOUT_SECONDS = 1800

PAGE_IMAGE_RE = re.compile(r"-(\d+)\.png$")


def convert_with_unhwp(src: Path) -> str:
    if not UNHWP_BIN:
        raise RuntimeError("unhwp not found")
    with tempfile.TemporaryDirectory() as td:
        # Use the markdown subcommand, not the default converter: default
        # conversion creates <stem>_output/images beside its input. The
        # persistent contract is one Markdown sidecar and no extracted assets.
        # Keep the short temporary input because deeply nested Drive paths have
        # failed in unhwp before.
        local_src = Path(td) / src.name
        output_md = Path(td) / "extract.md"
        shutil.copy2(src, local_src)
        result = subprocess.run(
            [UNHWP_BIN, "md", local_src.name, "-o", output_md.name],
            cwd=td,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or not output_md.exists():
            raise RuntimeError(
                f"unhwp did not produce Markdown (exit {result.returncode}): "
                f"{result.stdout.strip()} {result.stderr.strip()}"
            )
        return output_md.read_text(encoding="utf-8")


def convert_with_markitdown(src: Path) -> str:
    from markitdown import MarkItDown

    # markitdown's own exceptions (UnsupportedFormatException,
    # FileConversionException) subclass BaseException directly, not
    # Exception -- a plain `except Exception` at the call site silently
    # fails to catch them and crashes the whole batch. Normalize to
    # RuntimeError (a real Exception) so callers can catch it.
    try:
        return MarkItDown().convert(str(src)).text_content
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:
        raise RuntimeError(str(e)) from e


def convert_with_pandoc(src: Path) -> str:
    if not PANDOC_BIN:
        raise RuntimeError("pandoc not found")
    result = subprocess.run(
        [PANDOC_BIN, str(src), "-t", "markdown", "--wrap=none"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout


def convert_with_pymupdf(src: Path) -> str:
    # markitdown's PDF path goes through pdfminer, which chokes on large
    # scanned PDFs (zlib decompression MemoryError deep in a C-level
    # allocation that can escape normal exception handling and kill an
    # entire batch run). PyMuPDF (fitz) is a C-library-backed extractor
    # that handles the same files in seconds without the memory blowup.
    import fitz

    doc = fitz.open(str(src))
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()


def convert_with_pymupdf4llm(src: Path, timeout: float = PDF_TIMEOUT_SECONDS) -> list:
    # Structured extraction (tables, headings) instead of plain get_text().
    # Runs on a daemon worker thread so a pathological PDF that never returns
    # can't block the batch: the caller gets a TimeoutError back and falls
    # through to convert_with_pymupdf, and the stuck thread is abandoned
    # (daemon=True keeps it from blocking interpreter exit).
    import psutil

    psutil.Process().cpu_affinity(list(range(PDF_CPU_LIMIT)))

    outcome = {}

    def run():
        import pymupdf4llm

        try:
            outcome["pages"] = pymupdf4llm.to_markdown(str(src), page_chunks=True)
        except Exception as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise TimeoutError(f"pymupdf4llm exceeded {timeout}s on {src.name}")
    if "error" in outcome:
        raise outcome["error"]
    return [page["text"] for page in outcome["pages"]]


def convert_with_ocr(src: Path, pages=None):
    # Purely-scanned PDFs have no text layer at all -- pymupdf/pdfminer
    # return empty output for these no matter what. Rasterize each page and
    # run Tesseract (Korean + English) over the images instead.
    #
    # Both pdf2image's default mode AND pytesseract's own subprocess call
    # capture the child's stdout through a pipe read in a background thread;
    # on some renders that reader thread itself hits a MemoryError, which --
    # being a background thread -- doesn't propagate, it just dies, the
    # child blocks writing to the now-unread pipe, and the whole batch
    # deadlocks instead of failing cleanly. PyMuPDF page rendering avoids
    # that, but is stricter about malformed PDFs than poppler and outright
    # fails to open some real-world scans that poppler tolerates fine.
    # So: render pages with pdftoppm writing straight to files (no pipe,
    # and poppler's lenient parser), then OCR each file with the same
    # file-in/file-out tesseract.exe call used elsewhere -- nothing in this
    # path ever goes through a captured pipe.
    # pages, when given, is a 0-indexed list of pages to OCR instead of the
    # whole document -- the caller already knows which pages pymupdf4llm came
    # back empty on and there is no reason to re-rasterize the rest.
    if not POPPLER_BIN:
        raise RuntimeError("pdftoppm not found")
    if not Path(TESSERACT_BIN).exists():
        raise RuntimeError("tesseract not found")
    with tempfile.TemporaryDirectory() as td:
        prefix = Path(td) / "page"
        if pages is None:
            subprocess.run(
                [POPPLER_BIN, "-png", "-r", "200", str(src), str(prefix)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # poppler numbers output files by the page's real position in the
            # source document (zero-padded to the document's own page count),
            # not by position within the -f/-l range, so one run per
            # contiguous run of target pages is enough to keep every filename
            # mapped to the right page.
            for start, end in _contiguous_ranges(sorted(pages)):
                subprocess.run(
                    [
                        POPPLER_BIN, "-png", "-r", "200",
                        "-f", str(start + 1), "-l", str(end + 1),
                        str(src), str(prefix),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        page_images = sorted(
            Path(td).glob("page-*.png"),
            key=lambda p: int(PAGE_IMAGE_RE.search(p.name).group(1)),
        )
        if not page_images:
            raise RuntimeError("pdftoppm produced no page images")

        chunks = []
        by_page = {}
        out_base = Path(td) / "page_out"
        for png_path in page_images:
            subprocess.run(
                [
                    TESSERACT_BIN, str(png_path), str(out_base),
                    "-l", "kor+eng", "--tessdata-dir", str(TESSDATA_DIR),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            out_txt = out_base.with_suffix(".txt")
            text = ""
            if out_txt.exists():
                text = out_txt.read_text(encoding="utf-8", errors="replace")
                out_txt.unlink()
            png_path.unlink()
            if pages is None:
                chunks.append(text)
            else:
                page_number = int(PAGE_IMAGE_RE.search(png_path.name).group(1))
                by_page[page_number - 1] = text
        return by_page if pages is not None else "\n\n".join(chunks)


def _shape_markdown(shape, mso_shape_type):
    """Text/table/chart markdown for one shape, recursing into groups.

    markitdown's shape walk is flat (_markitdown.py:842) and never descends
    into MSO_SHAPE_TYPE.GROUP, which is where Korean consulting decks put
    their key-message boxes -- measured at 10.5% of a deck's text. Recursing
    here is the whole reason this converter exists over markitdown for pptx.
    """
    if shape.shape_type == mso_shape_type.GROUP:
        parts = []
        for child in shape.shapes:
            parts.extend(_shape_markdown(child, mso_shape_type))
        return parts

    parts = []
    if shape.has_table:
        parts.append(_table_markdown(shape.table))
    if shape.has_chart:
        # markitdown crashes here (_markitdown.py:952, IndexError when a
        # series has fewer values than categories) and takes the whole file
        # down with it. Chart data is a small share of deck text either way,
        # so on any failure just drop the chart and keep the rest of the slide.
        try:
            chart_text = _chart_markdown(shape.chart)
        except Exception:
            chart_text = ""
        if chart_text:
            parts.append(chart_text)
    if shape.has_text_frame:
        text = shape.text_frame.text.strip()
        if text:
            parts.append(text)
    return parts


def _escape_cell(text: str) -> str:
    """One grid cell as inline Markdown: no row break, no column break.

    In-cell line breaks become <br> rather than a space so a header like
    "판관비\\n<주2>" stays two lines in the rendered table instead of reading
    as one run-on label.
    """
    return text.strip().replace("\n", "<br>").replace("|", "\\|")


def _rows_markdown(rows) -> str:
    """Render a grid of already-escaped strings as one Markdown table.

    Rows are padded to the widest row, not to row 0: a sheet whose first row
    is a one-cell title would otherwise hide every later column behind a
    one-column separator.
    """
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    padded = [list(row) + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(row) + " |" for row in padded]
    lines.insert(1, "|" + "|".join(["---"] * width) + "|")
    return "\n".join(lines)


def _table_markdown(table) -> str:
    return _rows_markdown(
        [[_escape_cell(cell.text) for cell in row.cells] for row in table.rows]
    )


def _cell_text(value) -> str:
    """Excel's stored value as text, without pandas' column type coercion.

    markitdown routes xlsx through pandas, which forces one dtype per column:
    a column of years sharing a column with a text cell becomes float and
    prints as 2.025000e+03 (measured: 381 such cells in one KORAD template),
    and every empty cell arrives as the literal string NaN (129,881 across a
    30-workbook sample). Formatting the openpyxl value directly avoids both --
    an empty cell has no text and an int stays an int.
    """
    if value is None:
        return ""
    # bool before int: True would otherwise render as 1.
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    # datetime before date: datetime is a date subclass.
    if isinstance(value, datetime.datetime):
        if value.time() == datetime.time():
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _vertical_merge_fill(worksheet) -> dict:
    """Anchor value for each cell a single-column merge spans downward.

    Only column-wise merges are filled. Measured over the 231-workbook corpus:
    of 529,191 cells sitting behind a merge, 15,954 (3%) come from one column
    merged down several rows, where repeating the anchor is what the sheet
    means and makes each row self-contained. The other 97% are a label merged
    across columns; repeating those would manufacture 373,752 duplicate
    values, a worse distortion than leaving them empty.
    """
    fill = {}
    for cell_range in worksheet.merged_cells.ranges:
        if cell_range.min_col != cell_range.max_col:
            continue
        if cell_range.max_row == cell_range.min_row:
            continue
        anchor = worksheet.cell(cell_range.min_row, cell_range.min_col).value
        if anchor is None:
            continue
        for row in range(cell_range.min_row + 1, cell_range.max_row + 1):
            fill[(row, cell_range.min_col)] = anchor
    return fill


def convert_with_xlsx(src: Path):
    """Per-sheet Markdown, plus the names of the sheets hidden in the source.

    Returns (sheets, hidden). Sheets stay separate -- mirroring
    convert_with_pptx -- so the caller shapes the document without reopening
    the workbook, and hidden sheet names come back because a sheet the sender
    hid must not become indistinguishable from a visible one in the sidecar.
    """
    from openpyxl import load_workbook

    # read_only=True drops merged_cells.ranges, which _vertical_merge_fill
    # needs, so the workbook is opened normally.
    workbook = load_workbook(src, data_only=True)
    try:
        sheets, hidden = [], []
        for worksheet in workbook.worksheets:
            title = worksheet.title
            if worksheet.sheet_state != "visible":
                hidden.append(worksheet.title)
                title = f"{title} (원본에서 숨김 시트)"

            fill = _vertical_merge_fill(worksheet)
            rows = []
            for row in worksheet.iter_rows():
                cells = []
                for cell in row:
                    value = cell.value
                    if value is None:
                        value = fill.get((cell.row, cell.column))
                    cells.append(_escape_cell(_cell_text(value)))
                # Cell formatting alone inflates max_column, so the trailing
                # empties are an artifact.
                while cells and not cells[-1]:
                    cells.pop()
                rows.append(cells)
            # Blank rows at either end are layout padding, and a leading one
            # would become the table's header band. Interior blanks stay: a
            # blank row separating two tables is part of what the sheet says.
            while rows and not rows[-1]:
                rows.pop()
            while rows and not rows[0]:
                rows.pop(0)

            body = _rows_markdown(rows) if rows else "_(빈 시트)_"
            sheets.append(f"## {title}\n\n{body}")
        return sheets, hidden
    finally:
        workbook.close()


def _chart_markdown(chart) -> str:
    if not chart.has_title:
        return ""
    title = chart.chart_title.text_frame.text.strip()
    return f"**{title}**" if title else ""


def convert_with_pptx(src: Path) -> list:
    # markitdown/pandoc both take the whole file to one string; per-slide
    # units are kept here (mirroring convert_with_pymupdf4llm's per-page
    # list) so unit_quality_issue can judge slide density instead of the
    # whole-deck average hiding a few empty slides among the rest.
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    prs = Presentation(str(src))
    slides = []
    for slide in prs.slides:
        title_shape = slide.shapes.title
        parts = []
        if title_shape is not None and title_shape.has_text_frame:
            title_text = title_shape.text_frame.text.strip()
            if title_text:
                parts.append(f"# {title_text}")
        for shape in slide.shapes:
            if shape is title_shape:
                continue
            parts.extend(_shape_markdown(shape, MSO_SHAPE_TYPE))
        slides.append("\n\n".join(parts))
    return slides


def _contiguous_ranges(indexes):
    """Collapse a sorted list of page indexes into inclusive (start, end) runs."""
    ranges = []
    start = prev = None
    for index in indexes:
        if start is None:
            start = prev = index
        elif index == prev + 1:
            prev = index
        else:
            ranges.append((start, prev))
            start = prev = index
    if start is not None:
        ranges.append((start, prev))
    return ranges
