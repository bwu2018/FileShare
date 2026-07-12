import base64
import hashlib


def compute_chunk_hash(chunk: bytes) -> str:
    digest = hashlib.sha256(chunk).digest()
    return base64.b32encode(digest).decode("ascii")
