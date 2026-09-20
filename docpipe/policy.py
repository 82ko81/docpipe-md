"""Single definition of the constants every entry point has to agree on.

These used to be copied per entry point; a value updated on only one side let
the same file take a different path depending on how it arrived.
"""

SKIP_EXTENSIONS = {".md", ".csv", ".txt"}
UNHWP_EXTENSIONS = {".hwp", ".hwpx"}
PANDOC_EXTENSIONS = {".docx", ".pptx", ".odt", ".rtf", ".html", ".htm"}
# Legacy .xls is deliberately absent: openpyxl cannot read it, so it stays on
# the markitdown path.
OPENPYXL_EXTENSIONS = {".xlsx", ".xlsm"}

NO_CONVERTER_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".zip", ".aac", ".m4a", ".mp3", ".wav",
    ".json", ".py",
}

# Corporate seal certificates / bank passbooks / ID scans -- identity-adjacent
# documents that stay unconverted (not OCR'd, not made text-searchable) by
# default across any project, regardless of entry point (inbox classification
# or whole-project sweep). Add project-specific terms as needed.
SENSITIVE_NAME_MARKERS = ("인감증명서", "법인통장", "주민등록증", "여권사본")
