import asyncio

import httpx
import pytest

from backend.app.extraction_values import document_date, document_number, overlay_text
from backend.app.ocr import extract_fields, extraction_result, recognize


@pytest.mark.parametrize(
    "value, expected",
    [
        ("22/09/2026", "2026-09-22"),
        ("09/22/2026", "2026-09-22"),
        ("22-Sep-2026", "2026-09-22"),
        ("22nd September 2026", "2026-09-22"),
        ("03/04/2026", None),
        ("03.04.2026", None),
        ("31/02/2026", None),
    ],
)
def test_dates(value, expected):
    assert document_date(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("EUR 125.000,50", "125000.50"),
        ("USD 125,000.50", "125000.50"),
        ("125 000.50", "125000.50"),
        ("USD [110%]", None),
        ("-500.00", None),
    ],
)
def test_numbers(value, expected):
    assert document_number(value) == expected


def test_conflicts_and_equivalent_totals():
    result = extraction_result(
        "Invoice No: A\nInvoice No: B\nInvoice Date: 03/04/2026\nGrand Total: USD 100.00\nAmount Due: USD 200.00",
        1,
        "test",
    )
    assert "number" not in result["fields"]
    assert "amount" not in result["fields"]
    assert "issue_date" not in result["fields"]
    assert result["conflicts"]["number"] == ["A", "B"]
    assert "amount" in extract_fields("Grand Total: USD 100.00\nInvoice Total: 100")


def test_markdown_and_additional_units():
    fields = extract_fields(
        "COMMERCIAL INVOICE\n| Invoice Ref | INV-MD |\n| --- | --- |\n| Invoice Date | 22-Sep-2026 |\n| Quantity | 50 PCS |\n| Incoterms | CIF Karachi |\nPartial Shipment: No\nTransshipment: Yes"
    )
    assert fields["number"] == "INV-MD"
    assert fields["quantity_unit"] == "PCS"
    assert fields["incoterm"] == "CIF"
    assert fields["partial_shipment"] is False
    assert fields["transshipment"] is True


def test_spatial_ocr_rebuilds_separate_columns():
    def word(text, left, top):
        return {"WordText": text, "Left": left, "Top": top, "Width": len(text) * 5, "Height": 10}

    page = {
        "ParsedText": "flattened",
        "TextOverlay": {
            "Lines": [
                {
                    "Words": [
                        word("Invoice No", 10, 10),
                        word("INV-SPACE", 200, 10),
                        word("Invoice Date", 400, 10),
                        word("22 September 2026", 550, 10),
                    ]
                }
            ]
        },
    }
    result = extract_fields(overlay_text(page))
    assert result["number"] == "INV-SPACE"
    assert result["issue_date"] == "2026-09-22"


def test_automatic_advanced_retry(monkeypatch):
    monkeypatch.setenv("OCR_SPACE_API_KEY", "test-only")
    client = httpx.AsyncClient
    calls = []

    def respond(request):
        calls.append(request)
        text = (
            "Unclear document text"
            if len(calls) == 1
            else "COMMERCIAL INVOICE\nInvoice No: ADV-1\nInvoice Date: 2026-09-22\nGrand Total: USD 100.00"
        )
        return httpx.Response(
            200, json={"OCRExitCode": "1", "ParsedResults": [{"FileParseExitCode": "1", "ParsedText": text}]}
        )

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs)
    )
    result = asyncio.run(recognize(b"image", "scan.png", "image/png"))
    assert len(calls) == 2
    assert result["provider"] == "OCR.space advanced"
    assert result["fields"]["number"] == "ADV-1"
    assert result["evidence"]["number"]["source"] == "ADV-1"
