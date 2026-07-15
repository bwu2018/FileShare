# backend

The only piece of this project that ever writes to DNS on behalf of a browser. It
exists solely because the RFC 2136 TSIG secret (`DNSSTORE_TSIG_SECRET`) that
authenticates DNS writes can never be shipped to client-side JS -- the browser does
all encryption/chunking/hashing itself (`webapp/upload.js`) and POSTs only already-
encrypted `(hash, payload)` pairs here; this service never sees plaintext or the
decryption key, only ciphertext it relays into DNS.

## Endpoint

```
POST /api/v1/publish
Content-Type: application/json

{"records": [{"hash": "...", "payload": "base64..."}, ...]}
```

One request = one batch (capped at `MAX_RECORDS_PER_REQUEST`, see `constants.py` --
tied directly to the 65,535-byte RFC 2136 UPDATE message ceiling, not an arbitrary
number). The manifest record is just one more entry in the array; this service never
needs to know which uploaded hash "is" the manifest. A file needing more chunks than
fit in one batch means the browser sends multiple sequential requests --
`webapp/upload.js` handles this, not this service.

Response: `{"status": "ok", "record_count": N}` on success. See `app.py`'s route for
the full error/status-code mapping (400/401/422/429/502).

## Reused, unmodified

`deploy.config.DeployConfig`, `deploy.dynamic_update.send_update`,
`deploy.exceptions.DeployError`, `zonegen.records.format_txt_record`,
`zonegen.exceptions.ZoneGenerationError`. This package is purely the HTTP layer,
request validation, and rate limiting around that existing DNS-write pipeline -- see
`deploy/README.md` for how the underlying dynamic update itself works.

## Configuration

Same env vars as `deploy.cli` (`deploy/README.md`'s "Configuration" section):
`DNSSTORE_ORIGIN`, `DNSSTORE_VPS_IP`, `DNSSTORE_TSIG_SECRET`, plus the optional
`DNSSTORE_TSIG_KEY_NAME`. The SSH/bootstrap-only fields aren't used by this service.

## Running

Development:
```
export FLASK_APP=backend.wsgi:app
source ~/.config/dnsfileshare/deploy.env
.venv/bin/flask run
```

Production (behind Caddy, see `deploy/vps_config/Caddyfile`):
```
gunicorn --workers 1 --bind 127.0.0.1:8000 backend.wsgi:app
```

**Must run as a single worker (`--workers 1`).** `ratelimit.py`'s `RateLimiter` is an
in-memory, per-process counter -- multiple gunicorn workers would each keep their own
independent counts, silently multiplying the effective rate limit by the worker
count. This is an accepted tradeoff for a personal-scale tool with modest traffic;
revisit if real concurrent load ever shows up (a shared store like Redis would be the
fix, not more workers).

The provided systemd unit (`deploy/vps_config/dnsfileshare-backend.service.template`)
already pins this.

## Auth

Fully open in v1 -- no token or login is required to publish. `auth.py::check_auth`
is an isolated hook, currently a no-op, so a real check (e.g. a bearer token or OAuth)
can be added later without changing `app.py`'s request-handling flow. Given there is
no delete/expiry mechanism anywhere in this project, an open write endpoint means
anyone with the URL can add permanent records -- acceptable for now since this is a
personal tool, not something to forget about if this ever gets meaningfully shared.

## Abuse protection (no auth today, so this carries real weight)

- Per-record payload cap (`MAX_PAYLOAD_BYTES`) and per-request batch cap
  (`MAX_RECORDS_PER_REQUEST`), enforced in `validation.py` before anything touches
  `format_txt_record`/DNS.
- `MAX_CONTENT_LENGTH` on the Flask app bounds request-body parsing memory.
- Simple per-IP rate limiting (`ratelimit.py`), see the single-worker caveat above.

## Failure recovery

Because chunk addresses are `hash(nonce + index)` and re-sending an identical batch
is a no-op DNS overwrite (not a duplicate), the recovery story for any failed
request -- validation error aside -- is simply "the browser retries the whole
upload." No server-side partial-completion tracking exists or is needed.
