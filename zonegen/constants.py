TXT_STRING_MAX_LEN = 255  # RFC 1035 character-string max length per quoted piece

CHUNKS_LABEL = "chunks"  # owner name suffix: "<hash>.chunks"

RECORD_TTL = 604800  # 1 week; content is immutable (content-addressed), long TTL is safe

DEFAULT_NS_LABEL = "ns1"
DEFAULT_ADMIN_LABEL = "admin"
DEFAULT_REFRESH = 3600
DEFAULT_RETRY = 900
DEFAULT_EXPIRE = 604800
DEFAULT_MINIMUM = 3600
