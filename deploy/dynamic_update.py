import dns.name
import dns.query
import dns.rcode
import dns.rrset
import dns.tsig
import dns.tsigkeyring
import dns.update

from .constants import DNS_UPDATE_TIMEOUT_SECONDS
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


def send_update(
    origin: str,
    rrsets: list[dns.rrset.RRset],
    vps_ip: str,
    tsig_key_name: str,
    tsig_secret: str,
    port: int = 53,
) -> None:
    update = build_update(origin, rrsets, tsig_key_name, tsig_secret)
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
