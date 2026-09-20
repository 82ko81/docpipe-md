# Changelog

## 0.2.0 - 2026-09-21

Standalone package synchronized to the newer Workspace Docpipe implementation derived from upstream commit `388fc00ae7b4a69188af900e0f0d378b6fa38eb3` (2026-09-09).

### Added

- Direct XLSX/XLSM rendering with `openpyxl`
- Hidden-sheet labels and quality warnings
- Selective fill for vertical merged cells
- `convert_record()` structured result API
- `manifest.py` and merge-preserving `_manifest.json`
- Standalone regression tests and GitHub Actions CI
- Explicit synchronization provenance

### Changed

- Package version: 0.1.0 -> 0.2.0
- XLSX/XLSM no longer use the pandas-backed MarkItDown path
- Shared Markdown table rendering pads ragged rows to the widest row
- CLI help lists XLSX/XLSM

### Preserved

The previous standalone repository state at commit `f25064bb6a278c5cce1aa424c97551197a8a598b` is frozen on branch `archive/standalone-2026-08-20`.

## 0.1.0 - 2026-08-20

Initial standalone extraction of Docpipe from the Workspace implementation.
