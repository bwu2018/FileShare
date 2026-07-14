from pathlib import Path

from core import crypto
from core.store import ChunkStore
from manifest.pipeline import create_manifest
from zonegen.records import format_txt_record

from .config import DeployConfig
from .dynamic_update import send_update


def publish_file(path: Path, file_name: str, config: DeployConfig) -> tuple[str, bytes]:
    store = ChunkStore()
    key = crypto.generate_key()
    plaintext = path.read_bytes()

    pointer_hash = create_manifest(plaintext, key, file_name, store)

    rrsets = [format_txt_record(chunk_hash, payload, config.origin) for chunk_hash, payload in store.items()]
    send_update(config.origin, rrsets, config.vps_ip, config.tsig_key_name, config.tsig_secret)

    return pointer_hash, key
