# local_dns

A reusable local BIND fixture for validating that generated zone files actually behave
correctly over real DNS wire transport, before touching real infrastructure (Phase 5,
real deployment). This fixture is shared beyond Phase 3 — the downloader validation
harness (Phase 4) reuses the same running BIND instance to test real DNS resolution.

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
record — since chunk addressing is `hash(nonce+i)`-based rather than an index tree,
`file_name` is the only field that can still force a large record. It writes
`zones/dnsstore.test.zone`, then pauses for you
to restart BIND, then runs four checks against the live server:

- **V3** — a small content-chunk record round-trips correctly over DNS.
- **V4** — the large manifest record (long `file_name`) round-trips correctly, and
  reports whether the initial UDP query came back truncated (`TC` flag) before
  falling back to TCP.
- **V5** — a full end-to-end resolve, starting only from the manifest pointer hash and
  key, reconstructs the exact original plaintext using only DNS-served records (no
  reads from the in-memory `ChunkStore` at all).
- **V6** — the same full end-to-end reconstruction as V5, but via `downloader`'s public
  `download_from_dns(origin, pointer_hash, key, resolver_ip, resolver_port)` entry point
  instead of the lower-level `resolve_manifest`/`DnsChunkStore` pieces directly — proves
  Phase 4's validation harness (`downloader/dns_store.py`, `downloader/pipeline.py`)
  works end-to-end against the real fixture, and also confirms the reconstructed
  `file_name` matches, which V5 doesn't check.

## Running the dynamic-update (RFC 2136) verification driver

```
.venv/bin/python -m local_dns.verify_dynamic_update
```

**Run as a module (`-m local_dns.verify_dynamic_update`), not as a plain script path**
(`python local_dns/verify_dynamic_update.py`) — the latter fails with `ModuleNotFoundError:
No module named 'core'`, since Python adds the *script's own directory* to `sys.path`,
not the current working directory. `-m` adds the cwd instead, which is what makes `core`/
`manifest`/`deploy`/etc. importable. (This applies to `verify_zone.py` too, even though
this README previously showed the plain-script form.)

This validates `deploy/dynamic_update.py`/`deploy/publish.py` (RFC 2136 + TSIG dynamic
updates) locally before depending on them against real infrastructure — the zone's TSIG
key (`update-key`) is a fixed, local-only test secret baked into `named.conf`, never used
against anything real. It writes a header-only zone (the local equivalent of `deploy.cli
bootstrap`), then:

- **V-DU1** — publishes a real file via `deploy.dynamic_update.send_update`, no
  reload/restart needed at all (dynamic updates apply live).
- **V-DU2** — confirms it's actually resolvable via `download_from_dns()`, not just
  "accepted."
- **V-DU3** — publishes a *second* file and confirms the *first* one still resolves
  correctly — the direct test of RFC 2136 accumulation (not clobbering), the actual
  correctness property this whole design depends on.
- **V-DU4** — confirms a wrong TSIG secret is rejected, not silently accepted.
- **V-DU5** — publishes a real 3MB file, forcing many sequential `send_update` batches
  (`DNS_UPDATE_BATCH_SIZE` records per RFC 2136 UPDATE message), and confirms it
  round-trips byte-for-byte — proves the batching fix actually works against a real
  BIND server, not just in unit tests.

`main()` returns the `(file_name, pointer_hash, key)` of every file it published, so
`verify_delete.py` (below) can delete those same records instead of publishing its own.

## Running the delete verification driver

```
.venv/bin/python -m local_dns.verify_delete
```

Validates `deploy/dynamic_update.py`'s `build_delete_update`/`send_delete` against the
same live BIND container. Rather than publish its own test files, it calls
`verify_dynamic_update.main()` first (same zone reset, same restart) and deletes exactly
what that published:

- **V-DEL1** — confirms a still-live published record's TTL reflects the current
  `RECORD_TTL` value.
- **V-DEL2** — deletes every file `verify_dynamic_update` published, including the 3MB
  one, which forces multiple sequential `send_delete` batches.
- **V-DEL3** — confirms every deleted address (manifest + every content chunk) now
  resolves to NXDOMAIN.

**Two real, Docker-specific gotchas fixed while building this** (beyond the separate
real-VPS bugs found during deployment):
- `docker-compose.yml`'s `zones/` volume was originally mounted `:ro` — BIND needs write
  access there to create a `.jnl` journal file for dynamic updates, the same class of
  problem as the AppArmor issue found on the real VPS, just a different mechanism
  (Docker bind-mount permissions here, not AppArmor).
- The container's internal `named` process runs as UID 53 (hardcoded by the image's own
  entrypoint, unaffected by Docker's `user:` directive), while the host-side `zones/`
  directory is owned by the host user's UID — `chmod o+w local_dns/zones/` is the
  pragmatic fix, acceptable since this fixture is loopback-only and never networked.
- The script deletes any pre-existing `.jnl` journal file before writing a fresh zone
  file each run — a stale journal from a previous run doesn't match a freshly-rewritten
  zone file (different serial/content), which BIND correctly rejects new updates
  against (confirmed live: `SERVFAIL` on the very next update attempt otherwise). A real
  first-time bootstrap never has a pre-existing journal either, so this isn't
  papering over anything specific to the fixture.

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

## Checklist (V1-V7, V-DU1-V-DU5 for dynamic updates, V-DEL1-V-DEL3 for delete)

1. **V1.** `docker compose -f local_dns/docker-compose.yml up -d`; confirm the zone loads
   cleanly via `logs bind9` (no error lines).
2. **V2.** Run `.venv/bin/python -m local_dns.verify_zone` (module form, not the plain
   script path — see above); restart BIND when prompted.
3. **V3-V6.** Handled automatically by `verify_zone.py` (see above).
4. **V-DEL1-V-DEL3.** Run `.venv/bin/python -m local_dns.verify_delete` — this runs
   `verify_dynamic_update.main()` internally first (covering V-DU1-V-DU5), then runs its
   own delete checks against exactly what got published. Running
   `.venv/bin/python -m local_dns.verify_dynamic_update` on its own is still fine too if
   you only want the publish-side checks, without deleting anything afterward.
5. **V7.** `docker compose -f local_dns/docker-compose.yml down` (or `restart bind9` to
   iterate again with a freshly regenerated zone).
