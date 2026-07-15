"""Manual live-BIND verification driver for Phase 3 (zone file generator).

Requires the local_dns/ Docker stack running (`docker compose -f local_dns/docker-compose.yml
up -d`) and dnspython installed (`pip install -r local_dns/requirements.txt`).

NOT discovered or run by pytest -- this talks to a real DNS server and needs a manual
container restart between writing the zone file and querying it. See local_dns/README.md
for the full step-by-step checklist (V1-V7).
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
from core.store import ChunkStore
from downloader import DnsChunkStore, download_from_dns
from manifest import create_manifest, resolve_manifest
from zonegen import build_zone, generate_zone_file

ORIGIN = "dnsstore.test."
RESOLVER_IP = "127.0.0.1"
RESOLVER_PORT = 15353
ZONE_FILE_PATH = Path(__file__).parent / "zones" / "dnsstore.test.zone"


def build_test_store() -> tuple[ChunkStore, str, bytes, bytes, str]:
    """A few small content chunks, plus a deliberately long file_name -- since chunk
    addressing dropped the index tree (hash(nonce+i) addressing), file_name is now the
    only field that can still force a large, multi-string TXT record. 8000 bytes is
    comfortably under manifest/serialization.py's 65,535-byte UTF-8 cap on file_name,
    but -- unlike that cap alone -- was also chosen with headroom under
    zonegen.constants.MAX_TXT_RDATA_SIZE (65,535 wire bytes): the manifest's own
    encrypt+wrap+base64 overhead expands file_name by roughly 4/3, so a file_name
    anywhere near the raw 65,535-byte cap produces a base64 payload that overflows the
    DNS RDATA hard limit once packed into TXT strings (confirmed empirically -- a
    60,000-byte file_name produced an ~80,000-byte RDATA, which real BIND correctly
    refused to load with "ran out of space"). 8000 bytes still comfortably forces
    UDP truncation + multi-string TCP-fallback (matching the old INDEX_NODE_SIZE=8192
    scale from before the index-tree removal) while staying ~6x under the wire-size cap.
    """
    store = ChunkStore()
    key = crypto.generate_key()
    plaintext = os.urandom(3 * CHUNK_SIZE - 16)
    long_file_name = "x" * 8_000
    pointer_hash = create_manifest(plaintext, key, long_file_name, store)
    return store, pointer_hash, key, plaintext, long_file_name


def check_udp_truncation(qname: str) -> bool:
    query = dns.message.make_query(qname, dns.rdatatype.TXT)
    response = dns.query.udp(query, RESOLVER_IP, port=RESOLVER_PORT, timeout=5)
    return bool(response.flags & dns.flags.TC)


def main() -> None:
    print("Building in-memory store (a few content chunks + one long-file_name manifest, "
          "forces a large manifest TXT record)...")
    store, pointer_hash, key, plaintext, long_file_name = build_test_store()
    print(f"  {len(store)} total ChunkStore entries (content chunks + manifest)")
    print(f"  manifest pointer hash: {pointer_hash}")

    zone = build_zone(origin=ORIGIN, serial=int(time.time()))
    # Unlink first, don't just overwrite: BIND (running as its own uid inside the
    # container) can leave this file owned by itself (e.g. via a prior restart's
    # journal-to-zonefile sync), which makes a plain write_text() fail with
    # PermissionError -- deleting it (allowed by the directory's write permission,
    # even when the file itself isn't writable by us) and writing fresh sidesteps that.
    ZONE_FILE_PATH.unlink(missing_ok=True)
    ZONE_FILE_PATH.write_text(generate_zone_file(store, zone))
    # World-writable so BIND's own later journal-sync writes don't hit the same
    # problem in reverse (this file is host-owned again now, not BIND's uid).
    ZONE_FILE_PATH.chmod(0o666)
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
    dns_store = DnsChunkStore(origin=ORIGIN, resolver_ip=RESOLVER_IP, resolver_port=RESOLVER_PORT)
    fetched = dns_store.get(content_hash)
    assert fetched == store.get(content_hash), "content-chunk payload mismatch over DNS"
    print(f"V3 OK: content-chunk record {content_hash[:16]}... round-tripped over DNS")

    # V4: large manifest record (long file_name) -- UDP truncation + TCP fallback
    large_hash = max(store.items(), key=lambda kv: len(kv[1]))[0]
    qname = f"{large_hash}.chunks.{ORIGIN}"
    truncated = check_udp_truncation(qname)
    print(f"V4: large record ({len(store.get(large_hash))} base64 chars) UDP truncated = {truncated}")
    fetched_large = dns_store.get(large_hash)
    assert fetched_large == store.get(large_hash), "large-record payload mismatch over DNS"
    print("V4 OK: large manifest record (long file_name) round-tripped over DNS (TCP fallback if needed)")

    # V5: full-stack resolve, starting only from the pointer hash + key, entirely via DNS
    resolved = resolve_manifest(pointer_hash, key, dns_store)
    assert resolved == plaintext, "full-stack DNS-served round trip mismatch"
    print("V5 OK: resolve_manifest() reconstructed the exact original plaintext via DNS-served records")

    # V6: full end-to-end download_from_dns() -- starting only from origin + pointer_hash
    # + key, never reading directly from the in-memory store (Phase 4's validation harness)
    downloaded_name, downloaded_plaintext = download_from_dns(
        origin=ORIGIN.rstrip("."),
        pointer_hash=pointer_hash,
        key=key,
        resolver_ip=RESOLVER_IP,
        resolver_port=RESOLVER_PORT,
    )
    assert downloaded_name == long_file_name, "downloaded file_name mismatch"
    assert downloaded_plaintext == plaintext, "downloaded plaintext mismatch"
    print("V6 OK: downloader.download_from_dns() reconstructed file_name + plaintext via real DNS")

    print()
    print("All checks passed. Run `docker compose -f local_dns/docker-compose.yml down` when done.")


if __name__ == "__main__":
    main()
