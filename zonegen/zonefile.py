import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.rdtypes.ANY.NS
import dns.rdtypes.ANY.SOA
import dns.rdtypes.IN.A
import dns.rrset
import dns.zone

from core.store import ChunkStore

from .constants import (
    DEFAULT_ADMIN_LABEL,
    DEFAULT_EXPIRE,
    DEFAULT_MINIMUM,
    DEFAULT_NS_LABEL,
    DEFAULT_REFRESH,
    DEFAULT_RETRY,
    RECORD_TTL,
)
from .records import format_txt_record


def nameserver_fqdn(origin: str) -> str:
    return f"{DEFAULT_NS_LABEL}.{origin}"


def admin_email_fqdn(origin: str) -> str:
    return f"{DEFAULT_ADMIN_LABEL}.{origin}"


def _add_rrset(zone: dns.zone.Zone, rrset: dns.rrset.RRset) -> None:
    zone.find_rdataset(rrset.name, rrset.rdtype, create=True).update(rrset)


def build_zone(
    origin: str,
    serial: int,
    refresh: int = DEFAULT_REFRESH,
    retry: int = DEFAULT_RETRY,
    expire: int = DEFAULT_EXPIRE,
    minimum: int = DEFAULT_MINIMUM,
    ns_ip: str = "127.0.0.1",
    web_ip: str | None = None,
) -> dns.zone.Zone:
    # web_ip defaults to ns_ip: the webapp/backend are hosted on the same VPS as BIND
    # (see deploy/vps_config/Caddyfile), so the apex `A` record and the `ns1` glue
    # record point at the same address today. Kept as a separate parameter (not just
    # reusing ns_ip inline) so a future split onto a different host is a one-line
    # change here, not a rename.
    if web_ip is None:
        web_ip = ns_ip

    origin_name = dns.name.from_text(origin)
    zone = dns.zone.Zone(origin=origin_name)

    root_name = dns.name.from_text("@", origin=origin_name)
    ns_name = dns.name.from_text(DEFAULT_NS_LABEL, origin=origin_name)
    mname = dns.name.from_text(nameserver_fqdn(origin))
    rname = dns.name.from_text(admin_email_fqdn(origin))

    soa_rdata = dns.rdtypes.ANY.SOA.SOA(
        dns.rdataclass.IN,
        dns.rdatatype.SOA,
        mname,
        rname,
        serial,
        refresh,
        retry,
        expire,
        minimum,
    )
    ns_rdata = dns.rdtypes.ANY.NS.NS(dns.rdataclass.IN, dns.rdatatype.NS, mname)
    glue_a_rdata = dns.rdtypes.IN.A.A(dns.rdataclass.IN, dns.rdatatype.A, ns_ip)
    apex_a_rdata = dns.rdtypes.IN.A.A(dns.rdataclass.IN, dns.rdatatype.A, web_ip)

    _add_rrset(zone, dns.rrset.from_rdata(root_name, RECORD_TTL, soa_rdata))
    _add_rrset(zone, dns.rrset.from_rdata(root_name, RECORD_TTL, ns_rdata))
    _add_rrset(zone, dns.rrset.from_rdata(root_name, RECORD_TTL, apex_a_rdata))
    _add_rrset(zone, dns.rrset.from_rdata(ns_name, RECORD_TTL, glue_a_rdata))
    return zone


def generate_zone_file(store: ChunkStore, zone: dns.zone.Zone) -> str:
    origin = str(zone.origin)
    for chunk_hash, encoded_chunk in sorted(store.items()):
        _add_rrset(zone, format_txt_record(chunk_hash, encoded_chunk, origin))

    # sorted=False: preserve insertion order (header block, then hash-sorted records)
    # rather than dnspython's own DNSSEC canonical name order, which would interleave
    # the ns1 glue record among the TXT records.
    return zone.to_text(want_origin=True, relativize=True, sorted=False)
