"""Command-line interface for docpipe-md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .route import convert_one
from .sidecar import resolve_sidecar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docpipe-md",
        description="Convert a supported document to Markdown with quality checks and OCR fallback.",
    )
    parser.add_argument("source", type=Path, help="PDF, PPTX, DOCX, HWP/HWPX, ODT, RTF, or HTML file")
    parser.add_argument("-o", "--output", type=Path, default=None, help="output Markdown path")
    args = parser.parse_args(argv)

    source = args.source
    if not source.is_file():
        print(f"No such file: {source}", file=sys.stderr)
        return 1

    try:
        if args.output is None:
            source, output, rename_note = resolve_sidecar(source)
            if rename_note:
                print(f"Renamed source to avoid a sidecar collision: {rename_note}")
        else:
            output = args.output

        markdown = convert_one(source)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
        print(output)
        return 0
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
