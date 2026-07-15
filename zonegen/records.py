import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.rdtypes.ANY.TXT
import dns.rrset

from .constants import CHUNKS_LABEL, MAX_TXT_RDATA_SIZE, RECORD_TTL
from .exceptions import ZoneGenerationError
from .txt_packing import pack_txt_strings


def chunk_owner_name(chunk_hash: str, origin: str) -> dns.name.Name:
    # The DNS owner name a chunk's TXT record (or its delete counterpart) lives at.
    owner = f"{chunk_hash}.{CHUNKS_LABEL}"
    try:
        origin_name = dns.name.from_text(origin)
        return dns.name.from_text(owner, origin=origin_name)
    except (dns.name.LabelTooLong, dns.name.NameTooLong) as e:
        raise ZoneGenerationError(f"invalid name {owner}.{origin}: {e}") from e


def format_txt_record(chunk_hash: str, encoded_chunk: str, origin: str) -> dns.rrset.RRset:
    # Turns a single (chunk_hash, encoded_chunk) pair from the ChunkStore into one TXT resource record
    owner_name = chunk_owner_name(chunk_hash, origin)

    strings = pack_txt_strings(encoded_chunk)
    wire_size = sum(1 + len(s) for s in strings)
    if wire_size > MAX_TXT_RDATA_SIZE:
        raise ZoneGenerationError(
            f"TXT record for {owner_name} has {wire_size}-byte RDATA, "
            f"exceeds the {MAX_TXT_RDATA_SIZE}-byte DNS protocol maximum"
        )

    txt_rdata = dns.rdtypes.ANY.TXT.TXT(dns.rdataclass.IN, dns.rdatatype.TXT, strings)
    return dns.rrset.from_rdata(owner_name, RECORD_TTL, txt_rdata)
