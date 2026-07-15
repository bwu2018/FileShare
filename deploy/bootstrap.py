import time
from pathlib import Path

from core.store import ChunkStore
from zonegen.zonefile import build_zone, generate_zone_file

from . import remote
from .config import DeployConfig


def bootstrap_zone(config: DeployConfig) -> None:
    zone = build_zone(
        origin=config.origin, serial=int(time.time()), ns_ip=config.vps_ip
    )
    zone_text = generate_zone_file(ChunkStore(), zone)

    local_path = Path(config.local_zone_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(zone_text)

    remote.push_zone_file(
        local_path,
        config.ssh_host,
        config.ssh_user,
        config.remote_zone_path,
        config.ssh_port,
    )
    remote.restart_remote_bind(config.ssh_host, config.ssh_user, config.ssh_port)
    remote.check_remote_zone_ok(config.vps_ip, config.origin)
