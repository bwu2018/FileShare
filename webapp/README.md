# webapp

The real end-user downloader: a static, backend-free webapp. Paste a pointer hash and a
base64 key, and the browser resolves and decrypts the file entirely client-side via
DNS-over-HTTPS (Cloudflare's JSON API) and WebCrypto, then previews it inline if it's a
recognized type (text or image for v1 -- video is a future addition). No server of this
project's ever sees the key or the plaintext, and no server of this project's serves
chunk bytes.

## Structure

Zero-build vanilla JS -- no bundler, no framework, no npm install step to deploy. Each
`.js` file maps to one pipeline step, mirroring the Python side's module discipline
(`core/`, `manifest/`, `downloader/`):

- `doh.js` -- DNS-over-HTTPS transport (Cloudflare JSON API).
- `base32.js`, `hashing.js`, `aead.js`, `txtPacking.js`, `manifest.js`, `encoding.js` --
  pure functions, no network or DOM. Port `core/hashing.py`, `core/crypto.py`,
  `zonegen/txt_packing.py`, `manifest/serialization.py`, `core/encoding.py`.
- `download.js` -- orchestration (`downloadFromDns`), mirroring
  `downloader/pipeline.py::download_from_store` but with concurrent (not sequential)
  content-chunk fetching.
- `preview.js`, `main.js`, `index.html`, `styles.css` -- DOM-facing UI.

## Automated tests

`node --test` (Node's built-in test runner, zero dependencies) from this directory.
Covers all the pure functions above, including cross-checks against real vectors
produced by the actual Python functions (`webapp/tests/fixtures.json`) -- catches a
byte-layout or endianness mismatch directly, not just internal self-consistency.

```
cd webapp
node --test
```

## Manual verification checklist

No local-DNS equivalent exists for DNS-over-HTTPS, so this has to run against the real
live `dnsfileshare.com` deployment, not a local fixture.

### File-size matrix

Deliberately crosses two independent boundaries: whether a chunk's base64 payload needs
more than one RFC 1035 character-string (`TXT_STRING_MAX_LEN=255`,
`zonegen/constants.py`), and whether the file needs more than one content chunk
(`CHUNK_SIZE=1200`, `core/constants.py`). AES-GCM adds a 16-byte tag, so
`ciphertext_len = plaintext_len + 16`.

| Tier | Plaintext size | Ciphertext | Chunks | TXT strings/chunk | What it proves |
|---|---|---|---|---|---|
| Small | ~50 bytes | ~66 bytes | 1 | 1 (base64 ~88 chars) | Baseline, no packing/ordering complexity |
| Medium | ~800 bytes | ~816 bytes | 1 | 5 (base64 ~1088 chars) | Multi-string TXT reassembly within one record |
| Large | **2384 bytes exactly** | **2400 bytes exactly** | **2** (both full, no padding) | 7 each (base64 exactly 1600 chars) | Multi-chunk ordering/joining across separate DNS records |

The large tier's `2384`/`2400`-byte literal isn't arbitrary -- it's the same exact
boundary already validated against the Python round-trip suite for "2 full chunks, no
padding," reused here so this check lines up with an already-proven-correct case.

For `.txt`, hit these plaintext sizes exactly (generate a file of that many bytes). For
`.png`, exact byte counts aren't practical (real image structure) -- aim for
comfortably-within-tier real images instead (a 1-pixel PNG for small, a small icon for
medium, a small photo/screenshot a few KB to ~10KB for large). Confirm the actual byte
size with `ls -l` once chosen and fill in the table below:

| File | Bytes (actual) | pointer_hash | key (base64) |
|---|---|---|---|
| small.txt | | | |
| medium.txt | | | |
| large.txt | | | |
| small.png | | | |
| medium.png | | | |
| large.png | | | |

Publish all six via `deploy.cli publish`:
```
python -m deploy.cli publish path/to/small.txt --name small.txt
```

### Checklist

- **V1.** Serve the webapp locally: `python -m http.server` from this directory, open
  `http://localhost:8000`.
- **V2.** For each of the six files above: enter its `pointer_hash` + key, confirm
  correct preview rendering (text in a `<pre>`, image via `<img>`), and that the
  download button produces a byte-identical file (`diff` or checksum against the
  original).
- **V3.** Specifically for the medium/large tiers: verify the reassembled *content* is
  actually correct, not just that it rendered without erroring -- a multi-string or
  multi-chunk reassembly bug could produce corrupted-but-still-decryptable-looking
  output for text, or a visibly-broken image for a PNG, that a shallow "did it render"
  check would miss.
- **V4.** Open browser devtools' Network tab while downloading the large tier; confirm
  chunk requests are genuinely concurrent (overlapping), not sequential one-at-a-time.
- **V5.** Enter a correct `pointer_hash` with a wrong key -- confirm the
  decrypt-failure message, not a silent wrong result.
- **V6.** Enter a `pointer_hash` that was never published -- confirm the not-found
  message.
- **V7.** Publish and try a file with an unrecognized extension (e.g. `.bin`) -- confirm
  it falls back to download-only with no preview attempted, and the downloaded bytes
  are still correct.
- **V8.** Repeat V1-V2 once deployed to GitHub Pages, against the real public URL (not
  just `localhost`) -- confirms CORS against Cloudflare's DoH endpoint actually works
  from a real deployed origin, which some CORS configurations treat differently than
  `localhost`.

## Hosting (GitHub Pages)

The repo must be public for free GitHub Pages (already confirmed safe -- no secrets are
committed anywhere in git history). To enable:

1. Flip repo visibility to public (GitHub Settings -> Danger Zone, or
   `gh repo edit <owner>/<repo> --visibility public`) -- a real, not-fully-reversible
   action (anyone who clones/crawls while public keeps a copy regardless of later
   re-privating). Confirm before doing this.
2. GitHub Settings -> Pages -> Deploy from a branch -> select `main`, folder `/webapp`
   (or configure a GitHub Actions deploy step if `/webapp` as a Pages source folder
   isn't supported for your repo layout -- check current GitHub Pages docs, since this
   has changed over time).
3. Confirm the deployed URL loads `index.html` and completes checklist V8 above.
