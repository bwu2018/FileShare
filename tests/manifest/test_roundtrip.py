import math
import os

import pytest

from core import crypto
from core.constants import CHUNK_SIZE, NONCE_SIZE
from core.encoding import decode_chunk, encode_chunk
from core.exceptions import ChunkHashMismatchError, ChunkNotFoundError, DecryptionError
from core.hashing import compute_chunk_hash
from core.pipeline import store_plaintext
from core.store import ChunkStore
from manifest import index_tree
from manifest.constants import MANIFEST_VERSION
from manifest.exceptions import ManifestFormatError
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
        os.urandom(175184),  # 146-chunk boundary -> single-level index tree
        os.urandom(175185),  # 147-chunk boundary -> forces real 2-level recursion
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
    root_node = index_tree._fetch_index_node(manifest.root_hash, store)

    assert root_node.is_leaf is False

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


def test_bitflip_index_node_raises_hash_mismatch():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()
    manifest = fetch_manifest(pointer_hash, key, store)
    root_hash = manifest.root_hash

    corrupted = list(store._data[root_hash])
    corrupted[0] = "A" if corrupted[0] != "A" else "B"
    store._data[root_hash] = "".join(corrupted)

    with pytest.raises(ChunkHashMismatchError):
        resolve_manifest(pointer_hash, key, store)


def test_bitflip_content_chunk_raises_hash_mismatch():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()
    manifest = fetch_manifest(pointer_hash, key, store)
    root_node = index_tree._fetch_index_node(manifest.root_hash, store)
    target_hash = root_node.hashes[0]

    corrupted = list(store._data[target_hash])
    corrupted[0] = "A" if corrupted[0] != "A" else "B"
    store._data[target_hash] = "".join(corrupted)

    with pytest.raises(ChunkHashMismatchError):
        resolve_manifest(pointer_hash, key, store)


def test_missing_manifest_pointer_raises_chunk_not_found():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()
    del store._data[pointer_hash]

    with pytest.raises(ChunkNotFoundError):
        resolve_manifest(pointer_hash, key, store)


def test_missing_root_index_node_raises_chunk_not_found():
    _plaintext, key, store, pointer_hash = _create_multi_chunk_manifest()
    manifest = fetch_manifest(pointer_hash, key, store)
    del store._data[manifest.root_hash]

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


def test_chunk_count_mismatch_raises_manifest_format_error():
    key = crypto.generate_key()
    store = ChunkStore()
    plaintext = os.urandom(3000)

    blob = store_plaintext(plaintext, key, store)
    root_hash = index_tree.build_index_tree(blob.chunk_hashes, store)

    bad_manifest = Manifest(
        version=MANIFEST_VERSION,
        file_name="bad.bin",
        file_size=len(plaintext),
        chunk_count=len(blob.chunk_hashes) + 1,  # deliberately wrong
        content_nonce=blob.nonce,
        root_hash=root_hash,
    )
    pointer_hash = publish_manifest(bad_manifest, key, store)

    with pytest.raises(ManifestFormatError):
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
