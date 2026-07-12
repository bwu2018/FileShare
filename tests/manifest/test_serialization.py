import os

import pytest

from core.constants import NONCE_SIZE
from manifest.exceptions import ManifestFormatError
from manifest.models import Manifest
from manifest.serialization import deserialize_manifest, serialize_manifest


def _manifest(file_size=1000, chunk_count=5, file_name="test.txt") -> Manifest:
    return Manifest(
        version=1,
        file_name=file_name,
        file_size=file_size,
        chunk_count=chunk_count,
        content_nonce=os.urandom(NONCE_SIZE),
    )


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
