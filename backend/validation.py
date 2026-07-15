import base64
import re

from .constants import MAX_PAYLOAD_BYTES, MAX_RECORDS_PER_REQUEST
from .exceptions import UploadValidationError

# Matches core.hashing's base32 output alphabet (RFC 4648) plus '=' padding --
# every "hash" field is either a chunk address or a manifest pointer_hash, both
# produced the same way (base64.b32encode(sha256(...).digest())).
_HASH_PATTERN = re.compile(r"^[A-Z2-7]+=*$")


def validate_records(data: object) -> list[tuple[str, str]]:
    if not isinstance(data, dict):
        raise UploadValidationError("request body must be a JSON object")

    records = data.get("records")
    if not isinstance(records, list):
        raise UploadValidationError("'records' must be a list")
    if not records:
        raise UploadValidationError("'records' must not be empty")
    if len(records) > MAX_RECORDS_PER_REQUEST:
        raise UploadValidationError(
            f"'records' has {len(records)} entries, exceeds the per-request "
            f"maximum of {MAX_RECORDS_PER_REQUEST}"
        )

    validated: list[tuple[str, str]] = []
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            raise UploadValidationError(f"record[{i}] must be an object")

        chunk_hash = record.get("hash")
        payload = record.get("payload")
        if not isinstance(chunk_hash, str) or not chunk_hash:
            raise UploadValidationError(f"record[{i}] missing/invalid 'hash'")
        if not isinstance(payload, str) or not payload:
            raise UploadValidationError(f"record[{i}] missing/invalid 'payload'")
        if not _HASH_PATTERN.match(chunk_hash):
            raise UploadValidationError(f"record[{i}] 'hash' is not valid base32")

        try:
            decoded = base64.b64decode(payload, validate=True)
        except Exception as exc:
            raise UploadValidationError(f"record[{i}] 'payload' is not valid base64") from exc

        if len(decoded) > MAX_PAYLOAD_BYTES:
            raise UploadValidationError(
                f"record[{i}] payload is {len(decoded)} bytes, exceeds the "
                f"{MAX_PAYLOAD_BYTES}-byte maximum"
            )

        validated.append((chunk_hash, payload))

    return validated
