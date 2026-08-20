"""Sidecar naming and Markdown shaping helpers."""

import re
from pathlib import Path
from urllib.parse import quote

MARKDOWN_IMAGE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(\s*(?P<target><[^>\n]+>|[^)\n]+?)\s*\)(?:\{[^}\n]*\})?"
)
HTML_IMAGE = re.compile(r"<img\b(?P<attrs>[^>]*)>", re.IGNORECASE)
HTML_ALT = re.compile(r"\balt\s*=\s*(['\"])(?P<alt>.*?)\1", re.IGNORECASE)
SOURCE_HEADER = "<!-- source-reference -->"


def resolve_sidecar(src: Path):
    """Return a stable Markdown sidecar path for a source document."""
    rivals = [
        candidate
        for candidate in src.parent.iterdir()
        if candidate != src
        and candidate.is_file()
        and candidate.stem.casefold() == src.stem.casefold()
        and candidate.suffix.lower() != ".md"
    ]
    if not rivals:
        return src, src.with_suffix(".md"), None

    owner = min([src, *rivals], key=lambda p: (p.stat().st_mtime, p.name))
    if owner == src:
        return src, src.with_suffix(".md"), None

    base = f"{src.stem}-{src.suffix.lstrip('.').lower()}"
    renamed = src.with_name(base + src.suffix)
    counter = 2
    while renamed.exists() or renamed.with_suffix(".md").exists():
        renamed = src.with_name(f"{base}-{counter}{src.suffix}")
        counter += 1

    src.rename(renamed)
    return renamed, renamed.with_suffix(".md"), f"{src.name} -> {renamed.name}"


def _useful_image_alt(alt: str) -> str:
    alt = " ".join(alt.split())
    if alt.casefold() in {"", "image", "img", "picture", "photo"}:
        return ""
    if re.fullmatch(r"(?:image|img|picture|photo)\s*\d*", alt, re.I):
        return ""
    if re.fullmatch(r"\d+", alt):
        return ""
    if re.search(r"[\\/]", alt) and re.search(
        r"\.(?:png|jpe?g|gif|bmp|tiff?|webp|svg)$", alt, re.I
    ):
        return ""
    return alt


def remove_image_references(text: str) -> str:
    """Strip image markup while preserving useful alt text."""
    text = MARKDOWN_IMAGE.sub(lambda m: _useful_image_alt(m.group("alt")), text)

    def replace_html_image(match):
        alt_match = HTML_ALT.search(match.group("attrs"))
        return _useful_image_alt(alt_match.group("alt")) if alt_match else ""

    return HTML_IMAGE.sub(replace_html_image, text)


def add_source_reference(text: str, src: Path, method: str, warning: str | None = None) -> str:
    """Prepend a same-folder link to the source document."""
    display_name = src.name.replace("[", r"\[").replace("]", r"\]")
    target = quote(src.name, safe="!$&'()+,;=@[]_-~.")
    lines = [
        SOURCE_HEADER,
        f"> Source: [{display_name}](<{target}>)",
        f"> Conversion: {method}",
        "> Review: verify tables, numbers, images, and suspicious output against the original file",
    ]
    if warning:
        lines.append(f"> Warning: {warning}")
    return "\n".join(lines) + "\n\n" + text.lstrip("\n")
