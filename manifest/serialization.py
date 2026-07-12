import struct

from core.constants import NONCE_SIZE

from .constants import (
    HASH_STRING_LEN,
    INDEX_HEADER_SIZE,
    MANIFEST_HEADER_SIZE,
    MANIFEST_VERSION,
    MAX_HASHES_PER_NODE,
)
from .exceptions import ManifestFormatError
from .models import IndexNode, Manifest


def serialize_index_node(node: IndexNode) -> bytes:
    if len(node.hashes) > MAX_HASHES_PER_NODE:
        raise ManifestFormatError(
            f"IndexNode has {len(node.hashes)} hashes, exceeds MAX_HASHES_PER_NODE={MAX_HASHES_PER_NODE}"
        )
    for h in node.hashes:
        if len(h) != HASH_STRING_LEN:
            raise ManifestFormatError(
                f"hash string has length {len(h)}, expected {HASH_STRING_LEN}"
            )

    header = struct.pack(">BI", 1 if node.is_leaf else 0, len(node.hashes))
    body = "".join(node.hashes).encode("ascii")
    return header + body


def deserialize_index_node(data: bytes) -> IndexNode:
    if len(data) < INDEX_HEADER_SIZE:
        raise ManifestFormatError(
            f"IndexNode data truncated: {len(data)} bytes < header size {INDEX_HEADER_SIZE}"
        )

    is_leaf_byte, count = struct.unpack(">BI", data[:INDEX_HEADER_SIZE])
    if is_leaf_byte not in (0, 1):
        raise ManifestFormatError(f"invalid is_leaf byte: {is_leaf_byte}")

    body = data[INDEX_HEADER_SIZE:]
    if len(body) != count * HASH_STRING_LEN:
        raise ManifestFormatError(
            f"IndexNode body length {len(body)} does not match count*HASH_STRING_LEN={count * HASH_STRING_LEN}"
        )

    try:
        hashes = [
            body[i : i + HASH_STRING_LEN].decode("ascii")
            for i in range(0, len(body), HASH_STRING_LEN)
        ]
    except UnicodeDecodeError as exc:
        raise ManifestFormatError("IndexNode hash bytes are not valid ASCII") from exc

    return IndexNode(is_leaf=bool(is_leaf_byte), hashes=hashes)


def serialize_manifest(manifest: Manifest) -> bytes:
    if len(manifest.root_hash) != HASH_STRING_LEN:
        raise ManifestFormatError(
            f"root_hash has length {len(manifest.root_hash)}, expected {HASH_STRING_LEN}"
        )
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
    header += manifest.root_hash.encode("ascii")
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
    try:
        root_hash = data[25:81].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ManifestFormatError("root_hash bytes are not valid ASCII") from exc

    (name_len,) = struct.unpack(">H", data[81:83])
    if len(data) != prefix_size + name_len:
        raise ManifestFormatError(
            f"Manifest data length {len(data)} does not match expected={prefix_size + name_len}"
        )

    try:
        file_name = data[83 : 83 + name_len].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestFormatError("file_name bytes are not valid UTF-8") from exc

    return Manifest(
        version=version,
        file_name=file_name,
        file_size=file_size,
        chunk_count=chunk_count,
        content_nonce=content_nonce,
        root_hash=root_hash,
    )
