import subprocess
from pathlib import Path

import dns.message
import dns.query
import dns.rcode
import dns.rdatatype

from .constants import DNS_QUERY_TIMEOUT_SECONDS
from .exceptions import DeployError


def push_zone_file(local_path: Path, host: str, user: str, remote_path: str, port: int) -> None:
    subprocess.run(
        ["rsync", "-az", "-e", f"ssh -p {port}", str(local_path), f"{user}@{host}:{remote_path}"],
        check=True,
    )


def restart_remote_bind(host: str, user: str, port: int) -> None:
    # Not `rndc reload` -- confirmed live against a real dynamic zone (allow-update
    # configured) that BIND refuses it outright ("rndc: 'reload' failed: dynamic zone"),
    # to protect the journal's consistency. A full restart re-reads the on-disk zone
    # file cleanly regardless of dynamic status, and is fine here since this only ever
    # runs once, before the zone has received real traffic -- unlike a routine reload,
    # a one-time bootstrap's brief full outage is a non-issue.
    subprocess.run(
        ["ssh", "-p", str(port), f"{user}@{host}", "sudo", "systemctl", "restart", "bind9"],
        check=True,
    )


def check_remote_zone_ok(host: str, zone_name: str) -> None:
    # Queries the zone directly over DNS rather than parsing `rndc status` text --
    # a real confirmation that the reload actually took effect, not just that the
    # rndc command itself exited zero (rndc can accept a reload it then fails to apply).
    query = dns.message.make_query(zone_name, dns.rdatatype.SOA)
    response = dns.query.udp(query, host, timeout=DNS_QUERY_TIMEOUT_SECONDS)
    if response.rcode() != dns.rcode.NOERROR or not response.answer:
        raise DeployError(
            f"zone {zone_name} did not answer correctly after reload: "
            f"rcode={dns.rcode.to_text(response.rcode())}"
        )
