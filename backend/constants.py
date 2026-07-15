# Caps each POST /api/v1/publish request to roughly 20-25 records' worth of RRsets,
# which keeps one send_update() call safely under the 65,535-byte DNS UPDATE
# message ceiling (dns.query.tcp's 2-byte length prefix) with margin for name/RR
# framing overhead. A file needing more chunks means the browser sends multiple
# sequential requests -- see webapp/upload.js.
MAX_RECORDS_PER_REQUEST = 25

# Comfortably covers CHUNK_SIZE=1200 (core/constants.py) plus manifest overhead,
# checked against the *decoded* payload, before it ever reaches format_txt_record.
MAX_PAYLOAD_BYTES = 4096

# Flask's own request-body cap, sized to MAX_RECORDS_PER_REQUEST * (base64 blowup of
# MAX_PAYLOAD_BYTES + hash + JSON syntax), with headroom.
MAX_CONTENT_LENGTH = 300_000

# Simple per-IP fixed-window-ish rate limit (see ratelimit.py) -- there is no auth in
# v1, so this is the only abuse protection against a public write endpoint that
# performs permanent, delete-less DNS writes.
RATE_LIMIT_MAX_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60.0
