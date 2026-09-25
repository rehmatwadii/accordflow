# OCR integration verification — 2026-09-24

- OCR.space live request using the configured local key succeeded on a synthetic invoice PDF. Extracted invoice number, ISO issue date, amount, currency, and buyer matched the fixture.
- Full Python suite: 73 passed. Covers provider errors, partial/empty results, size/configuration limits, ambiguous dates, permissions, preview without persistence, and saving reviewed fields.
- Existing browser journeys: 4 passed. Dedicated OCR browser journey: 1 passed with a stubbed provider response, including automatic population, correction, review confirmation, and persistence.
- TypeScript/Vite build, Ruff checks, and heuristic secret scan passed.
- Local backend restarted with OCR configuration; frontend rebuilt.

Recognition is real OCR.space text recognition. Structured trade field mapping uses common English labels, not an AI model. Complex line-item tables, unlabeled values, and ambiguous dates are not inferred. Unrecognized fields remain blank for review. Partial provider results are rejected. Files selected in the OCR flow are transmitted to OCR.space; JSON extraction stays local. No raw OCR text is written to logs or audit events; reviewed fields and the original document are saved through the existing upload workflow.

## Layout extraction update

Text PDFs are now read locally with preserved column spacing before the OCR.space fallback. The parser recognizes document types, distinguishes each document number from invoice references, skips template placeholders, matches party headers to their values, and reads simple invoice totals. The upload screen selects detected document types and explains missing required values.

All eight supplied PDFs passed the optional browser upload test (LOCAL_PDF_MANIFEST (an ignored local JSON manifest)). The invoice populated its number, date, parties, quantity, unit price, total and line total. Missing insurance number/date/insured value remained blank, with no substitution of invoice value for coverage. Source PDFs were not committed or saved as app documents.

Validation: 77 Python tests, 5 existing browser journeys, and 1 additional journey covering all 8 PDFs passed. Frontend build, Ruff and heuristic secret scan passed. This remains deterministic field extraction, not general AI document understanding.

## Advanced extraction update

- OCR.space Engine 2 now requests word coordinates and reconstructs rows/columns instead of relying solely on flattened OCR text.
- A low-yield scan (fewer than four recognized fields and missing number or issue date) receives one bounded Engine 3 retry. The alternative is used only when it recognizes more fields. Provider failure retains the initial result.
- The upload form offers Try advanced OCR, which explicitly sends even text PDFs to OCR.space Engine 3 and replaces extracted values on success. Existing values remain available if this request fails.
- Expanded parsing: Markdown tables, invoice references, additional units, explicit shipment flags, European/US amount formatting, and additional unambiguous dates. Ambiguous day/month dates remain unfilled.
- Conflicting document identifiers, dates and totals are withheld and reported. Invoice totals are checked against recognized line totals. Source snippets are shown for values matched to document labels. No probabilistic confidence score is invented.
- No model API or new external provider was added. This is rule-based structured extraction plus OCR.space recognition, not guaranteed general document understanding.

Validation: 94 backend tests passed, 6 browser journeys passed including all 8 supplied PDFs. Advanced Engine 3 also passed a live synthetic invoice test (reference, date, total, buyer and currency). The modified API permission/advanced-option integration test passed separately. Frontend build and Ruff passed.

Provider documentation: https://ocr.space/ocrapi
