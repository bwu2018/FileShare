from typing import Iterator

import dns.name
import dns.query
import dns.rcode
import dns.rdatatype
import dns.rrset
import dns.tsig
import dns.tsigkeyring
import dns.update

from zonegen import chunk_owner_name

from .constants import DNS_UPDATE_BATCH_SIZE, DNS_UPDATE_TIMEOUT_SECONDS
from .exceptions import DeployError


def build_update(
    origin: str, rrsets: list[dns.rrset.RRset], tsig_key_name: str, tsig_secret: str
) -> dns.update.UpdateMessage:
    keyring = dns.tsigkeyring.from_text({tsig_key_name: tsig_secret})
    update = dns.update.Update(
        origin,
        keyring=keyring,
        keyname=dns.name.from_text(tsig_key_name),
        keyalgorithm=dns.tsig.HMAC_SHA256,
    )
    for rrset in rrsets:
        update.add(rrset.name, rrset)
    return update


def build_update_batches(
    origin: str,
    rrsets: list[dns.rrset.RRset],
    tsig_key_name: str,
    tsig_secret: str,
    batch_size: int = DNS_UPDATE_BATCH_SIZE,
) -> Iterator[dns.update.UpdateMessage]:
    for i in range(0, len(rrsets), batch_size):
        yield build_update(origin, rrsets[i : i + batch_size], tsig_key_name, tsig_secret)


def build_delete_update(
    origin: str, addresses: list[str], tsig_key_name: str, tsig_secret: str
) -> dns.update.UpdateMessage:
    keyring = dns.tsigkeyring.from_text({tsig_key_name: tsig_secret})
    update = dns.update.Update(
        origin,
        keyring=keyring,
        keyname=dns.name.from_text(tsig_key_name),
        keyalgorithm=dns.tsig.HMAC_SHA256,
    )
    for address in addresses:
        update.delete(chunk_owner_name(address, origin), dns.rdatatype.TXT)
    return update


def build_delete_update_batches(
    origin: str,
    addresses: list[str],
    tsig_key_name: str,
    tsig_secret: str,
    batch_size: int = DNS_UPDATE_BATCH_SIZE,
) -> Iterator[dns.update.UpdateMessage]:
    for i in range(0, len(addresses), batch_size):
        yield build_delete_update(origin, addresses[i : i + batch_size], tsig_key_name, tsig_secret)


def _send(update: dns.update.UpdateMessage, vps_ip: str, port: int) -> None:
    try:
        response = dns.query.tcp(update, vps_ip, port=port, timeout=DNS_UPDATE_TIMEOUT_SECONDS)
    except (dns.tsig.PeerError, dns.tsig.BadSignature, dns.tsig.BadKey, dns.tsig.BadAlgorithm) as exc:
        # A wrong secret/key/algorithm raises here directly, before there's a response
        # message to check an rcode on at all -- confirmed live (a bad secret raises
        # dns.tsig.PeerBadSignature, not a NOTAUTH-rcode response). Distinct from raw
        # transport failures (timeout, connection refused), which propagate unwrapped.
        raise DeployError(f"dynamic update rejected: TSIG error ({exc})") from exc

    if response.rcode() != dns.rcode.NOERROR:
        raise DeployError(f"dynamic update rejected: rcode={dns.rcode.to_text(response.rcode())}")


def send_update(
    origin: str,
    rrsets: list[dns.rrset.RRset],
    vps_ip: str,
    tsig_key_name: str,
    tsig_secret: str,
    port: int = 53,
    batch_size: int = DNS_UPDATE_BATCH_SIZE,
) -> None:
    for update in build_update_batches(origin, rrsets, tsig_key_name, tsig_secret, batch_size):
        _send(update, vps_ip, port)


def send_delete(
    origin: str,
    addresses: list[str],
    vps_ip: str,
    tsig_key_name: str,
    tsig_secret: str,
    port: int = 53,
    batch_size: int = DNS_UPDATE_BATCH_SIZE,
) -> None:
    for update in build_delete_update_batches(origin, addresses, tsig_key_name, tsig_secret, batch_size):
        _send(update, vps_ip, port)
