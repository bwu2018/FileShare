"""Manual live-infrastructure verification driver for publish + delete against the
real production deployment. Requires production credentials already sourced:

    source ~/.config/dnsfileshare/deploy.env

NOT discovered or run by pytest. Unlike local_dns/'s harness, this can never reset
the whole zone between runs -- production holds other real, permanent records -- so
every test file this publishes must be individually, reliably deleted afterward,
including on failure (see the try/finally in _run_case below).

Run as a module: `.venv/bin/python -m e2e.verify_live`
"""

import os
import tempfile
from pathlib import Path

import dns.message
import dns.query
import dns.rcode
import dns.rdatatype

from deploy.config import DeployConfig
from deploy.dynamic_update import send_delete
from deploy.publish import publish_file
from downloader import DnsChunkStore, download_from_dns
from manifest import list_stored_addresses
from zonegen.constants import CHUNKS_LABEL, RECORD_TTL

PUBLIC_RESOLVER_IP = "1.1.1.1"


def _query_ttl(qname: str, resolver_ip: str) -> int:
    query = dns.message.make_query(qname, dns.rdatatype.TXT)
    response = dns.query.udp(query, resolver_ip, port=53, timeout=5)
    return response.answer[0].ttl


def _is_nxdomain(qname: str, resolver_ip: str) -> bool:
    query = dns.message.make_query(qname, dns.rdatatype.TXT)
    response = dns.query.udp(query, resolver_ip, port=53, timeout=5)
    return response.rcode() == dns.rcode.NXDOMAIN


def _run_case(config: DeployConfig, file_name: str, plaintext: bytes) -> None:
    print(f"--- {file_name} ({len(plaintext)} bytes) ---")

    with tempfile.NamedTemporaryFile(suffix=f"_{file_name}") as tmp:
        tmp.write(plaintext)
        tmp.flush()
        pointer_hash, key = publish_file(Path(tmp.name), file_name, config)
    print(f"published: pointer_hash={pointer_hash}")

    store = DnsChunkStore(config.origin, config.vps_ip)
    addresses = list_stored_addresses(pointer_hash, key, store)
    print(f"  {len(addresses)} addresses (manifest + content chunks)")

    try:
        origin_bare = config.origin.rstrip(".")

        name, downloaded = download_from_dns(origin_bare, pointer_hash, key, config.vps_ip)
        assert name == file_name and downloaded == plaintext
        print("  OK: round-trips correctly directly against the VPS")

        name, downloaded = download_from_dns(origin_bare, pointer_hash, key, PUBLIC_RESOLVER_IP)
        assert name == file_name and downloaded == plaintext
        print(f"  OK: round-trips correctly through public resolver {PUBLIC_RESOLVER_IP}")

        qname = f"{pointer_hash}.{CHUNKS_LABEL}.{config.origin}"
        ttl = _query_ttl(qname, config.vps_ip)
        assert ttl == RECORD_TTL, f"expected TTL {RECORD_TTL}, got {ttl}"
        print(f"  OK: manifest record TTL={ttl}")
    finally:
        send_delete(config.origin, addresses, config.vps_ip, config.tsig_key_name, config.tsig_secret)
        print(f"  deleted {len(addresses)} records")

        for address in addresses:
            qname = f"{address}.{CHUNKS_LABEL}.{config.origin}"
            assert _is_nxdomain(qname, config.vps_ip), f"expected NXDOMAIN for {qname}, still resolves"
        print("  OK: every address is NXDOMAIN at the VPS")


def main() -> None:
    config = DeployConfig.from_env()
    print(f"Target: {config.origin} @ {config.vps_ip}")
    print()

    _run_case(config, "e2e_live_small.bin", os.urandom(500))
    print()
    _run_case(config, "e2e_live_batched.bin", os.urandom(100_000))

    print()
    print("All checks passed. Production zone left exactly as it was before this run.")


if __name__ == "__main__":
    main()
