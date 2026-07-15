// Must stay in sync with zonegen/constants.py::CHUNKS_LABEL -- not re-derived, just
// mirrored, since this webapp has no way to import Python source directly.
export const CHUNKS_LABEL = 'chunks';

export const DEFAULT_RESOLVER_URL = 'https://cloudflare-dns.com/dns-query';

// Bounded concurrency for content-chunk fetches. Each fetch is a full HTTPS DoH round
// trip, so sequential fetching (as the Python reference implementation does over raw
// UDP) would be far too slow in a browser -- not tuned precisely, just a reasonable
// default.
export const DEFAULT_CONCURRENCY = 20;

// Mirrors core/constants.py -- must stay in sync, no way to import Python source
// directly.
export const CHUNK_SIZE = 1200;
export const KEY_SIZE = 32;
export const NONCE_SIZE = 12;

// Relative so it resolves against whatever origin actually serves this page (Caddy
// reverse-proxies /api/* to the backend under the same origin in production; also
// works unmodified when serving webapp/ locally against a local backend for testing).
export const DEFAULT_PUBLISH_URL = '/api/v1/publish';

// Must match backend.constants.MAX_RECORDS_PER_REQUEST -- both sides independently
// enforce it (this bounds requests the browser sends; the backend bounds what it will
// accept), tied to the 65,535-byte RFC 2136 UPDATE message ceiling. Not re-derived
// automatically since the two sides can't share a single source of truth across
// Python/JS -- keep in sync by hand if either changes.
export const UPLOAD_BATCH_SIZE = 25;
