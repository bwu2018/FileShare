// Must stay in sync with zonegen/constants.py::CHUNKS_LABEL -- not re-derived, just
// mirrored, since this webapp has no way to import Python source directly.
export const CHUNKS_LABEL = 'chunks';

export const DEFAULT_RESOLVER_URL = 'https://cloudflare-dns.com/dns-query';

// Bounded concurrency for content-chunk fetches. Each fetch is a full HTTPS DoH round
// trip, so sequential fetching (as the Python reference implementation does over raw
// UDP) would be far too slow in a browser -- not tuned precisely, just a reasonable
// default.
export const DEFAULT_CONCURRENCY = 20;
