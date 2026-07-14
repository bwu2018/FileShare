import os
from dataclasses import dataclass

from .constants import DEFAULT_SSH_PORT, TSIG_KEY_NAME
from .exceptions import DeployError

_REQUIRED_VARS = ("DNSSTORE_ORIGIN", "DNSSTORE_VPS_IP", "DNSSTORE_TSIG_SECRET")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise DeployError(f"required environment variable {name} is not set")
    return value


@dataclass(frozen=True)
class DeployConfig:
    origin: str
    vps_ip: str
    tsig_secret: str
    tsig_key_name: str = TSIG_KEY_NAME
    ssh_host: str = ""
    ssh_user: str = "deploy"
    ssh_port: int = DEFAULT_SSH_PORT
    remote_zone_path: str = ""
    local_zone_path: str = ""

    @classmethod
    def from_env(cls) -> "DeployConfig":
        origin = _require_env("DNSSTORE_ORIGIN")
        vps_ip = _require_env("DNSSTORE_VPS_IP")
        tsig_secret = _require_env("DNSSTORE_TSIG_SECRET")
        bare_origin = origin.rstrip(".")

        return cls(
            origin=origin,
            vps_ip=vps_ip,
            tsig_secret=tsig_secret,
            tsig_key_name=os.environ.get("DNSSTORE_TSIG_KEY_NAME", TSIG_KEY_NAME),
            ssh_host=os.environ.get("DNSSTORE_SSH_HOST", vps_ip),
            ssh_user=os.environ.get("DNSSTORE_SSH_USER", "deploy"),
            ssh_port=int(os.environ.get("DNSSTORE_SSH_PORT", DEFAULT_SSH_PORT)),
            remote_zone_path=os.environ.get(
                "DNSSTORE_REMOTE_ZONE_PATH", f"/var/lib/bind/{bare_origin}.zone"
            ),
            local_zone_path=os.environ.get(
                "DNSSTORE_LOCAL_ZONE_PATH", f"/tmp/{bare_origin}.zone"
            ),
        )
