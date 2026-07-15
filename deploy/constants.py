DEFAULT_SSH_PORT = 22
DNS_UPDATE_TIMEOUT_SECONDS = 5
DNS_QUERY_TIMEOUT_SECONDS = 5
TSIG_KEY_NAME = "update-key"

# Caps each RFC 2136 UPDATE message to this many rrsets/deletes, keeping it safely
# under the 65,535-byte ceiling (dns.query.tcp's 2-byte length prefix) with margin
# for name/RR framing overhead. Mirrors backend.constants.MAX_RECORDS_PER_REQUEST,
# which enforces the same ceiling on the browser/backend upload path.
DNS_UPDATE_BATCH_SIZE = 25
