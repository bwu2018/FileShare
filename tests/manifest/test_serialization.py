import os
import struct

import pytest

from core.constants import NONCE_SIZE
from core.hashing import compute_chunk_hash
from manifest.constants import HASH_STRING_LEN, INDEX_HEADER_SIZE, MAX_HASHES_PER_NODE
from manifest.exceptions import ManifestFormatError
from manifest.models import IndexNode, Manifest
from manifest.serialization import (
    deserialize_index_node,
    deserialize_manifest,
    serialize_index_node,
    serialize_manifest,
)


def _hash(i: int) -> str:
    return compute_chunk_hash(str(i).encode())


def _manifest(file_size=1000, chunk_count=5, file_name="test.txt") -> Manifest:
    return Manifest(
        version=1,
        file_name=file_name,
        file_size=file_size,
        chunk_count=chunk_count,
        content_nonce=os.urandom(NONCE_SIZE),
        root_hash=_hash(999),
    )


def test_index_node_roundtrip_leaf():
    node = IndexNode(is_leaf=True, hashes=[_hash(0), _hash(1), _hash(2)])
    assert deserialize_index_node(serialize_index_node(node)) == node


def test_index_node_roundtrip_internal():
    node = IndexNode(is_leaf=False, hashes=[_hash(0), _hash(1)])
    assert deserialize_index_node(serialize_index_node(node)) == node


def test_index_node_roundtrip_empty_hashes():
    node = IndexNode(is_leaf=True, hashes=[])
    assert deserialize_index_node(serialize_index_node(node)) == node


def test_index_node_exact_serialized_size():
    hashes = [_hash(i) for i in range(10)]
    node = IndexNode(is_leaf=True, hashes=hashes)
    data = serialize_index_node(node)
    assert len(data) == INDEX_HEADER_SIZE + 10 * HASH_STRING_LEN


def test_index_node_serialize_rejects_wrong_length_hash():
    node = IndexNode(is_leaf=True, hashes=["too_short"])
    with pytest.raises(ManifestFormatError):
        serialize_index_node(node)


def test_index_node_serialize_rejects_oversized_node():
    node = IndexNode(is_leaf=True, hashes=[_hash(i) for i in range(MAX_HASHES_PER_NODE + 1)])
    with pytest.raises(ManifestFormatError):
        serialize_index_node(node)


def test_index_node_deserialize_truncated_header_raises():
    with pytest.raises(ManifestFormatError):
        deserialize_index_node(b"\x01\x00\x00")


def test_index_node_deserialize_count_mismatch_raises():
    node = IndexNode(is_leaf=True, hashes=[_hash(0)])
    data = serialize_index_node(node)
    with pytest.raises(ManifestFormatError):
        deserialize_index_node(data[:-1])


def test_index_node_deserialize_invalid_flag_raises():
    bad = struct.pack(">BI", 2, 0)
    with pytest.raises(ManifestFormatError):
        deserialize_index_node(bad)


def test_manifest_roundtrip():
    manifest = _manifest()
    assert deserialize_manifest(serialize_manifest(manifest)) == manifest


def test_manifest_header_is_constant_size_regardless_of_file_size():
    small = serialize_manifest(_manifest(file_size=1, chunk_count=1, file_name="a"))
    large = serialize_manifest(_manifest(file_size=10_000_000, chunk_count=500_000, file_name="a"))
    assert len(small) == len(large)


def test_manifest_roundtrip_empty_and_unicode_file_name():
    empty = deserialize_manifest(serialize_manifest(_manifest(file_name="")))
    assert empty.file_name == ""

    unicode_manifest = _manifest(file_name="résumé 文件.pdf")
    result = deserialize_manifest(serialize_manifest(unicode_manifest))
    assert result.file_name == "résumé 文件.pdf"


def test_manifest_deserialize_rejects_unsupported_version():
    data = bytearray(serialize_manifest(_manifest()))
    data[0] = 99
    with pytest.raises(ManifestFormatError):
        deserialize_manifest(bytes(data))


def test_manifest_deserialize_truncated_name_raises():
    data = serialize_manifest(_manifest(file_name="hello"))
    with pytest.raises(ManifestFormatError):
        deserialize_manifest(data[:-2])
