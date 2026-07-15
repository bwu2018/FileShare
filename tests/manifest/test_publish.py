import os

from core import crypto
from core.hashing import compute_chunk_address
from core.store import ChunkStore
from manifest.pipeline import create_manifest
from manifest.publish import fetch_manifest, list_stored_addresses


def test_list_stored_addresses_returns_pointer_hash_then_every_chunk_in_order():
    key = crypto.generate_key()
    store = ChunkStore()
    plaintext = os.urandom(5000)  # multiple chunks

    pointer_hash = create_manifest(plaintext, key, "multi.bin", store)
    manifest = fetch_manifest(pointer_hash, key, store)

    addresses = list_stored_addresses(pointer_hash, key, store)

    expected = [pointer_hash] + [
        compute_chunk_address(manifest.content_nonce, i) for i in range(manifest.chunk_count)
    ]
    assert addresses == expected
    assert len(addresses) == len(store)  # accounts for every record ever stored, nothing missed


def test_list_stored_addresses_single_chunk():
    key = crypto.generate_key()
    store = ChunkStore()

    pointer_hash = create_manifest(os.urandom(100), key, "small.bin", store)
    addresses = list_stored_addresses(pointer_hash, key, store)

    assert len(addresses) == 2  # manifest + exactly one content chunk
    assert addresses[0] == pointer_hash


def test_list_stored_addresses_empty_plaintext():
    key = crypto.generate_key()
    store = ChunkStore()

    pointer_hash = create_manifest(b"", key, "empty.bin", store)
    addresses = list_stored_addresses(pointer_hash, key, store)

    # Empty plaintext still yields one chunk: AES-GCM's 16-byte tag means the
    # "ciphertext" is never actually empty, so there's still one content chunk to delete.
    assert len(addresses) == 2
    assert addresses[0] == pointer_hash
