"""Manual live-BIND verification driver for the delete primitive
(deploy/dynamic_update.py's build_delete_update/send_delete).

Requires the local_dns/ Docker stack running, same as verify_dynamic_update.py.

Rather than publish its own fresh test files, this reuses whatever
verify_dynamic_update.main() already published in the same run (same zone reset,
same restarted container) -- no duplicate publishing, and delete gets proven
against exactly the records publish already proved work. Calls send_delete()
directly (with an explicit port override) rather than deploy/delete.py's
delete_file(), the same way verify_dynamic_update.py calls send_update()
directly instead of deploy/publish.py's publish_file() -- both need to target
the local container's RESOLVER_PORT (15353), not production's default port 53.

Run as a module: `.venv/bin/python -m local_dns.verify_delete`
"""

import dns.message
import dns.query
import dns.rcode
import dns.rdatatype

from deploy.dynamic_update import send_delete
from downloader.dns_store import DnsChunkStore
from manifest import list_stored_addresses
from zonegen.constants import CHUNKS_LABEL, RECORD_TTL

from . import verify_dynamic_update as vdu


def _delete(pointer_hash: str, key: bytes) -> int:
    # Mirrors verify_dynamic_update.py's own _publish()/_download(): calls the real
    # deploy.dynamic_update primitives directly with an explicit port, since the local
    # BIND container listens on RESOLVER_PORT (15353), not deploy/delete.py's
    # production-default port 53.
    store = DnsChunkStore(vdu.ORIGIN, vdu.RESOLVER_IP, vdu.RESOLVER_PORT)
    addresses = list_stored_addresses(pointer_hash, key, store)
    send_delete(vdu.ORIGIN, addresses, vdu.RESOLVER_IP, vdu.TSIG_KEY_NAME, vdu.TSIG_SECRET, port=vdu.RESOLVER_PORT)
    return addresses


def _query_ttl(qname: str) -> int:
    query = dns.message.make_query(qname, dns.rdatatype.TXT)
    response = dns.query.udp(query, vdu.RESOLVER_IP, port=vdu.RESOLVER_PORT, timeout=5)
    return response.answer[0].ttl


def _is_nxdomain(qname: str) -> bool:
    query = dns.message.make_query(qname, dns.rdatatype.TXT)
    response = dns.query.udp(query, vdu.RESOLVER_IP, port=vdu.RESOLVER_PORT, timeout=5)
    return response.rcode() == dns.rcode.NXDOMAIN


def main() -> None:
    published = vdu.main()

    print("V-DEL1: checking a still-live record's TTL reflects the current RECORD_TTL...")
    file_name, pointer_hash, _key = published[0]
    qname = f"{pointer_hash}.{CHUNKS_LABEL}.{vdu.ORIGIN}"
    ttl = _query_ttl(qname)
    assert ttl == RECORD_TTL, f"expected TTL {RECORD_TTL}, got {ttl}"
    print(f"V-DEL1 OK: {file_name}'s manifest record has TTL={ttl}")

    print("V-DEL2: deleting every published file (including the 3MB one, forcing "
          "multiple sequential send_delete batches)...")
    all_addresses: list[str] = []
    for file_name, pointer_hash, key in published:
        addresses = _delete(pointer_hash, key)
        all_addresses.extend(addresses)
        print(f"  deleted {len(addresses)} records for {file_name!r}")
    print("V-DEL2 OK: send_delete() accepted for every published file")

    print("V-DEL3: confirming every deleted address now resolves to NXDOMAIN...")
    for address in all_addresses:
        qname = f"{address}.{CHUNKS_LABEL}.{vdu.ORIGIN}"
        assert _is_nxdomain(qname), f"expected NXDOMAIN for {qname}, record still resolves"
    print(f"V-DEL3 OK: all {len(all_addresses)} deleted addresses are NXDOMAIN")

    print()
    print("All checks passed. Run `docker compose -f local_dns/docker-compose.yml down` when done.")


if __name__ == "__main__":
    main()
