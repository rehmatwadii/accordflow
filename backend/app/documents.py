"""Document inspection and JSON extraction; cloud OCR lives in ocr.py."""

import hashlib
import json
from pathlib import PurePath
from typing import Protocol

from .errors import AppError
from .schemas import DocumentFields

MAX_FILE_SIZE = 5 * 1024 * 1024


class DocumentExtractionProvider(Protocol):
    def extract(self, content: bytes, mime: str) -> dict: ...


class MockExtractionProvider:
    """Structured synthetic JSON extraction. PDFs/images require reviewed manual fields."""

    def extract(self, content, mime):
        if mime == "application/json":
            try:
                return DocumentFields.model_validate(json.loads(content)).model_dump(mode="json")
            except (ValueError, TypeError):
                raise AppError(
                    422,
                    "INVALID_DOCUMENT_FIELDS",
                    "Synthetic JSON must match the documented document-field schema",
                ) from None
        return {}


class DemoMalwareScanner:
    """Reject known executable/polyglot markers; NOT an antivirus engine."""

    def scan(self, content):
        if content.startswith((b"MZ", b"\x7fELF", b"#!")) or any(
            v in content
            for v in (
                b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE",
                b"/JavaScript",
                b"/JS",
                b"/Launch",
                b"/EmbeddedFile",
            )
        ):
            raise AppError(422, "UNSAFE_DOCUMENT", "Active content or prohibited file signature detected")


def inspect_file(filename, content):
    if not content or len(content) > MAX_FILE_SIZE:
        raise AppError(413, "FILE_SIZE", "Documents must contain between 1 byte and 5 MB")
    if (
        not filename
        or "/" in filename
        or "\\" in filename
        or len(filename) > 200
        or any(ord(c) < 32 for c in filename)
    ):
        raise AppError(422, "UNSAFE_FILENAME", "Use a simple filename without path components")
    suffix = PurePath(filename).suffix.lower()
    mime = None
    if suffix == ".pdf" and content.startswith(b"%PDF-") and b"%%EOF" in content[-1024:]:
        mime = "application/pdf"
    elif suffix == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif (
        suffix in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9")
    ):
        mime = "image/jpeg"
    elif suffix == ".json":
        try:
            if isinstance(json.loads(content), dict):
                mime = "application/json"
        except (ValueError, UnicodeDecodeError):
            pass
    if not mime:
        raise AppError(422, "FILE_TYPE", "Upload a signature-valid PDF, PNG, JPEG or synthetic JSON document")
    DemoMalwareScanner().scan(content)
    return mime, hashlib.sha256(content).hexdigest()
