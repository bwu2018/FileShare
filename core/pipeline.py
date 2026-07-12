from . import crypto
from .chunking import join_chunks, split_into_chunks
from .constants import CHUNK_SIZE
from .encoding import decode_chunk, encode_chunk
from .hashing import compute_chunk_address
from .models import EncodedBlob
from .store import ChunkStore


def store_plaintext(
    plaintext: bytes, key: bytes, store: ChunkStore, chunk_size: int = CHUNK_SIZE
) -> EncodedBlob:
    nonce, ciphertext = crypto.encrypt(key, plaintext)
    chunks = split_into_chunks(ciphertext, chunk_size)
    for i, chunk in enumerate(chunks):
        store.put(compute_chunk_address(nonce, i), encode_chunk(chunk))
    return EncodedBlob(nonce=nonce, chunk_count=len(chunks))


def load_plaintext(blob: EncodedBlob, key: bytes, store: ChunkStore) -> bytes:
    chunks = []
    for i in range(blob.chunk_count):
        address = compute_chunk_address(blob.nonce, i)
        chunks.append(decode_chunk(store.get(address)))
    ciphertext = join_chunks(chunks)
    return crypto.decrypt(key, blob.nonce, ciphertext)
