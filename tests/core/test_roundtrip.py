import math
import os

import pytest

from core import (
    ChunkNotFoundError,
    ChunkStore,
    DecryptionError,
    crypto,
    load_plaintext,
    store_plaintext,
)
from core.constants import CHUNK_SIZE
from core.hashing import compute_chunk_address


def expected_chunk_count(plaintext_len: int) -> int:
    ciphertext_len = plaintext_len + 16  # AES-GCM tag overhead
    return math.ceil(ciphertext_len / CHUNK_SIZE)


@pytest.mark.parametrize(
    "plaintext",
    [
        b"",
        b"x" * 1184,  # ciphertext exactly 1200 bytes -> 1 full chunk, no padding
        b"x" * 2384,  # ciphertext exactly 2400 bytes -> 2 full chunks, no padding
        b"hello world, this is a deterministic ASCII test case",
        os.urandom(500),  # partial last chunk
        os.urandom(10_000),  # larger multi-chunk file
    ],
)
def test_roundtrip(plaintext):
    key = crypto.generate_key()
    store = ChunkStore()

    blob = store_plaintext(plaintext, key, store)

    assert blob.chunk_count == expected_chunk_count(len(plaintext))
    assert len(store) == blob.chunk_count

    result = load_plaintext(blob, key, store)
    assert result == plaintext


def _store_multi_chunk_blob():
    key = crypto.generate_key()
    store = ChunkStore()
    plaintext = os.urandom(3000)  # ciphertext 3016 bytes -> 3 chunks at CHUNK_SIZE=1200
    blob = store_plaintext(plaintext, key, store)
    assert blob.chunk_count >= 2
    return plaintext, key, store, blob


def test_bitflip_stored_chunk_raises_decryption_error():
    _plaintext, key, store, blob = _store_multi_chunk_blob()
    target_address = compute_chunk_address(blob.nonce, 0)

    corrupted = list(store._data[target_address])
    corrupted[0] = "A" if corrupted[0] != "A" else "B"
    store._data[target_address] = "".join(corrupted)

    with pytest.raises(DecryptionError):
        load_plaintext(blob, key, store)


def test_missing_chunk_raises_not_found():
    _plaintext, key, store, blob = _store_multi_chunk_blob()
    del store._data[compute_chunk_address(blob.nonce, 0)]

    with pytest.raises(ChunkNotFoundError):
        load_plaintext(blob, key, store)


def test_wrong_key_raises_decryption_error():
    _plaintext, _key, store, blob = _store_multi_chunk_blob()
    wrong_key = crypto.generate_key()

    with pytest.raises(DecryptionError):
        load_plaintext(blob, wrong_key, store)


def test_reordered_chunks_raises_decryption_error():
    _plaintext, key, store, blob = _store_multi_chunk_blob()
    addr0 = compute_chunk_address(blob.nonce, 0)
    addr1 = compute_chunk_address(blob.nonce, 1)
    store._data[addr0], store._data[addr1] = store._data[addr1], store._data[addr0]

    with pytest.raises(DecryptionError):
        load_plaintext(blob, key, store)


def test_crypto_roundtrip():
    key = crypto.generate_key()
    plaintext = b"some plaintext data"
    nonce, ciphertext = crypto.encrypt(key, plaintext)
    assert crypto.decrypt(key, nonce, ciphertext) == plaintext


def test_crypto_tampered_ciphertext_raises_decryption_error():
    key = crypto.generate_key()
    nonce, ciphertext = crypto.encrypt(key, b"some plaintext data")
    tampered = bytearray(ciphertext)
    tampered[0] ^= 0xFF

    with pytest.raises(DecryptionError):
        crypto.decrypt(key, nonce, bytes(tampered))


def test_crypto_nonce_uniqueness():
    key = crypto.generate_key()
    nonce1, _ = crypto.encrypt(key, b"same plaintext")
    nonce2, _ = crypto.encrypt(key, b"same plaintext")
    assert nonce1 != nonce2
