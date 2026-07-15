# DNS TXT-Record Content Store

A file storage/sharing system that uses DNS TXT records as the transport and cache
layer. Files are encrypted client-side, chunked, and each chunk is published as a TXT
record at a hash-derived hostname under a single shared zone. Uploading and
downloading both happen entirely in the browser; sharing a file means sharing a link
that carries a `pointer_hash` (a real content hash of the encrypted manifest) and a
decryption key. Public DNS resolvers opportunistically cache the resulting records,
which absorbs read load without needing a traditional CDN.

**Live site:** https://dnsfileshare.com/

## How it works

1. **Upload** (browser, `webapp/upload.js`): encrypt the plaintext with AES-256-GCM
   (fresh key + nonce per file), chunk the ciphertext, hash+address each chunk
   (`hash(nonce + index)`), and build a manifest record (file name, chunk count, AEAD
   nonce) addressed by its own `pointer_hash`. The browser POSTs only these already-
   encrypted `(hash, payload)` records to `backend/`, which performs the actual signed
   DNS write — it never sees plaintext or the key. The upload page then shows a share
   link: `https://dnsfileshare.com/download/#pointer_hash=<...>&key=<...>`.
2. **Download** (browser, `webapp/download.js`): parses the link's URL fragment,
   fetches the manifest by `pointer_hash`, re-derives every chunk address from
   `nonce` + `chunk_count`, fetches each chunk via DNS-over-HTTPS, reassembles, and
   decrypts — all client-side.

The decryption key (and the `pointer_hash`) travel only in the URL fragment, never the
query string, so neither is ever sent to a server or written to an access log. Public
resolvers only ever see encrypted bytes.

## Repo layout

| Directory     | Role                                                                                                                    |
| ------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `core/`       | Pure library: encrypt/chunk/hash/encode pipeline and its reverse. No DNS.                                               |
| `manifest/`   | Manifest format, serialization, and publishing helper.                                                                  |
| `zonegen/`    | Turns chunks + manifest into a valid DNS zone file; RFC 1035 multi-string TXT packing.                                  |
| `local_dns/`  | Dockerized BIND fixture for testing zone generation and dynamic updates locally.                                        |
| `downloader/` | Python reference client: fetch manifest + chunks from real DNS, verify, decrypt.                                        |
| `deploy/`     | Real DNS deployment: RFC 2136 dynamic updates, VPS/zone bootstrap, publish CLI.                                         |
| `backend/`    | Small Flask service the browser uploader talks to — the only thing with DNS write credentials that a browser can reach. |
| `webapp/`     | Static browser front end: upload page + link-based downloader (DNS-over-HTTPS + WebCrypto, zero-build JS).              |
| `tests/`      | pytest suite for `core`/`manifest`/`zonegen`/`downloader`/`deploy`/`backend`, one dir per package.                      |

## Quickstart

**Upload a file** (browser):

- Open the webapp's main page. Choose a file, click **Upload**, and copy the resulting
  share link. Filenames must have extensions.

**Upload a file** (CLI — scripting/automation, requires DNS deploy credentials, see
`deploy/README.md`):

```
python -m deploy.cli publish path/to/file --name file.txt
```

**Download a file:**

- Browser: open the share link (`https://dnsfileshare.com/download/#pointer_hash=...&key=...`).
- Python: `python -m deploy.cli verify <pointer_hash> <key>`, or use
  `downloader.download_from_dns` directly.

**Try it now** — a small published test file (`hello.txt`, "Hello, world!"):

```
pointer_hash: GSRSYUZXNPIYZBQ7XYX3KSI7D4GDO2VPKG3XF4LIUVAT4F3XVA6A====
key (base64): q3HXEmNuywnDkgzqEhIls7pbg2nPYm4RZzBxCj4yk1s=
```

Open https://dnsfileshare.com/download/#pointer_hash=GSRSYUZXNPIYZBQ7XYX3KSI7D4GDO2VPKG3XF4LIUVAT4F3XVA6A====&key=q3HXEmNuywnDkgzqEhIls7pbg2nPYm4RZzBxCj4yk1s=,
or run:

```
python -m deploy.cli verify GSRSYUZXNPIYZBQ7XYX3KSI7D4GDO2VPKG3XF4LIUVAT4F3XVA6A==== q3HXEmNuywnDkgzqEhIls7pbg2nPYm4RZzBxCj4yk1s=
```

**Run the tests:**

```
.venv/bin/pytest -v          # core / manifest / zonegen / downloader / deploy / backend
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
- **The backend only ever relays already-encrypted bytes.** The browser does all
  encryption, chunking, and hashing itself; `backend/` exists solely because the TSIG
  secret that authenticates DNS writes can't be shipped to client-side JS. It never
  sees plaintext or the decryption key.
- **Downloading is still backend-free.** A server that resolves DNS and re-serves
  chunk bytes over HTTP would recentralize exactly the read load this project's
  DNS-caching design exists to distribute, so `backend/` is deliberately upload-only —
  the browser still does its own DoH queries and WebCrypto decryption for downloads,
  and Caddy serves the static webapp directly (not proxied through the backend), so a
  backend outage can never break the ability to load a share link.

## Future plans

- Automated end-to-end tests against the live deployment (currently just a manual
  checklist)
- Per-file DNS zones for scaling
- A cache-warming client
- A local key record for the publisher to track what they've published
- Video preview in the webapp
- Oauth
