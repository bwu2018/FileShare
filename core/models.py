from dataclasses import dataclass


@dataclass(frozen=True)
class EncodedBlob:
    nonce: bytes
    chunk_count: int
