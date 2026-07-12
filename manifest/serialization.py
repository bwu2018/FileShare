import struct

from core.constants import NONCE_SIZE

from .constants import MANIFEST_HEADER_SIZE, MANIFEST_VERSION
from .exceptions import ManifestFormatError
from .models import Manifest


def serialize_manifest(manifest: Manifest) -> bytes:
    if len(manifest.content_nonce) != NONCE_SIZE:
        raise ManifestFormatError(
            f"content_nonce has length {len(manifest.content_nonce)}, expected {NONCE_SIZE}"
        )

    name_bytes = manifest.file_name.encode("utf-8")
    if len(name_bytes) > 0xFFFF:
        raise ManifestFormatError(
            f"file_name encodes to {len(name_bytes)} bytes, exceeds uint16 max"
        )

    header = struct.pack(
        ">BQI",
        manifest.version,
        manifest.file_size,
        manifest.chunk_count,
    )
    header += manifest.content_nonce
    header += struct.pack(">H", len(name_bytes))
    return header + name_bytes


def deserialize_manifest(data: bytes) -> Manifest:
    prefix_size = MANIFEST_HEADER_SIZE + 2  # +2 for the name_len field itself
    if len(data) < prefix_size:
        raise ManifestFormatError(
            f"Manifest data truncated: {len(data)} bytes < minimum {prefix_size}"
        )

    version, file_size, chunk_count = struct.unpack(">BQI", data[0:13])
    if version != MANIFEST_VERSION:
        raise ManifestFormatError(f"unsupported manifest version: {version}")

    content_nonce = data[13:25]

    (name_len,) = struct.unpack(">H", data[25:27])
    if len(data) != prefix_size + name_len:
        raise ManifestFormatError(
            f"Manifest data length {len(data)} does not match expected={prefix_size + name_len}"
        )

    try:
        file_name = data[27 : 27 + name_len].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestFormatError("file_name bytes are not valid UTF-8") from exc

    return Manifest(
        version=version,
        file_name=file_name,
        file_size=file_size,
        chunk_count=chunk_count,
        content_nonce=content_nonce,
    )
