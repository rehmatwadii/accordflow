import asyncio

import httpx
import pytest

from backend.app.errors import AppError
from backend.app.ocr import extract_fields, recognize


def test_trade_fields_and_ambiguous_dates():
    fields = extract_fields(
        "Invoice No: INV-77\nInvoice Date: 2026-09-24\nGrand Total: USD 12,500.50\nBuyer: Example Imports\nPort of Loading: Karachi"
    )
    assert fields == {
        "number": "INV-77",
        "issue_date": "2026-09-24",
        "amount": "12500.50",
        "currency": "USD",
        "applicant": "Example Imports",
        "loading_port": "Karachi",
    }
    assert "issue_date" not in extract_fields("Date: 03/04/2026")
    assert extract_fields("Unreadable page") == {}


def mock_provider(monkeypatch, payload):
    monkeypatch.setenv("OCR_SPACE_API_KEY", "test-key")
    original = httpx.AsyncClient

    def respond(request):
        assert request.headers["apikey"] == "test-key"
        assert request.url == "https://api.ocr.space/parse/image"
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)
    )


def test_success(monkeypatch):
    mock_provider(
        monkeypatch,
        {
            "OCRExitCode": 1,
            "ParsedResults": [{"FileParseExitCode": 1, "ParsedText": "Invoice No: ABC\nDate: 2026-09-24"}],
        },
    )
    result = asyncio.run(recognize(b"test", "invoice.pdf", "application/pdf"))
    assert result["fields"]["number"] == "ABC"
    assert result["review_required"] is True


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"OCRExitCode": 2},
        {"IsErroredOnProcessing": True},
        {"OCRExitCode": 1, "ParsedResults": [{"FileParseExitCode": 1, "ParsedText": ""}]},
    ],
)
def test_provider_failure(monkeypatch, payload):
    mock_provider(monkeypatch, payload)
    with pytest.raises(AppError):
        asyncio.run(recognize(b"test", "invoice.pdf", "application/pdf"))


def test_limits_and_missing_key(monkeypatch):
    monkeypatch.delenv("OCR_SPACE_API_KEY", raising=False)
    with pytest.raises(AppError):
        asyncio.run(recognize(b"x", "invoice.pdf", "application/pdf"))
    monkeypatch.setenv("OCR_SPACE_API_KEY", "test")
    with pytest.raises(AppError):
        asyncio.run(recognize(b"x" * (1024 * 1024 + 1), "invoice.pdf", "application/pdf"))
