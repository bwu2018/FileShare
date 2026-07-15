import time

import dns.exception
import dns.flags
import dns.message
import dns.query
import dns.rcode
import dns.rdatatype

from core.exceptions import ChunkNotFoundError, DnsStoreError
from zonegen.constants import CHUNKS_LABEL
from zonegen.txt_packing import unpack_txt_strings

from .constants import (
    DEFAULT_RESOLVER_PORT,
    DNS_QUERY_MAX_ATTEMPTS,
    DNS_QUERY_RETRY_BACKOFF_SECONDS,
    DNS_QUERY_TIMEOUT_SECONDS,
)


class DnsChunkStore:
    """Read-only ChunkStore-shaped adapter backed by a live DNS server.

    Only implements get() -- that's all core.pipeline.load_plaintext /
    manifest.fetch_manifest need to walk the manifest -> content chunks entirely
    through DNS-served records.
    """

    def __init__(self, origin: str, resolver_ip: str, resolver_port: int = DEFAULT_RESOLVER_PORT) -> None:
        self.origin = origin if origin.endswith(".") else f"{origin}."
        self.resolver_ip = resolver_ip
        self.resolver_port = resolver_port

    def _query_once(self, qname: str) -> dns.message.Message:
        query = dns.message.make_query(qname, dns.rdatatype.TXT)
        response = dns.query.udp(
            query, self.resolver_ip, port=self.resolver_port, timeout=DNS_QUERY_TIMEOUT_SECONDS
        )
        if response.flags & dns.flags.TC:
            response = dns.query.tcp(
                query, self.resolver_ip, port=self.resolver_port, timeout=DNS_QUERY_TIMEOUT_SECONDS
            )
        return response

    def get(self, chunk_hash: str) -> str:
        qname = f"{chunk_hash}.{CHUNKS_LABEL}.{self.origin}"

        for attempt in range(1, DNS_QUERY_MAX_ATTEMPTS + 1):
            try:
                response = self._query_once(qname)
                break
            except dns.exception.Timeout:
                if attempt == DNS_QUERY_MAX_ATTEMPTS:
                    raise
                time.sleep(DNS_QUERY_RETRY_BACKOFF_SECONDS * attempt)

        if response.rcode() not in (dns.rcode.NOERROR, dns.rcode.NXDOMAIN):
            raise DnsStoreError(f"DNS query for {qname} failed: rcode={dns.rcode.to_text(response.rcode())}")

        if not response.answer:
            raise ChunkNotFoundError(chunk_hash)

        strings = [s.decode("ascii") for s in response.answer[0][0].strings]
        return unpack_txt_strings(strings)
