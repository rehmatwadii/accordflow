"""OCR.space text recognition and conservative, label-based trade field extraction."""

import os
import re
from decimal import Decimal

import httpx

from .errors import AppError
from .extraction_values import document_date, document_number, overlay_text


TYPES = {
    "INSURANCE_CERTIFICATE": r"INSURANCE CERTIFICATE",
    "BENEFICIARY_CERTIFICATE": r"BENEFICIARY['\u2019]S CERTIFICATE",
    "DRAFT": r"BILL OF EXCHANGE",
    "INSPECTION_CERTIFICATE": r"INSPECTION CERTIFICATE",
    "CERTIFICATE_OF_ORIGIN": r"CERTIFICATE OF ORIGIN",
    "PACKING_LIST": r"PACKING LIST",
    "BILL_OF_LADING": r"BILL OF LADING",
    "COMMERCIAL_INVOICE": r"COMMERCIAL INVOICE",
}


def detect_type(text):
    for kind, title in TYPES.items():
        if re.search(title, text[:500], re.I):
            return kind
    return None


def extract_fields(text: str, details=None) -> dict:
    # Normalize Markdown tables returned by advanced OCR without merging columns.
    rows = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            line = "    ".join(cells)
        rows.append(line.rstrip())
    text = "\n".join(rows).replace("\t", "    ").replace("\u00a0", " ")
    kind = detect_type(text)
    number_labels = {
        "COMMERCIAL_INVOICE": r"(?:commercial )?invoice (?:number|no\.?|#|ref(?:erence)?\.?)",
        "PACKING_LIST": r"packing list (?:number|no\.?|#)",
        "BILL_OF_LADING": r"b/?l (?:number|no\.?)|bill of lading (?:number|no\.?)",
        "DRAFT": r"(?:draft )?(?:no\.|number)",
        "INSURANCE_CERTIFICATE": r"certificate / policy (?:no\.?|number)|policy (?:no\.?|number)",
    }
    aliases = {
        "number": number_labels.get(
            kind,
            r"certificate (?:number|no\.?)|document (?:number|no\.?)"
            if kind
            else r"invoice (?:number|no\.?|#|ref(?:erence)?\.?)|document (?:number|no\.?)|certificate (?:number|no\.?)",
        ),
        "issue_date": r"invoice date|issue date|date of issue|document date|date of this certificate|date",
        "shipment_date": r"shipped on board date|shipment date|shipped on board",
        "amount": r"insured value|sum insured|insurance amount"
        if kind == "INSURANCE_CERTIFICATE"
        else r"grand total|total invoice (?:value|amount)|invoice total|total amount|invoice amount|amount due|amount",
        "currency": r"currency",
        "quantity": r"total quantity|quantity|qty\.?",
        "quantity_unit": r"quantity unit|unit of measure",
        "unit_price": r"unit price(?: \([A-Z]{3}\))?|price per unit",
        "applicant": r"buyer / applicant|applicant / buyer|consignee / applicant|applicant|buyer|bill to",
        "beneficiary": r"seller / beneficiary|shipper / beneficiary|beneficiary / seller|shipper / exporter|beneficiary|seller|exporter(?: \(name & address\))?",
        "consignee": r"consignee / applicant|consignee(?: \(name & address\))?",
        "notify_party": r"notify party",
        "loading_port": r"port of loading|loading port|load port",
        "discharge_port": r"port of discharge|discharge port|discharge port name",
        "country": r"country of origin|origin country",
        "vessel": r"vessel name|vessel",
        "incoterm": r"incoterms?",
    }

    def is_header(value):
        value = re.sub(r"^\d+\.\s+", "", value)
        return any(re.fullmatch(rf"(?:{label})[:#]?", value, re.I) for label in aliases.values()) or bool(
            re.fullmatch(r"Booking / Reference No\.|VESSEL / VOYAGE|CLAIMS PAYABLE AT / TO", value, re.I)
        )

    lines = text.splitlines()
    candidates = {}
    # Preserve horizontal gaps: a header and the value below it belong to the same column.
    for index, line in enumerate(lines):
        cells = list(re.finditer(r"\S(?:.*?\S)?(?= {2,}|$)", line))
        for cell_index, cell in enumerate(cells):
            content = re.sub(r"^\d+\.\s+", "", cell[0])
            for name, labels in aliases.items():
                match = re.match(rf"(?:{labels})(?=$|[ :#])[:#]?\s*(.*)$", content, re.I)
                if not match:
                    continue
                value = match[1].strip()
                if not value and cell_index + 1 < len(cells):
                    following = cells[cell_index + 1][0]
                    if not is_header(following):
                        value = following
                if not value:
                    next_line = next((row for row in lines[index + 1 : index + 4] if row.strip()), "")
                    next_cells = list(re.finditer(r"\S(?:.*?\S)?(?= {2,}|$)", next_line))
                    if len(cells) > 1 and len(next_cells) == len(cells):
                        value = next_cells[cell_index][0]
                    elif len(cells) == 1 and len(next_cells) == 1:
                        value = next_cells[0][0]
                if value:
                    candidates.setdefault(name, []).append(value)
    fields = {}
    evidence = {}
    conflicts = {}
    for name, values in candidates.items():
        for value in values:
            # Brackets and underscores are unfilled template content, never facts.
            if value.startswith(("[", "/")) or "__" in value or is_header(value):
                continue
            if name in {"issue_date", "shipment_date"}:
                parsed_date = document_date(value)
                if parsed_date:
                    fields[name] = parsed_date
            elif name in {"amount", "quantity", "unit_price"}:
                units = (
                    re.search(
                        r"\s+(MT|Metric Tons(?: \(MT\))?|KG|KGS|PCS|pieces|cartons|CTN|units)$", value, re.I
                    )
                    if name == "quantity"
                    else None
                )
                numeric = document_number(value[: units.start()] if units else value)
                if numeric:
                    fields[name] = numeric
                    if units:
                        unit = units[1].upper()
                        fields["quantity_unit"] = {
                            "METRIC TONS": "MT",
                            "METRIC TONS (MT)": "MT",
                            "KGS": "KG",
                            "PIECES": "PCS",
                            "CARTONS": "CTN",
                        }.get(unit, unit)
            elif name == "currency":
                if value.upper() in {"USD", "EUR", "GBP", "PKR", "AED", "CNY", "JPY"}:
                    fields[name] = value.upper()
            else:
                clean = re.split(r"\s*\[", value)[0].strip()
                if clean and not any(
                    re.fullmatch(rf"(?:{label})", clean, re.I) for label in aliases.values()
                ):
                    fields[name] = clean[:100]
            if name in fields:
                evidence[name] = {"source": value[:300], "method": "document label"}
                break
        # Never choose an arbitrary number/date when the document disagrees with itself.
        normalize = (
            document_date
            if name in {"issue_date", "shipment_date"}
            else document_number
            if name in {"amount", "unit_price"}
            else None
        )
        if normalize:
            distinct = {normalize(v) for v in values} - {None}
            if name in {"amount", "unit_price"}:
                distinct = {str(Decimal(v).normalize()) for v in distinct}
        elif name == "number":
            distinct = {
                v.strip()
                for v in values
                if not v.startswith(("[", "/")) and "__" not in v and not is_header(v)
            }
        else:
            distinct = set()
        if len(distinct) > 1:
            conflicts[name] = sorted(distinct)
            fields.pop(name, None)
            evidence.pop(name, None)
    currencies = set(re.findall(r"\b(?:USD|EUR|GBP|PKR|AED|CNY|JPY)\b", text))
    if "currency" not in fields and len(currencies) == 1:
        fields["currency"] = currencies.pop()
    quantities = set(re.findall(r"\b([0-9]+(?:\.[0-9]+)?)\s+(?:MT|Metric\s+Tons)\b", text, re.I))
    if "quantity" not in fields and len(quantities) == 1:
        fields["quantity"] = quantities.pop()
        fields["quantity_unit"] = "MT"
    if kind == "COMMERCIAL_INVOICE":
        # Totals and line items are only interpreted under invoice table headers.
        for line in lines:
            total = re.match(
                r"^\s*TOTAL\s+[\d.,]+\s+(?:MT|KG|PCS|CTN|UNITS)\s+([\d,]+\.\d{2})\s*$", line, re.I
            )
            if total:
                fields["amount"] = total[1].replace(",", "")
                evidence["amount"] = {"source": line.strip()[:300], "method": "invoice total row"}
        if re.search(r"unit price", text, re.I) and re.search(r"amount", text, re.I):
            rows = re.findall(
                r"\b[\d.,]+\s+(?:MT|KG|PCS|CTN|UNITS)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})", text, re.I
            )
            if rows:
                fields["line_totals"] = [row[1].replace(",", "") for row in rows]
                if len(rows) == 1:
                    fields["unit_price"] = rows[0][0].replace(",", "")
    for name, label in (
        ("partial_shipment", "partial shipments?"),
        ("transshipment", "trans[ -]?shipments?"),
    ):
        value = re.search(rf"(?im)^\s*{label}\s*[:\-]?\s+(yes|no|true|false)\s*$", text)
        if value:
            fields[name] = value[1].lower() in {"yes", "true"}
            evidence[name] = {"source": value[0].strip(), "method": "explicit document statement"}
    if "incoterm" in fields:
        term = re.match(r"^(FOB|CIF|CFR|EXW|FCA|CPT|CIP|DAP|DPU|DDP|FAS)\b", fields["incoterm"], re.I)
        if term:
            fields["incoterm"] = term[1].upper()
        else:
            fields.pop("incoterm")
    if kind == "DRAFT":
        buyer = re.search(r"for account of (.+?) \(Applicant\)", text, re.I)
        seller = re.search(r"Drawer \(Beneficiary\):\s*\n([^\n]+)", text, re.I)
        if buyer:
            fields["applicant"] = buyer[1].strip()
        if seller:
            fields["beneficiary"] = seller[1].strip()
    if kind == "BILL_OF_LADING" and "quantity" not in fields:
        wrapped = re.findall(r"\b([0-9]+) Metric\s+Tons\b", re.sub(r"[ \t]+", " ", text), re.I)
        if len(set(wrapped)) == 1:
            fields["quantity"] = wrapped[0]
            fields["quantity_unit"] = "MT"
    for name in conflicts:
        fields.pop(name, None)
        evidence.pop(name, None)
    if details is not None:
        details.update({"evidence": evidence, "conflicts": conflicts})
    return fields


