from dataclasses import dataclass


@dataclass(frozen=True)
class Manifest:
    version: int
    file_name: str
    file_size: int
    chunk_count: int
    content_nonce: bytes
