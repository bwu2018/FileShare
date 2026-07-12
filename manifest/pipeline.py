from core.models import EncodedBlob
from core.pipeline import load_plaintext, store_plaintext
from core.store import ChunkStore

from .constants import MANIFEST_VERSION
from .models import Manifest
from .publish import fetch_manifest, publish_manifest


def create_manifest(plaintext: bytes, key: bytes, file_name: str, store: ChunkStore) -> str:
    blob = store_plaintext(plaintext, key, store)

    manifest = Manifest(
        version=MANIFEST_VERSION,
        file_name=file_name,
        file_size=len(plaintext),
        chunk_count=blob.chunk_count,
        content_nonce=blob.nonce,
    )
    return publish_manifest(manifest, key, store)


def resolve_manifest(pointer_hash: str, key: bytes, store: ChunkStore) -> bytes:
    manifest = fetch_manifest(pointer_hash, key, store)
    blob = EncodedBlob(nonce=manifest.content_nonce, chunk_count=manifest.chunk_count)
    return load_plaintext(blob, key, store)
