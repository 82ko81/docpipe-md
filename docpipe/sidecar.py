"""Sidecar naming and the Markdown shaping that goes around converted text."""

import re
from pathlib import Path
from urllib.parse import quote

MARKDOWN_IMAGE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(\s*(?P<target><[^>\n]+>|[^)\n]+?)\s*\)"
    r"(?:\{[^}\n]*\})?"
)
HTML_IMAGE = re.compile(r"<img\b(?P<attrs>[^>]*)>", re.IGNORECASE)
HTML_ALT = re.compile(r"\balt\s*=\s*(['\"])(?P<alt>.*?)\1", re.IGNORECASE)
SOURCE_HEADER = "<!-- source-reference -->"


def resolve_sidecar(src: Path):
    """Give every source a plain <stem>.md sidecar.

    When two sources share a stem, the older one keeps <stem>.md and the later
    one is renamed to <stem>-<ext>.<ext>, so each sidecar name still maps back
    to exactly one source. Returns (source, sidecar, rename note or None); the
    source may differ from the argument when a rename happened.
    """
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

    # Oldest source owns the plain name; ties break on filename so two runs
    # never disagree about who owns it.
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
    if alt.casefold() in {
        "",
        "image",
        "img",
        "picture",
        "photo",
        "첨부파일 아이콘",
    }:
        return ""
    if re.fullmatch(r"(?:그림|그래픽|image|img|picture|photo)\s*\d*", alt, re.I):
        return ""
    if re.fullmatch(r"\d+", alt):
        return ""
    if re.search(r"[\\/]", alt) and re.search(
        r"\.(?:png|jpe?g|gif|bmp|tiff?|webp|svg)$", alt, re.I
    ):
        return ""
    return alt


def remove_image_references(text: str) -> str:
    """Remove image markup when the single-file pipeline keeps text only."""

    def replace_markdown_image(match):
        return _useful_image_alt(match.group("alt"))

    text = MARKDOWN_IMAGE.sub(replace_markdown_image, text)

    def replace_html_image(match):
        alt_match = HTML_ALT.search(match.group("attrs"))
        return _useful_image_alt(alt_match.group("alt")) if alt_match else ""

    return HTML_IMAGE.sub(replace_html_image, text)


def add_source_reference(text: str, src: Path, method: str, warning=None) -> str:
    """Prepend a stable same-folder link back to the source file."""

    display_name = src.name.replace("[", r"\[").replace("]", r"\]")
    target = quote(src.name, safe="!$&'()+,;=@[]_-~.")
    lines = [
        SOURCE_HEADER,
        f"> 원본: [{display_name}](<{target}>)",
        f"> 변환: {method}",
        "> 확인: 표·숫자·이미지와 변환이 이상한 부분은 원본을 기준으로 확인",
    ]
    if warning:
        lines.append(f"> 원본 확인 필요: {warning}")
    return "\n".join(lines) + "\n\n" + text.lstrip("\n")
