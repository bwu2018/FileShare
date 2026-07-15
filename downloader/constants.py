DEFAULT_RESOLVER_PORT = 53
DNS_QUERY_TIMEOUT_SECONDS = 5

# A query can time out transiently (e.g. a dropped UDP response, or the authoritative
# server's own Response Rate Limiting reacting to many rapid sequential chunk queries
# from one client -- confirmed live against the real production BIND deployment, which
# has RRL enabled). Retry with a short backoff rather than failing the whole download
# on one dropped response.
DNS_QUERY_MAX_ATTEMPTS = 4
DNS_QUERY_RETRY_BACKOFF_SECONDS = 1.0
