INDEX_NODE_SIZE = 8192  # index-node byte budget; independent of core.constants.CHUNK_SIZE
HASH_STRING_LEN = 56    # base32(SHA-256 digest), fixed width: ceil(32/5)=7 groups * 8 chars/group
INDEX_HEADER_SIZE = 5   # 1 byte is_leaf flag + 4 byte uint32 count

MAX_HASHES_PER_NODE = (INDEX_NODE_SIZE - INDEX_HEADER_SIZE) // HASH_STRING_LEN  # 146

MANIFEST_VERSION = 1
MANIFEST_HEADER_SIZE = 81  # version(1) + file_size(8) + chunk_count(4) + content_nonce(12) + root_hash(56)
