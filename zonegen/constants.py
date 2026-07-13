TXT_STRING_MAX_LEN = 255  # RFC 1035 character-string max length per quoted piece

# DNS RDATA is a 16-bit length field (RFC 1035 4.1.3) -- a TXT record's total wire size
# (sum of each packed character-string's 1-byte length prefix + its bytes) can never
# exceed this, regardless of how many character-strings it's split across.
MAX_TXT_RDATA_SIZE = 65535

CHUNKS_LABEL = "chunks"  # owner name suffix: "<hash>.chunks"

RECORD_TTL = 604800  # 1 week; content is immutable (content-addressed), long TTL is safe

DEFAULT_NS_LABEL = "ns1"
DEFAULT_ADMIN_LABEL = "admin"
DEFAULT_REFRESH = 3600
DEFAULT_RETRY = 900
DEFAULT_EXPIRE = 604800
DEFAULT_MINIMUM = 3600
