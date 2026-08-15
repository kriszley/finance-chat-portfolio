"""Security-focused tests for the upload endpoint."""

import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from routers import upload as upload_router


DEMO_CSV = b"Filter,Date,Description,Sub-description,Status,Type of Transaction,Amount\n"


def _upload(filename: str, content: bytes = DEMO_CSV):
    file = UploadFile(file=BytesIO(content), filename=filename)
    return asyncio.run(upload_router.upload_file(file))


def test_upload_returns_opaque_token_and_uses_safe_name(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_router, "UPLOAD_DIR", tmp_path)

    result = _upload("../scotiabank-demo.csv")

    assert result.filename == "scotiabank-demo.csv"
    assert "/" not in result.file_path
    assert ".." not in result.file_path
    assert (tmp_path / result.file_path).is_file()


def test_upload_rejects_oversized_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_router, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(upload_router, "MAX_UPLOAD_BYTES", 4)

    with pytest.raises(HTTPException) as exc:
        _upload("scotiabank-demo.csv", b"12345")

    assert exc.value.status_code == 413
