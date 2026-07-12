from core import crypto
from core.constants import NONCE_SIZE
from core.encoding import decode_chunk, encode_chunk
from core.exceptions import ChunkHashMismatchError
from core.hashing import compute_chunk_hash
from core.store import ChunkStore

from .models import Manifest
from .serialization import deserialize_manifest, serialize_manifest


def publish_manifest(manifest: Manifest, key: bytes, store: ChunkStore) -> str:
    serialized = serialize_manifest(manifest)
    manifest_nonce, ciphertext = crypto.encrypt(key, serialized)
    wrapped = manifest_nonce + ciphertext

    pointer_hash = compute_chunk_hash(wrapped)
    store.put(pointer_hash, encode_chunk(wrapped))
    return pointer_hash


def fetch_manifest(pointer_hash: str, key: bytes, store: ChunkStore) -> Manifest:
    encoded = store.get(pointer_hash)
    wrapped = decode_chunk(encoded)
    if compute_chunk_hash(wrapped) != pointer_hash:
        raise ChunkHashMismatchError(pointer_hash)

    manifest_nonce, ciphertext = wrapped[:NONCE_SIZE], wrapped[NONCE_SIZE:]
    serialized = crypto.decrypt(key, manifest_nonce, ciphertext)
    return deserialize_manifest(serialized)
