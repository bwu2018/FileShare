import base64

import pytest

from backend.constants import MAX_PAYLOAD_BYTES, MAX_RECORDS_PER_REQUEST
from backend.exceptions import UploadValidationError
from backend.validation import validate_records

VALID_HASH = "GSRSYUZXNPIYZBQ7XYX3KSI7D4GDO2VPKG3XF4LIUVAT4F3XVA6A===="


def _payload_b64(n_bytes: int = 10) -> str:
    return base64.b64encode(b"x" * n_bytes).decode("ascii")


def test_valid_records_pass_through():
    data = {"records": [{"hash": VALID_HASH, "payload": _payload_b64()}]}
    result = validate_records(data)
    assert result == [(VALID_HASH, _payload_b64())]


def test_rejects_non_dict_body():
    with pytest.raises(UploadValidationError):
        validate_records(["not", "a", "dict"])


def test_rejects_missing_records_key():
    with pytest.raises(UploadValidationError):
        validate_records({})


def test_rejects_non_list_records():
    with pytest.raises(UploadValidationError):
        validate_records({"records": "nope"})


def test_rejects_empty_records_list():
    with pytest.raises(UploadValidationError):
        validate_records({"records": []})


def test_rejects_over_batch_cap():
    records = [{"hash": VALID_HASH, "payload": _payload_b64()}] * (MAX_RECORDS_PER_REQUEST + 1)
    with pytest.raises(UploadValidationError):
        validate_records({"records": records})


def test_accepts_exactly_batch_cap():
    records = [{"hash": VALID_HASH, "payload": _payload_b64()}] * MAX_RECORDS_PER_REQUEST
    result = validate_records({"records": records})
    assert len(result) == MAX_RECORDS_PER_REQUEST


def test_rejects_record_missing_hash():
    with pytest.raises(UploadValidationError):
        validate_records({"records": [{"payload": _payload_b64()}]})


def test_rejects_record_missing_payload():
    with pytest.raises(UploadValidationError):
        validate_records({"records": [{"hash": VALID_HASH}]})


def test_rejects_non_base32_hash():
    with pytest.raises(UploadValidationError):
        validate_records({"records": [{"hash": "not-base32!!", "payload": _payload_b64()}]})


def test_rejects_invalid_base64_payload():
    with pytest.raises(UploadValidationError):
        validate_records({"records": [{"hash": VALID_HASH, "payload": "!!!not-base64!!!"}]})


def test_rejects_oversized_payload():
    oversized = _payload_b64(MAX_PAYLOAD_BYTES + 1)
    with pytest.raises(UploadValidationError):
        validate_records({"records": [{"hash": VALID_HASH, "payload": oversized}]})


def test_accepts_payload_at_exact_cap():
    at_cap = _payload_b64(MAX_PAYLOAD_BYTES)
    result = validate_records({"records": [{"hash": VALID_HASH, "payload": at_cap}]})
    assert result == [(VALID_HASH, at_cap)]
