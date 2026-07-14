# DNS TXT-Record Content Store

A file storage/sharing system that uses DNS TXT records as the transport and cache
layer. Files are encrypted client-side, chunked, and each chunk is published as a TXT
record at a hash-derived hostname under a single shared zone. Sharing a file means
sharing a `pointer_hash` (a real content hash of the encrypted manifest) + a decryption
key; public DNS resolvers opportunistically cache the resulting records, which absorbs
read load without needing a traditional CDN.

**Live downloader:** https://bwu2018.github.io/FileShare/

## How it works

1. **Encrypt** the plaintext once with AES-256-GCM (fresh key + nonce per file).
2. **Chunk** the ciphertext into fixed-size pieces.
3. **Hash + address** each chunk (`hash(nonce + index)`) and publish it as a TXT record
   at `<address>.dnsfileshare.com`.
4. A **manifest** record (file name, chunk count, AEAD nonce) is published the same way,
   addressed by its own `pointer_hash`.
5. To download: fetch the manifest by `pointer_hash`, re-derive every chunk address from
   `nonce` + `chunk_count`, fetch each chunk, reassemble, and decrypt.

The decryption key never touches DNS — it's shared out-of-band alongside the `pointer_hash`. Public resolvers only ever see encrypted bytes.

## Repo layout

| Directory     | Role                                                                                     |
| ------------- | ---------------------------------------------------------------------------------------- |
| `core/`       | Pure library: encrypt/chunk/hash/encode pipeline and its reverse. No DNS.                |
| `manifest/`   | Manifest format, serialization, and publishing helper.                                   |
| `zonegen/`    | Turns chunks + manifest into a valid DNS zone file; RFC 1035 multi-string TXT packing.   |
| `local_dns/`  | Dockerized BIND fixture for testing zone generation and dynamic updates locally.         |
| `downloader/` | Python reference client: fetch manifest + chunks from real DNS, verify, decrypt.         |
| `deploy/`     | Real DNS deployment: RFC 2136 dynamic updates, VPS/zone bootstrap, publish CLI.          |
| `webapp/`     | Static, backend-free browser downloader (DNS-over-HTTPS + WebCrypto, zero-build JS).     |
| `tests/`      | pytest suite for `core`/`manifest`/`zonegen`/`downloader`/`deploy`, one dir per package. |

## Quickstart

**Publish a file** (requires DNS deploy credentials — see `deploy/README.md`):

```
python -m deploy.cli publish path/to/file --name file.txt
```

This prints a `pointer_hash` and key.

**Download a file:**

- Browser: paste the `pointer_hash` and key into https://bwu2018.github.io/FileShare/
  (or serve `webapp/` locally with `python -m http.server`).
- Python: `python -m deploy.cli verify <pointer_hash> <key>`, or use
  `downloader.download_from_dns` directly.

**Try it now** — a small published test file (`hello.txt`, "Hello, world!"):

```
pointer_hash: GSRSYUZXNPIYZBQ7XYX3KSI7D4GDO2VPKG3XF4LIUVAT4F3XVA6A====
key (base64): q3HXEmNuywnDkgzqEhIls7pbg2nPYm4RZzBxCj4yk1s=
```

Paste those into the live downloader above, or run:

```
python -m deploy.cli verify GSRSYUZXNPIYZBQ7XYX3KSI7D4GDO2VPKG3XF4LIUVAT4F3XVA6A==== q3HXEmNuywnDkgzqEhIls7pbg2nPYm4RZzBxCj4yk1s=
```

**Run the tests:**

```
.venv/bin/pytest -v          # core / manifest / zonegen / downloader / deploy
cd webapp && node --test     # webapp's pure-function JS tests
```

## Design notes

- **Encrypt before chunking** — each chunk's DNS _payload_ is ciphertext (its _address_
  is `hash(nonce + index)`, not a hash of the payload — see below), so raw DNS data is
  meaningless without the key.
- **Chunk addressing is `hash(nonce + index)`**, not a stored per-chunk hash list —
  order comes free from the index, and addresses stay non-enumerable without the
  manifest (the nonce isn't derivable without it).
- **Own authoritative nameserver** (self-hosted BIND on a VPS) rather than a managed DNS
  provider, updated via RFC 2136 signed dynamic updates rather than regenerating whole
  zone files — makes the nameserver itself the durable, cumulative store.
- **The downloader is deliberately backend-free.** A server that resolves DNS and
  re-serves chunk bytes over HTTP would recentralize exactly the read load this
  project's DNS-caching design exists to distribute. The browser does its own DoH
  queries and WebCrypto decryption instead.

## Future plans

- Automated end-to-end tests against the live deployment (currently just a manual
  checklist).
- Per-file DNS zones for scaling.
- A cache-warming client.
- A local key record for the publisher to track what they've published.
- Video preview in the webapp.
