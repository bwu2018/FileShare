class DnsStoreError(Exception):
    pass


class ChunkNotFoundError(DnsStoreError):
    pass


class ChunkHashMismatchError(DnsStoreError):
    pass


class DecryptionError(DnsStoreError):
    pass
