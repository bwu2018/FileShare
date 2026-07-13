from typing import Protocol

from core.models import EncodedBlob
from core.pipeline import load_plaintext
from manifest.publish import fetch_manifest

from .constants import DEFAULT_RESOLVER_PORT
from .dns_store import DnsChunkStore


class ReadableChunkStore(Protocol):
    def get(self, chunk_hash: str) -> str: ...


def download_from_store(pointer_hash: str, key: bytes, store: ReadableChunkStore) -> tuple[str, bytes]:
    manifest = fetch_manifest(pointer_hash, key, store)
    blob = EncodedBlob(nonce=manifest.content_nonce, chunk_count=manifest.chunk_count)
    plaintext = load_plaintext(blob, key, store)
    return manifest.file_name, plaintext


def download_from_dns(
    origin: str,
    pointer_hash: str,
    key: bytes,
    resolver_ip: str,
    resolver_port: int = DEFAULT_RESOLVER_PORT,
) -> tuple[str, bytes]:
    store = DnsChunkStore(origin, resolver_ip, resolver_port)
    return download_from_store(pointer_hash, key, store)
