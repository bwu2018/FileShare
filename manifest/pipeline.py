from core.models import EncodedBlob
from core.pipeline import load_plaintext, store_plaintext
from core.store import ChunkStore

from .constants import MANIFEST_VERSION
from .exceptions import ManifestFormatError
from .index_tree import build_index_tree, walk_index_tree
from .models import Manifest
from .publish import fetch_manifest, publish_manifest


def create_manifest(plaintext: bytes, key: bytes, file_name: str, store: ChunkStore) -> str:
    blob = store_plaintext(plaintext, key, store)
    root_hash = build_index_tree(blob.chunk_hashes, store)

    manifest = Manifest(
        version=MANIFEST_VERSION,
        file_name=file_name,
        file_size=len(plaintext),
        chunk_count=len(blob.chunk_hashes),
        content_nonce=blob.nonce,
        root_hash=root_hash,
    )
    return publish_manifest(manifest, key, store)


def resolve_manifest(pointer_hash: str, key: bytes, store: ChunkStore) -> bytes:
    manifest = fetch_manifest(pointer_hash, key, store)
    chunk_hashes = walk_index_tree(manifest.root_hash, store)

    if len(chunk_hashes) != manifest.chunk_count:
        raise ManifestFormatError(
            f"chunk_count mismatch: manifest says {manifest.chunk_count}, tree has {len(chunk_hashes)}"
        )

    blob = EncodedBlob(nonce=manifest.content_nonce, chunk_hashes=chunk_hashes)
    return load_plaintext(blob, key, store)
