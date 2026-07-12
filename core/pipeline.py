from . import crypto
from .chunking import join_chunks, split_into_chunks
from .constants import CHUNK_SIZE
from .encoding import decode_chunk, encode_chunk
from .exceptions import ChunkHashMismatchError
from .hashing import compute_chunk_hash
from .models import EncodedBlob
from .store import ChunkStore


def store_plaintext(
    plaintext: bytes, key: bytes, store: ChunkStore, chunk_size: int = CHUNK_SIZE
) -> EncodedBlob:
    nonce, ciphertext = crypto.encrypt(key, plaintext)
    chunk_hashes = []
    for chunk in split_into_chunks(ciphertext, chunk_size):
        chunk_hash = compute_chunk_hash(chunk)
        store.put(chunk_hash, encode_chunk(chunk))
        chunk_hashes.append(chunk_hash)
    return EncodedBlob(nonce=nonce, chunk_hashes=chunk_hashes)


def load_plaintext(blob: EncodedBlob, key: bytes, store: ChunkStore) -> bytes:
    chunks = []
    for chunk_hash in blob.chunk_hashes:
        chunk = decode_chunk(store.get(chunk_hash))
        if compute_chunk_hash(chunk) != chunk_hash:
            raise ChunkHashMismatchError(chunk_hash)
        chunks.append(chunk)
    ciphertext = join_chunks(chunks)
    return crypto.decrypt(key, blob.nonce, ciphertext)
