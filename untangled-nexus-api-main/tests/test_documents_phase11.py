import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.routers.documents import validate_file


def test_document_size_and_content_validation():
    with pytest.raises(HTTPException) as empty:
        validate_file("empty.pdf", b"")
    assert empty.value.status_code == 413

    oversized = b"%PDF-" + b"x" * get_settings().max_document_bytes
    with pytest.raises(HTTPException) as large:
        validate_file("large.pdf", oversized)
    assert large.value.status_code == 413

    with pytest.raises(HTTPException) as disguised:
        validate_file("disguised.pdf", b"not a PDF")
    assert disguised.value.status_code == 415
