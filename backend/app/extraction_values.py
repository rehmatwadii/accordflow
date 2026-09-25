"""Conservative normalization and spatial reconstruction for document extraction."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from statistics import median


def document_date(value):
    value = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", value.strip(), flags=re.I)
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    ):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    parts = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", value)
    if parts:
        a, b, year = map(int, parts.groups())
        # Resolve only if there is one possible interpretation.
        if a == b or a > 12 or b > 12:
            day, month = (a, b) if a > 12 or a == b else (b, a)
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                pass
    return None


def document_number(value):
    value = re.sub(r"^(?:USD|EUR|GBP|PKR|AED|CNY|JPY|[$\u20ac\u00a3])\s*", "", value.strip(), flags=re.I)
    value = re.sub(r"\s*(?:USD|EUR|GBP|PKR|AED|CNY|JPY)$", "", value, flags=re.I)
    if re.fullmatch(r"\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", value):
        value = value.replace(",", "").replace(" ", "")
    elif re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}", value):
        value = value.replace(".", "").replace(",", ".")
    else:
        return None
    try:
        return value if Decimal(value) > 0 else None
    except InvalidOperation:
        return None


def overlay_text(page):
    """Rebuild OCR columns using word coordinates rather than flattened text."""
    overlay = page.get("TextOverlay") or {}
    words = [
        w
        for line in overlay.get("Lines", [])
        for w in line.get("Words", [])
        if isinstance(w.get("WordText"), str)
        and w["WordText"].strip()
        and all(isinstance(w.get(k), (int, float)) for k in ("Left", "Top", "Width", "Height"))
    ]
    if not words:
        return page.get("ParsedText") or ""
    widths = [w["Width"] / len(w["WordText"]) for w in words if w["Width"] > 0]
    unit = max(1, median(widths)) if widths else 5
    rows = []
    for word in sorted(words, key=lambda w: (w["Top"], w["Left"])):
        row = next(
            (r for r in reversed(rows[-3:]) if abs(r[0] - word["Top"]) <= max(2, word["Height"] * 0.45)), None
        )
        if row is None:
            row = [word["Top"], []]
            rows.append(row)
        row[1].append(word)
    result = []
    for _, row in rows:
        text, edge = "", 0
        for word in sorted(row, key=lambda w: w["Left"]):
            gap = word["Left"] - edge
            spaces = (
                max(1, min(300, round(gap / unit))) if text else max(0, min(300, round(word["Left"] / unit)))
            )
            if text and gap < unit * 2:
                spaces = 1
            text += " " * spaces + word["WordText"]
            edge = word["Left"] + word["Width"]
        result.append(text)
    return "\n".join(result)
