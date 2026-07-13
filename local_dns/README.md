# local_dns

A reusable local BIND fixture for validating that generated zone files actually behave
correctly over real DNS wire transport, before touching real infrastructure (Phase 4,
real deployment). This fixture is shared beyond Phase 3 — the downloader-client phase
(Phase 4) reuses the same running BIND instance to test real DNS resolution.

## Prerequisites

- Docker Desktop with WSL integration enabled for this distro (Settings -> Resources ->
  WSL Integration -> enable this distro -> Apply & Restart), so `docker compose` works
  from this shell.
- `pip install -r local_dns/requirements.txt` (installs `dnspython`) into the project's
  `.venv`, e.g. `.venv/bin/pip install -r local_dns/requirements.txt`.

## Start / stop / reset

```
docker compose -f local_dns/docker-compose.yml up -d              # start
docker compose -f local_dns/docker-compose.yml logs bind9          # confirm zone loaded cleanly
docker compose -f local_dns/docker-compose.yml restart bind9      # reload after regenerating the zone
docker compose -f local_dns/docker-compose.yml down                # stop
docker compose -f local_dns/docker-compose.yml down -v && \
  docker compose -f local_dns/docker-compose.yml up -d            # full reset
```

BIND is bound to `127.0.0.1:15353` (not port 53), to avoid conflicting with WSL2's own
resolver and to avoid needing an elevated host privilege for a low port. (Port 5353 was
tried first but conflicts with mDNS on the Windows host — Chrome/Steam commonly hold it
for local network discovery — which made Docker Desktop's port forwarder fail with a 500
error on container start.)

BIND re-reads the zone file fully on process **restart** — there is no live/incremental
reload configured (`rndc` isn't set up), so always `restart bind9` after regenerating
`zones/dnsstore.test.zone`, not just `up -d` again.

## Running the verification driver

```
.venv/bin/python local_dns/verify_zone.py
```

This builds an in-memory store with a few small content chunks plus one manifest
record with a deliberately long `file_name` (up to the 65,535-byte UTF-8 cap
`manifest/serialization.py` enforces), producing at least one large, multi-string TXT
record — since removing the index tree (chunk addressing moved to `hash(nonce+i)`,
see `CLAUDE.md`'s addressing revision) left `file_name` as the only field that can
still force a large record. It writes `zones/dnsstore.test.zone`, then pauses for you
to restart BIND, then runs three checks against the live server:

- **V3** — a small content-chunk record round-trips correctly over DNS.
- **V4** — the large manifest record (long `file_name`) round-trips correctly, and
  reports whether the initial UDP query came back truncated (`TC` flag) before
  falling back to TCP.
- **V5** — a full end-to-end resolve, starting only from the manifest pointer hash and
  key, reconstructs the exact original plaintext using only DNS-served records (no
  reads from the in-memory `ChunkStore` at all).

## Manual `dig` invocations

`dig` isn't installed on the host; the BIND container image ships with it already:

```
docker compose -f local_dns/docker-compose.yml exec bind9 \
  dig @127.0.0.1 <hash>.chunks.dnsstore.test TXT
```

To specifically inspect UDP truncation vs. TCP fallback for a large record:

```
docker compose -f local_dns/docker-compose.yml exec bind9 \
  dig @127.0.0.1 <hash>.chunks.dnsstore.test TXT +notcp +ignore   # inspect the tc flag
docker compose -f local_dns/docker-compose.yml exec bind9 \
  dig @127.0.0.1 <hash>.chunks.dnsstore.test TXT +tcp             # confirm full answer over TCP
```

Optional host-side convenience (needs `sudo apt install -y dnsutils`):

```
dig @127.0.0.1 -p 15353 <hash>.chunks.dnsstore.test TXT +short
```

## Checklist (V1-V6)

1. **V1.** `docker compose -f local_dns/docker-compose.yml up -d`; confirm the zone loads
   cleanly via `logs bind9` (no error lines).
2. **V2.** Run `local_dns/verify_zone.py`; restart BIND when prompted.
3. **V3-V5.** Handled automatically by `verify_zone.py` (see above).
4. **V6.** `docker compose -f local_dns/docker-compose.yml down` (or `restart bind9` to
   iterate again with a freshly regenerated zone).
