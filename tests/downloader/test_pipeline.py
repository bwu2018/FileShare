import os

import pytest

from core import crypto
from core.exceptions import ChunkHashMismatchError, ChunkNotFoundError, DecryptionError
from core.hashing import compute_chunk_address
from core.store import ChunkStore
from downloader.pipeline import download_from_store
from manifest.pipeline import create_manifest
from manifest.publish import fetch_manifest


class _CountingStore:
    """Wraps a ChunkStore and records how many times get() is called per hash."""

    def __init__(self, store: ChunkStore) -> None:
        self._store = store
        self.get_counts: dict[str, int] = {}

    def get(self, chunk_hash: str) -> str:
        self.get_counts[chunk_hash] = self.get_counts.get(chunk_hash, 0) + 1
        return self._store.get(chunk_hash)


def _publish(plaintext: bytes, file_name: str = "test.bin") -> tuple[bytes, ChunkStore, str]:
    key = crypto.generate_key()
    store = ChunkStore()
    pointer_hash = create_manifest(plaintext, key, file_name, store)
    return key, store, pointer_hash


@pytest.mark.parametrize(
    "plaintext",
    [
        b"",
        os.urandom(500),
        os.urandom(200_000),
    ],
)
def test_roundtrip(plaintext):
    key, store, pointer_hash = _publish(plaintext)

    file_name, downloaded = download_from_store(pointer_hash, key, store)

    assert file_name == "test.bin"
    assert downloaded == plaintext


def test_roundtrip_unicode_file_name():
    key, store, pointer_hash = _publish(b"hello", file_name="résumé 文件.pdf")

    file_name, downloaded = download_from_store(pointer_hash, key, store)

    assert file_name == "résumé 文件.pdf"
    assert downloaded == b"hello"


def test_wrong_key_raises_decryption_error():
    _key, store, pointer_hash = _publish(os.urandom(5000))
    wrong_key = crypto.generate_key()

    with pytest.raises(DecryptionError):
        download_from_store(pointer_hash, wrong_key, store)


def test_missing_pointer_hash_raises_chunk_not_found():
    key, store, pointer_hash = _publish(os.urandom(5000))
    del store._data[pointer_hash]

    with pytest.raises(ChunkNotFoundError):
        download_from_store(pointer_hash, key, store)


def test_bitflip_manifest_payload_raises_hash_mismatch():
    key, store, pointer_hash = _publish(os.urandom(5000))

    corrupted = list(store._data[pointer_hash])
    corrupted[0] = "A" if corrupted[0] != "A" else "B"
    store._data[pointer_hash] = "".join(corrupted)

    with pytest.raises(ChunkHashMismatchError):
        download_from_store(pointer_hash, key, store)


def test_bitflip_content_chunk_raises_decryption_error():
    key, store, pointer_hash = _publish(os.urandom(5000))

    # Look up the manifest's content_nonce independently, without going through
    # download_from_store, so this test doesn't depend on the function under test.
    manifest = fetch_manifest(pointer_hash, key, store)
    target_address = compute_chunk_address(manifest.content_nonce, 0)

    corrupted = list(store._data[target_address])
    corrupted[0] = "A" if corrupted[0] != "A" else "B"
    store._data[target_address] = "".join(corrupted)

    with pytest.raises(DecryptionError):
        download_from_store(pointer_hash, key, store)


def test_manifest_fetched_exactly_once():
    key, store, pointer_hash = _publish(os.urandom(5000))
    counting_store = _CountingStore(store)

    download_from_store(pointer_hash, key, counting_store)

    assert counting_store.get_counts[pointer_hash] == 1


def test_works_against_plain_core_chunk_store():
    key, store, pointer_hash = _publish(b"plain store check")

    assert isinstance(store, ChunkStore)
    _file_name, downloaded = download_from_store(pointer_hash, key, store)
    assert downloaded == b"plain store check"
