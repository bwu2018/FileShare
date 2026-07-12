import base64
import hashlib
import struct


def compute_chunk_hash(chunk: bytes) -> str:
    digest = hashlib.sha256(chunk).digest()
    return base64.b32encode(digest).decode("ascii")


def compute_chunk_address(nonce: bytes, index: int) -> str:
    digest = hashlib.sha256(nonce + struct.pack(">I", index)).digest()
    return base64.b32encode(digest).decode("ascii")
