"""Document conversion utilities for producing Markdown from office files."""

from .route import convert_one
from .sidecar import resolve_sidecar

__all__ = ["convert_one", "resolve_sidecar"]
