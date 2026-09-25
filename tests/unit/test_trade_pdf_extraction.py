import asyncio
from io import BytesIO

from reportlab.pdfgen import canvas

from backend.app.ocr import detect_type, extract_fields, recognize


def test_invoice_columns_and_totals():
    text = """COMMERCIAL INVOICE
           SELLER / BENEFICIARY                       BUYER / APPLICANT
 Example Exporter [Full Address]             Example Importer [Full Address]
 Invoice No.       INV-88                    Invoice Date     22 September 2026
 Currency          USD
 No. Description       Quantity     Unit Price (USD)     Amount (USD)
 1   Cotton fabric     100 MT        1,250.00             125,000.00
                       TOTAL        100 MT              125,000.00
"""
    fields = extract_fields(text)
    assert fields["number"] == "INV-88"
    assert fields["issue_date"] == "2026-09-22"
    assert fields["applicant"] == "Example Importer"
    assert fields["beneficiary"] == "Example Exporter"
    assert fields["amount"] == "125000.00"
    assert fields["quantity"] == "100"
    assert fields["unit_price"] == "1250.00"
    assert fields["line_totals"] == ["125000.00"]


def test_placeholders_and_references_are_not_document_identity():
    assert (
        extract_fields("PACKING LIST\nPacking List No.    PL-10\nInvoice No.    INV-55")["number"] == "PL-10"
    )
    assert "number" not in extract_fields("BENEFICIARY'S CERTIFICATE\nInvoice Reference   INV-55")
    fields = extract_fields(
        "INSURANCE CERTIFICATE\nCertificate / Policy No.   [Policy No.]\nDate of Issue   [Issue Date]\nInvoice Value    USD 125,000.00\nInsured Value    USD [110% of invoice value]"
    )
    assert "amount" not in fields
    assert "number" not in fields
    assert "issue_date" not in fields
    assert detect_type("INSURANCE CERTIFICATE") == "INSURANCE_CERTIFICATE"


def test_stacked_headers_do_not_become_values():
    fields = extract_fields("""BILL OF LADING
 B/L Number          Booking / Reference No.        Date of Issue
 [B/L Number]        [Booking Ref]                  22 September 2026
 NOTIFY PARTY                         VESSEL / VOYAGE
 [Notify Party]                        Vessel: [Vessel Name]
""")
    assert fields == {"issue_date": "2026-09-22"}


def test_native_pdf_does_not_need_cloud_key(monkeypatch):
    monkeypatch.delenv("OCR_SPACE_API_KEY", raising=False)
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    for index, line in enumerate(
        [
            "COMMERCIAL INVOICE",
            "Invoice No: INV-LOCAL",
            "Invoice Date: 2026-09-22",
            "Grand Total: USD 125,000.00",
        ]
    ):
        pdf.drawString(60, 750 - index * 25, line)
    pdf.save()
    result = asyncio.run(recognize(stream.getvalue(), "invoice.pdf", "application/pdf"))
    assert result["provider"] == "PDF text"
    assert result["fields"]["number"] == "INV-LOCAL"
    assert result["fields"]["amount"] == "125000.00"


def test_combined_consignee_and_typographic_text():
    fields = extract_fields("PACKING LIST\nCONSIGNEE / APPLICANT\nExample Importer")
    assert fields["consignee"] == fields["applicant"] == "Example Importer"
    assert detect_type("BENEFICIARY\u2019S CERTIFICATE") == "BENEFICIARY_CERTIFICATE"
    assert extract_fields("Grand Total: \u20ac1250.00")["amount"] == "1250.00"
