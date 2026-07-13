import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.rdtypes.ANY.TXT
import dns.rrset

from .constants import CHUNKS_LABEL, RECORD_TTL
from .exceptions import ZoneGenerationError
from .txt_packing import pack_txt_strings


def format_txt_record(chunk_hash: str, encoded_chunk: str, origin: str) -> dns.rrset.RRset:
    # Turns a single (chunk_hash, encoded_chunk) pair from the ChunkStore into one TXT resource record
    owner = f"{chunk_hash}.{CHUNKS_LABEL}"
    try:
        origin_name = dns.name.from_text(origin)
        owner_name = dns.name.from_text(owner, origin=origin_name)
    except (dns.name.LabelTooLong, dns.name.NameTooLong) as e:
        raise ZoneGenerationError(f"invalid name {owner}.{origin}: {e}") from e

    txt_rdata = dns.rdtypes.ANY.TXT.TXT(dns.rdataclass.IN, dns.rdatatype.TXT, pack_txt_strings(encoded_chunk))
    return dns.rrset.from_rdata(owner_name, RECORD_TTL, txt_rdata)