def extraction_result(text, pages, provider):
    details = {}
    fields = extract_fields(text, details)
    missing = [name for name in ("number", "issue_date") if name not in fields]
    warnings = []
    for name, values in details["conflicts"].items():
        warnings.append(
            f"Conflicting {name.replace('_', ' ')} values: {', '.join(values)}. Select the correct value from the document."
        )
    if fields.get("amount") and fields.get("line_totals"):
        if Decimal(fields["amount"]) != sum(Decimal(v) for v in fields["line_totals"]):
            warnings.append(
                "Document total differs from the recognized line totals. Check charges, discounts, and OCR values."
            )
    if "[" in text or "___" in text:
        warnings.append(
            "This document contains unfilled template placeholders. They have not been used as field values."
        )
    if missing:
        warnings.append(
            "Not found in this document: "
            + ", ".join(missing)
            + ". Enter actual document details; related invoice references are not document numbers."
        )
    return {
        "text": text[:100000],
        "fields": fields,
        "pages": pages,
        "provider": provider,
        "document_type": detect_type(text),
        "warnings": warnings,
        "evidence": details["evidence"],
        "conflicts": details["conflicts"],
        "review_required": True,
    }


async def recognize(content: bytes, filename: str, mime: str, advanced: bool = False) -> dict:
    if not advanced and mime == "application/pdf" and content.startswith(b"%PDF-"):
        from io import BytesIO
        from pypdf import PdfReader

        try:
            reader = PdfReader(BytesIO(content))
            if len(reader.pages) > 50:
                raise AppError(413, "PDF_PAGE_LIMIT", "Use a PDF containing at most 50 pages.")
            page_text = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
            if page_text and all(len(re.sub(r"\s", "", text)) >= 50 for text in page_text):
                result = extraction_result("\n\n".join(page_text), len(page_text), "PDF text")
                # Wrapped descriptions can cross unrelated columns in layout mode.
                # The PDF's reading order recovers quantities without borrowing LC data.
                if "quantity" not in result["fields"]:
                    plain = "\n".join(page.extract_text() or "" for page in reader.pages)
                    quantities = set(
                        re.findall(r"\b([0-9]+(?:\.[0-9]+)?)\s+(?:MT|Metric\s+Tons)\b", plain, re.I)
                    )
                    if len(quantities) == 1:
                        result["fields"]["quantity"] = quantities.pop()
                        result["fields"]["quantity_unit"] = "MT"
                return result
        except AppError:
            raise
        except Exception:
            # Image-only or unsupported PDF: use the configured OCR provider.
            pass
    key = os.getenv("OCR_SPACE_API_KEY", "")
    if not key:
        raise AppError(503, "OCR_NOT_CONFIGURED", "OCR is not configured. Enter document fields manually.")
    if len(content) > 1024 * 1024:
        raise AppError(
            413,
            "OCR_FILE_SIZE",
            "OCR.space Free accepts files up to 1 MB and PDFs up to 3 pages. Use a smaller document or enter fields manually.",
        )
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            response = await client.post(
                "https://api.ocr.space/parse/image",
                headers={"apikey": key},
                files={"file": (filename, content, mime)},
                data={
                    "OCREngine": "3" if advanced else "2",
                    "isOverlayRequired": "false" if advanced else "true",
                    "language": "eng",
                    "isTable": "true",
                    "detectOrientation": "true",
                    "scale": "true",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise AppError(
            502, "OCR_UNAVAILABLE", "OCR.space could not process the request. Retry or enter fields manually."
        ) from None
    if not isinstance(payload, dict):
        raise AppError(502, "OCR_RESPONSE", "OCR.space returned an invalid response.")
    pages = payload.get("ParsedResults")
    if (
        payload.get("IsErroredOnProcessing")
        or str(payload.get("OCRExitCode")) != "1"
        or not isinstance(pages, list)
        or not pages
    ):
        raise AppError(
            422,
            "OCR_FAILED",
            "OCR did not finish all pages. Check file readability, the 3-page limit, and your API quota; or enter fields manually.",
        )
    if any(not isinstance(p, dict) or str(p.get("FileParseExitCode")) != "1" for p in pages):
        raise AppError(422, "OCR_PARTIAL", "Some pages could not be read. Retry with a clearer document.")
    text = "\n\n".join(overlay_text(p) if not advanced else p.get("ParsedText") or "" for p in pages).strip()
    if not text:
        raise AppError(
            422, "OCR_EMPTY", "No readable text was found. Try a clearer scan or enter fields manually."
        )
    result = extraction_result(text, len(pages), "OCR.space advanced" if advanced else "OCR.space")
    if (
        not advanced
        and len(result["fields"]) < 4
        and not all(k in result["fields"] for k in ("number", "issue_date"))
    ):
        try:
            alternative = await recognize(content, filename, mime, advanced=True)
            if len(alternative["fields"]) > len(result["fields"]):
                alternative["warnings"].append(
                    "Advanced OCR was used automatically because the first scan recognized few fields."
                )
                return alternative
        except AppError:
            result["warnings"].append(
                "Advanced OCR retry was unavailable; initial recognition has been retained."
            )
    return result
