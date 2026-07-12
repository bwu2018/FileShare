"""Manual live-BIND verification driver for Phase 3 (zone file generator).

Requires the local_dns/ Docker stack running (`docker compose -f local_dns/docker-compose.yml
up -d`) and dnspython installed (`pip install -r local_dns/requirements.txt`).

NOT discovered or run by pytest -- this talks to a real DNS server and needs a manual
container restart between writing the zone file and querying it. See local_dns/README.md
for the full step-by-step checklist (V1-V6).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import dns.flags
import dns.message
import dns.query
import dns.rdatatype

from core import crypto
from core.constants import CHUNK_SIZE
from core.exceptions import ChunkNotFoundError
from core.store import ChunkStore
from manifest import create_manifest, resolve_manifest
from manifest.constants import MAX_HASHES_PER_NODE
from zonegen import ZoneConfig, generate_zone_file, unpack_txt_strings

ORIGIN = "dnsstore.test."
RESOLVER_IP = "127.0.0.1"
RESOLVER_PORT = 15353
ZONE_FILE_PATH = Path(__file__).parent / "zones" / "dnsstore.test.zone"


class DnsChunkStore:
    """Read-only ChunkStore-compatible adapter backed by a live DNS server.

    Only implements get() -- that's all core.pipeline.load_plaintext /
    manifest.resolve_manifest need to walk the manifest -> index tree -> content chunks
    entirely through DNS-served records, proving the full stack survives real wire
    transport, not just the raw TXT-record layer in isolation.
    """

    def get(self, chunk_hash: str) -> str:
        qname = f"{chunk_hash}.chunks.{ORIGIN}"
        query = dns.message.make_query(qname, dns.rdatatype.TXT)
        response = dns.query.udp(query, RESOLVER_IP, port=RESOLVER_PORT, timeout=5)
        if response.flags & dns.flags.TC:
            response = dns.query.tcp(query, RESOLVER_IP, port=RESOLVER_PORT, timeout=5)

        if not response.answer:
            raise ChunkNotFoundError(chunk_hash)

        strings = [s.decode("ascii") for s in response.answer[0][0].strings]
        return unpack_txt_strings(strings)


def build_test_store() -> tuple[ChunkStore, str, bytes]:
    """Deliberately >MAX_HASHES_PER_NODE (146) content chunks, so build_index_tree emits
    a real is_leaf=False root over a near-max-size leaf IndexNode (~8181 raw bytes / ~43
    TXT strings) -- exercising the large-record/TCP-fallback path phase2.md flagged as
    unvalidated, not just small single-string content-chunk records.
    """
    store = ChunkStore()
    key = crypto.generate_key()
    # 147 full-size content chunks: ciphertext = plaintext + 16-byte AEAD tag
    plaintext = os.urandom(147 * CHUNK_SIZE - 16)
    pointer_hash = create_manifest(plaintext, key, "verify.bin", store)
    return store, pointer_hash, key, plaintext


def check_udp_truncation(qname: str) -> bool:
    query = dns.message.make_query(qname, dns.rdatatype.TXT)
    response = dns.query.udp(query, RESOLVER_IP, port=RESOLVER_PORT, timeout=5)
    return bool(response.flags & dns.flags.TC)


def main() -> None:
    print("Building in-memory store (147 content chunks, forces real index-tree recursion)...")
    store, pointer_hash, key, plaintext = build_test_store()
    print(f"  {len(store)} total ChunkStore entries (content chunks + index nodes + manifest)")
    print(f"  manifest pointer hash: {pointer_hash}")

    config = ZoneConfig(origin=ORIGIN, serial=int(time.time()))
    ZONE_FILE_PATH.write_text(generate_zone_file(store, config))
    print(f"Wrote {ZONE_FILE_PATH} ({len(store)} records).")
    print()
    compose_cmd = ["docker", "compose", "-f", "local_dns/docker-compose.yml"]
    if sys.stdin.isatty():
        print("Now run:  docker compose -f local_dns/docker-compose.yml restart bind9")
        input("Press Enter once BIND has restarted and `logs bind9` shows the zone loaded cleanly...")
    else:
        print("Non-interactive stdin: restarting bind9 automatically...")
        subprocess.run([*compose_cmd, "restart", "bind9"], check=True, cwd=Path(__file__).parent.parent)
        time.sleep(2)

    # V3: small content-chunk record round trip
    content_hash = next(h for h, _ in store.items() if h != pointer_hash)
    dns_store = DnsChunkStore()
    fetched = dns_store.get(content_hash)
    assert fetched == store.get(content_hash), "content-chunk payload mismatch over DNS"
    print(f"V3 OK: content-chunk record {content_hash[:16]}... round-tripped over DNS")

    # V4: large index-node record -- UDP truncation + TCP fallback
    large_hash = max(store.items(), key=lambda kv: len(kv[1]))[0]
    qname = f"{large_hash}.chunks.{ORIGIN}"
    truncated = check_udp_truncation(qname)
    print(f"V4: large record ({len(store.get(large_hash))} base64 chars) UDP truncated = {truncated}")
    fetched_large = dns_store.get(large_hash)
    assert fetched_large == store.get(large_hash), "large-record payload mismatch over DNS"
    print("V4 OK: large index-node record round-tripped over DNS (TCP fallback if needed)")

    # V5: full-stack resolve, starting only from the pointer hash + key, entirely via DNS
    resolved = resolve_manifest(pointer_hash, key, dns_store)
    assert resolved == plaintext, "full-stack DNS-served round trip mismatch"
    print("V5 OK: resolve_manifest() reconstructed the exact original plaintext via DNS-served records")

    print()
    print("All checks passed. Run `docker compose -f local_dns/docker-compose.yml down` when done.")


if __name__ == "__main__":
    main()
