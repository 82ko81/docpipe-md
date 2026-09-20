"""Quality judgement on extracted text."""

import statistics

# Characters a single page or slide has to carry before it counts as intact.
# Deliberately lower than the 40 text_quality_issue asks of a whole document:
# measured over the 207-file pptx corpus under raw/ (203 readable, 5,123
# slides), a per-unit floor of 40 flags 24 text-bearing files, 12 of them
# design templates whose placeholder text genuinely is 32-38 characters a
# slide. A floor of 20 flags none of them. 20 is where the warning still means
# "text went missing" rather than "this document is sparse", and a warning
# nobody can act on is worse than none -- it teaches the reader to skip the
# same line that carries the real findings.
MIN_UNIT_CHARS = 20


def _compact_len(text: str) -> int:
    return len("".join(text.split()))


def empty_unit_indexes(units):
    """Indexes of the units that extracted no text at all.

    Callers need the indexes rather than a count: the PDF path picks exactly
    these pages to send to OCR. pymupdf returning nothing for a page means the
    page carries no text layer, which is why this is an equality test and not a
    threshold.

    Only wholly empty units are found here. A page that yields a running head
    and nothing else -- some text, but the body is a picture -- is real and is
    not detected; catching it needs a per-unit image/text ratio, which is out
    of scope for now.
    """
    return [index for index, unit in enumerate(units) if not _compact_len(unit)]


def unit_quality_issue(units, unit_label, *, empty_is_loss):
    """Return a reason when the per-unit extraction looks lossy, else None.

    text_quality_issue only ever sees the concatenated document, so a handful
    of dense pages hides the pages that came back empty: a 69-page deck with 50
    unextractable pages still reaches it as 1,475 characters and passes. Judge
    the units separately instead.

    empty_is_loss says whether an empty unit is itself the defect, which is a
    per-format fact and not a preference. For a PDF page it is -- 10 documents,
    87 of 87 empty pages were genuinely missing their text layer. For a slide
    it is not: 204 of the corpus's 5,123 slides are legitimately image-only,
    34 of them inside one otherwise healthy deck.
    """
    if not units:
        return None

    empty = empty_unit_indexes(units)
    if len(empty) == len(units):
        # Nothing left to compare the empty units against, and
        # text_quality_issue already reports this document as having no text.
        # Saying it twice would put two warnings on every image-only deck.
        return None

    reasons = []
    if empty_is_loss and empty:
        reasons.append(
            f"{len(units)}{unit_label} 중 {len(empty)}{unit_label}에서 "
            "텍스트가 추출되지 않음"
        )
    # Median, not mean: one long appendix unit should not vouch for the rest.
    typical = statistics.median(_compact_len(unit) for unit in units)
    if typical < MIN_UNIT_CHARS:
        reasons.append(f"{unit_label}당 텍스트 중앙값 {typical:.0f}자로 본문 유실 의심")
    return "; ".join(reasons) or None


def text_quality_issue(text: str):
    """Return a reason when extracted text is too weak to trust without OCR."""

    compact = "".join(text.split())
    if not compact:
        return "추출된 텍스트 없음"
    if len(compact) < 40:
        return "추출된 텍스트가 너무 적음"
    if text.count("(cid:") >= 5:
        return "PDF 글꼴 매핑 오류(cid)"
    if text.count("�") >= 5 or text.count("�") / len(text) > 0.01:
        return "깨진 문자 비율이 높음"
    return None
