"""Manual live-BIND verification driver for the RFC 2136 dynamic-update path
(deploy/dynamic_update.py, deploy/publish.py), validated locally before ever depending
on it against real infrastructure again.

Requires the local_dns/ Docker stack running (`docker compose -f local_dns/docker-compose.yml
up -d`) and dnspython installed (`pip install -r local_dns/requirements.txt`). The zone's
TSIG key ("update-key") is a fixed, local-only test secret baked into named.conf -- never
used against real infrastructure.

NOT discovered or run by pytest -- this talks to a real DNS server and needs a manual
container restart between writing the header-only zone file and sending updates to it.

main() returns the (file_name, pointer_hash, key) tuples it published, so
verify_delete.py can delete those same records instead of publishing its own.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from core import crypto
from core.constants import CHUNK_SIZE
from core.store import ChunkStore
from deploy import DeployError
from deploy.dynamic_update import send_update
from downloader import download_from_dns
from manifest import create_manifest
from zonegen import build_zone, generate_zone_file
from zonegen.records import format_txt_record

ORIGIN = "dnsstore.test."
RESOLVER_IP = "127.0.0.1"
RESOLVER_PORT = 15353
TSIG_KEY_NAME = "update-key"
TSIG_SECRET = "UwUr4X2a/4uCVRYdC2vkCmdLexGeykFUTCbrMsBFPco="
ZONE_FILE_PATH = Path(__file__).parent / "zones" / "dnsstore.test.zone"
JOURNAL_FILE_PATH = ZONE_FILE_PATH.parent / (ZONE_FILE_PATH.name + ".jnl")


def _publish(file_name: str, plaintext: bytes) -> tuple[str, bytes]:
    store = ChunkStore()
    key = crypto.generate_key()
    pointer_hash = create_manifest(plaintext, key, file_name, store)

    rrsets = [format_txt_record(chunk_hash, payload, ORIGIN) for chunk_hash, payload in store.items()]
    send_update(ORIGIN, rrsets, RESOLVER_IP, TSIG_KEY_NAME, TSIG_SECRET, port=RESOLVER_PORT)
    return pointer_hash, key


def _download(pointer_hash: str, key: bytes) -> tuple[str, bytes]:
    return download_from_dns(
        origin=ORIGIN.rstrip("."),
        pointer_hash=pointer_hash,
        key=key,
        resolver_ip=RESOLVER_IP,
        resolver_port=RESOLVER_PORT,
    )


def main() -> list[tuple[str, str, bytes]]:
    print("Writing a header-only zone (no chunk records yet) -- the local equivalent of "
          "deploy.cli bootstrap...")
    # A stale .jnl from a previous run of this script no longer matches the
    # freshly-rewritten zone file below (different serial/content) -- confirmed live
    # that BIND then rejects new dynamic updates (SERVFAIL) against the mismatched pair.
    # A real first-time bootstrap never has a pre-existing journal either.
    JOURNAL_FILE_PATH.unlink(missing_ok=True)
    # Unlink the zone file too, don't just overwrite it: BIND (running as its own uid
    # inside the container) periodically syncs its journal-tracked updates back into
    # this file, including on restart -- so a prior run can leave it owned by BIND, not
    # the host user, and a plain write_text() then fails with PermissionError. Deleting
    # it (allowed by the directory's own write permission, even when the file itself
    # isn't writable by us) and writing a fresh one sidesteps that.
    ZONE_FILE_PATH.unlink(missing_ok=True)
    zone = build_zone(origin=ORIGIN, serial=int(time.time()), ns_ip=RESOLVER_IP)
    ZONE_FILE_PATH.write_text(generate_zone_file(ChunkStore(), zone))
    # World-writable so BIND's own later journal-sync writes don't hit the same
    # problem in reverse (this file is host-owned again now, not BIND's uid).
    ZONE_FILE_PATH.chmod(0o666)
    print(f"Wrote {ZONE_FILE_PATH} (header only).")
    print()

    compose_cmd = ["docker", "compose", "-f", "local_dns/docker-compose.yml"]
    if sys.stdin.isatty():
        print("Now run:  docker compose -f local_dns/docker-compose.yml restart bind9")
        input("Press Enter once BIND has restarted and `logs bind9` shows the zone loaded cleanly...")
    else:
        print("Non-interactive stdin: restarting bind9 automatically...")
        subprocess.run([*compose_cmd, "restart", "bind9"], check=True, cwd=Path(__file__).parent.parent)
        time.sleep(2)

    print("V-DU1: publishing a real file via a real RFC 2136 dynamic update "
          "(deploy.dynamic_update.send_update)...")
    plaintext_1 = os.urandom(3 * CHUNK_SIZE - 16)
    pointer_hash_1, key_1 = _publish("dynamic_update_test.bin", plaintext_1)
    print("V-DU1 OK: dynamic update accepted, no reload/restart needed")

    name_1, downloaded_1 = _download(pointer_hash_1, key_1)
    assert name_1 == "dynamic_update_test.bin" and downloaded_1 == plaintext_1
    print("V-DU2 OK: download_from_dns() resolved the dynamically-added records correctly")

    print("V-DU3: publishing a second file, confirming the first still resolves "
          "(accumulation, not clobbering)...")
    plaintext_2 = os.urandom(500)
    pointer_hash_2, key_2 = _publish("dynamic_update_test2.bin", plaintext_2)

    name_1_again, downloaded_1_again = _download(pointer_hash_1, key_1)
    assert name_1_again == "dynamic_update_test.bin" and downloaded_1_again == plaintext_1
    name_2, downloaded_2 = _download(pointer_hash_2, key_2)
    assert name_2 == "dynamic_update_test2.bin" and downloaded_2 == plaintext_2
    print("V-DU3 OK: second publish accumulated correctly, first file's records untouched")

    print("V-DU4: dynamic update with a wrong TSIG secret should be rejected, not "
          "silently accepted...")
    store = ChunkStore()
    key_3 = crypto.generate_key()
    pointer_hash_3 = create_manifest(os.urandom(100), key_3, "should_not_land.bin", store)
    rrsets_3 = [format_txt_record(h, payload, ORIGIN) for h, payload in store.items()]
    try:
        send_update(ORIGIN, rrsets_3, RESOLVER_IP, TSIG_KEY_NAME, "d29uZ3NlY3JldHZhbHVlMTIzNDU2Nzg=", port=RESOLVER_PORT)
    except DeployError as e:
        print(f"V-DU4 OK: rejected as expected ({e})")
    else:
        raise AssertionError("expected a DeployError for a bad TSIG secret, but the update was accepted")

    print("V-DU5: publishing a real 3MB file, forcing many sequential send_update batches...")
    plaintext_4 = os.urandom(3 * 1024 * 1024)
    pointer_hash_4, key_4 = _publish("large_batched_test.bin", plaintext_4)

    name_4, downloaded_4 = _download(pointer_hash_4, key_4)
    assert name_4 == "large_batched_test.bin" and downloaded_4 == plaintext_4
    print("V-DU5 OK: 3MB file published across multiple batches and round-tripped correctly")

    print()
    print("All checks passed. Run `docker compose -f local_dns/docker-compose.yml down` when done.")

    return [
        ("dynamic_update_test.bin", pointer_hash_1, key_1),
        ("dynamic_update_test2.bin", pointer_hash_2, key_2),
        ("large_batched_test.bin", pointer_hash_4, key_4),
    ]


if __name__ == "__main__":
    main()
