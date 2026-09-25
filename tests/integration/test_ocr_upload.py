from scripts.seed import demo_terms


def test_extraction_access_and_reviewed_upload(system, login, monkeypatch):
    client, _, _ = system
    headers = login("analyst")
    lc = client.post(
        "/api/v1/lcs", headers=headers, json={"title": "OCR test invoice", "terms": demo_terms()}
    ).json()
    path = f"/api/v1/lcs/{lc['id']}/documents"
    calls = []

    async def recognize(content, filename, mime, advanced=False):
        calls.append((filename, advanced))
        return {
            "text": "Invoice No: OCR-1",
            "fields": {"number": "OCR-1", "issue_date": "2026-09-24"},
            "pages": 1,
            "provider": "OCR.space",
            "review_required": True,
        }

    monkeypatch.setattr("backend.app.cases.recognize", recognize)
    files = {"file": ("invoice.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")}
    assert client.post(path + "/extract", files=files).status_code == 401
    assert client.post(path + "/extract", headers=login("auditor"), files=files).status_code == 403
    assert calls == []
    response = client.post(path + "/extract", headers=headers, files=files)
    assert response.status_code == 200
    assert response.json()["fields"]["number"] == "OCR-1"
    advanced_response = client.post(
        path + "/extract", headers=headers, files=files, data={"advanced": "true"}
    )
    assert advanced_response.status_code == 200
    assert calls[-1] == ("invoice.pdf", True)
    assert client.get(f"/api/v1/lcs/{lc['id']}", headers=headers).json()["documents"] == []
    result = client.post(
        path,
        headers=headers,
        files=files,
        data={
            "type": "COMMERCIAL_INVOICE",
            "version": lc["version"],
            "fields": '{"number":"OCR-1-reviewed","issue_date":"2026-09-24"}',
        },
    )
    assert result.status_code == 201, result.text
    assert result.json()["number"] == "OCR-1-reviewed"
