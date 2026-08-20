"""Quality checks for extracted document text."""

import statistics

MIN_UNIT_CHARS = 20


def _compact_len(text: str) -> int:
    return len("".join(text.split()))


def empty_unit_indexes(units: list[str]) -> list[int]:
    """Return indexes for pages or slides that yielded no text."""
    return [index for index, unit in enumerate(units) if not _compact_len(unit)]


def unit_quality_issue(units: list[str], unit_label: str, *, empty_is_loss: bool) -> str | None:
    """Return a warning when page/slide-level extraction looks incomplete."""
    if not units:
        return None

    empty = empty_unit_indexes(units)
    if len(empty) == len(units):
        return None

    reasons: list[str] = []
    if empty_is_loss and empty:
        reasons.append(f"{len(empty)} of {len(units)} {unit_label}(s) produced no text")

    typical = statistics.median(_compact_len(unit) for unit in units)
    if typical < MIN_UNIT_CHARS:
        reasons.append(
            f"median extracted text is only {typical:.0f} characters per {unit_label}; content loss is possible"
        )
    return "; ".join(reasons) or None


def text_quality_issue(text: str) -> str | None:
    """Return a warning when extracted text is too weak to trust."""
    compact = "".join(text.split())
    if not compact:
        return "no text was extracted"
    if len(compact) < 40:
        return "very little text was extracted"
    if text.count("(cid:") >= 5:
        return "PDF font mapping appears broken (cid markers detected)"
    if text.count("�") >= 5 or text.count("�") / max(len(text), 1) > 0.01:
        return "a high proportion of replacement characters was detected"
    return None
