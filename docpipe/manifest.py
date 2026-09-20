"""Machine-readable record of what a conversion run produced.

The Markdown log beside it stays: that is append-only prose telling a human
what happened on a given day. This is the other half -- what the tree looks
like now, in a form something can query. Until it existed the conversion
method and the quality warning survived only as prose inside each sidecar's
header, so "which files warned" or "which carried a hidden sheet" meant
regexing every sidecar in the tree.
"""

import json
from datetime import datetime
from pathlib import Path, PurePath

MANIFEST_NAME = "_manifest.json"
SCHEMA = 1


def _relative(value) -> str:
    """Paths are stored with forward slashes so the file reads the same anywhere.

    Backslashes would also make the sort order and the record keys depend on
    which platform wrote the manifest.
    """
    return PurePath(value).as_posix()


def entry(path, outcome, **fields):
    """One file's record. Empty fields are dropped rather than stored as null.

    outcome is one of: converted, skipped, failed, no-converter, sensitive.
    """
    record = {"path": _relative(path), "outcome": outcome}
    for key in ("sidecar", "method", "warning", "renamed_from", "error"):
        value = fields.get(key)
        if not value:
            continue
        record[key] = _relative(value) if key == "sidecar" else str(value)
    return record


def _existing(path: Path) -> dict:
    """Entries already on disk, keyed by path; {} if unreadable.

    A manifest that cannot be parsed is replaced rather than raising: it is a
    derived index, and refusing to finish a conversion run over a damaged
    index would be the worse failure.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(document, dict) or not isinstance(document.get("files"), list):
        return {}
    return {
        record["path"]: record
        for record in document["files"]
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }


def write_manifest(path: Path, entries) -> dict:
    """Merge this run's entries into the manifest at path and write it back.

    Merged, not replaced: a rerun skips every file that already has a sidecar,
    so a fresh write would drop the method and warning belonging to each file
    the run did not touch -- exactly the rows a reader is querying for.
    """
    records = _existing(path)
    for record in entries:
        # A skip knows only that a sidecar exists -- no method, no warning. It
        # seeds a row for a file nothing has recorded yet (the first run over
        # an already-converted tree would otherwise produce an empty manifest)
        # but never displaces the richer row an earlier conversion wrote.
        if record["outcome"] == "skipped" and record["path"] in records:
            continue
        records[record["path"]] = record
    files = [records[key] for key in sorted(records)]

    counts = {}
    for record in files:
        outcome = record.get("outcome", "unknown")
        counts[outcome] = counts.get(outcome, 0) + 1
    counts["warned"] = sum(1 for record in files if record.get("warning"))

    document = {
        "schema": SCHEMA,
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "counts": counts,
        "files": files,
    }
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return document
