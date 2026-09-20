"""Document conversion layer shared by every entry point.

Knows nothing about workspace locations: a caller hands it a file and gets
Markdown back. Path policy (inbox, recordings queue, project roots) stays in
the entry-point scripts.
"""

from .manifest import MANIFEST_NAME, entry, write_manifest
from .route import convert_one, convert_record
from .sidecar import resolve_sidecar

__all__ = [
    "MANIFEST_NAME",
    "convert_one",
    "convert_record",
    "entry",
    "resolve_sidecar",
    "write_manifest",
]
