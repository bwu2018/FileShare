from downloader.constants import DEFAULT_RESOLVER_PORT
from downloader.dns_store import DnsChunkStore
from manifest import list_stored_addresses

from .config import DeployConfig
from .dynamic_update import send_delete


def delete_file(pointer_hash: str, key: bytes, config: DeployConfig) -> int:
    store = DnsChunkStore(config.origin, config.vps_ip, DEFAULT_RESOLVER_PORT)
    addresses = list_stored_addresses(pointer_hash, key, store)
    send_delete(config.origin, addresses, config.vps_ip, config.tsig_key_name, config.tsig_secret)
    return len(addresses)
