import math
import os

import pytest

from core import crypto
from core.constants import CHUNK_SIZE, NONCE_SIZE
from core.encoding import decode_chunk, encode_chunk
from core.exceptions import ChunkHashMismatchError, ChunkNotFoundError, DecryptionError
from core.hashing import compute_chunk_address, compute_chunk_hash
from core.pipeline import store_plaintext
from core.store import ChunkStore
from manifest.constants import MANIFEST_VERSION
from manifest.models import Manifest
from manifest.pipeline import create_manifest, resolve_manifest
from manifest.publish import fetch_manifest, publish_manifest


def expected_chunk_count(plaintext_len: int) -> int:
    ciphertext_len = plaintext_len + 16  # AES-GCM tag overhead
    return math.ceil(ciphertext_len / CHUNK_SIZE)


@pytest.mark.parametrize(
    "plaintext",
    [
        b"",
        b"x" * 1184,  # ciphertext exactly 1200 bytes -> 1 full chunk, no padding
        os.urandom(500),  # partial single chunk
        os.urandom(200_000),  # ~167 chunks, general multi-chunk coverage
    ],
)
def test_roundtrip(plaintext):
    key = crypto.generate_key()
    store = ChunkStore()

    pointer_hash = create_manifest(plaintext, key, "test.bin", store)
    manifest = fetch_manifest(pointer_hash, key, store)

    assert manifest.file_size == len(plaintext)
    assert manifest.chunk_count == expected_chunk_count(len(plaintext))
    assert manifest.file_name == "test.bin"

    result = resolve_manifest(pointer_hash, key, store)
    assert result == plaintext


def test_roundtrip_10mb_realistic_scale():
    plaintext = os.urandom(10_000_000)
    key = crypto.generate_key()
    store = ChunkStore()

    pointer_hash = create_manifest(plaintext, key, "big.bin", store)
    manifest = fetch_manifest(pointer_hash, key, store)

    assert len(store) == manifest.chunk_count + 1  # + the manifest pointer itself

    result = resolve_manifest(pointer_hash, key, store)
    assert result == plaintext


def _create_multi_chunk_manifest():
    key = crypto.generate_key()
    store = ChunkStore()
    plaintext = os.urandom(5000)
    pointer_hash = create_manifest(plaintext, key, "multi.bin", store)
    return plaintext, key, store, pointer_hash


def test_bitflip_manifest_payload_raises_hash_mismatch():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()

    corrupted = list(store._data[pointer_hash])
    corrupted[0] = "A" if corrupted[0] != "A" else "B"
    store._data[pointer_hash] = "".join(corrupted)

    with pytest.raises(ChunkHashMismatchError):
        fetch_manifest(pointer_hash, key, store)


def test_bitflip_content_chunk_raises_decryption_error():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()
    manifest = fetch_manifest(pointer_hash, key, store)
    target_address = compute_chunk_address(manifest.content_nonce, 0)

    corrupted = list(store._data[target_address])
    corrupted[0] = "A" if corrupted[0] != "A" else "B"
    store._data[target_address] = "".join(corrupted)

    with pytest.raises(DecryptionError):
        resolve_manifest(pointer_hash, key, store)


def test_missing_manifest_pointer_raises_chunk_not_found():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()
    del store._data[pointer_hash]

    with pytest.raises(ChunkNotFoundError):
        resolve_manifest(pointer_hash, key, store)


def test_missing_content_chunk_raises_chunk_not_found():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()
    manifest = fetch_manifest(pointer_hash, key, store)
    del store._data[compute_chunk_address(manifest.content_nonce, 0)]

    with pytest.raises(ChunkNotFoundError):
        resolve_manifest(pointer_hash, key, store)


def test_wrong_key_raises_decryption_error():
    _plaintext, _key, store, pointer_hash = _create_multi_chunk_manifest()
    wrong_key = crypto.generate_key()

    with pytest.raises(DecryptionError):
        resolve_manifest(pointer_hash, wrong_key, store)


def test_consistent_manifest_tamper_raises_decryption_error():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()

    wrapped = bytearray(decode_chunk(store.get(pointer_hash)))
    wrapped[NONCE_SIZE] ^= 0xFF  # flip first byte of the ciphertext, after the nonce prefix
    mutated = bytes(wrapped)
    new_pointer_hash = compute_chunk_hash(mutated)
    store.put(new_pointer_hash, encode_chunk(mutated))

    with pytest.raises(DecryptionError):
        resolve_manifest(new_pointer_hash, key, store)


def test_chunk_count_mismatch_raises_chunk_not_found():
    key = crypto.generate_key()
    store = ChunkStore()
    plaintext = os.urandom(3000)

    blob = store_plaintext(plaintext, key, store)

    bad_manifest = Manifest(
        version=MANIFEST_VERSION,
        file_name="bad.bin",
        file_size=len(plaintext),
        chunk_count=blob.chunk_count + 1,  # deliberately wrong: one phantom chunk
        content_nonce=blob.nonce,
    )
    pointer_hash = publish_manifest(bad_manifest, key, store)

    with pytest.raises(ChunkNotFoundError):
        resolve_manifest(pointer_hash, key, store)


def test_two_calls_use_independent_nonces():
    key = crypto.generate_key()
    plaintext = b"same content"
    store1 = ChunkStore()
    store2 = ChunkStore()

    pointer1 = create_manifest(plaintext, key, "same.txt", store1)
    pointer2 = create_manifest(plaintext, key, "same.txt", store2)

    assert pointer1 != pointer2

    manifest1 = fetch_manifest(pointer1, key, store1)
    manifest2 = fetch_manifest(pointer2, key, store2)
    assert manifest1.content_nonce != manifest2.content_nonce
