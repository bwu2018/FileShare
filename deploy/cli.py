import argparse
import base64
from pathlib import Path

from downloader.pipeline import download_from_dns

from .bootstrap import bootstrap_zone
from .config import DeployConfig
from .delete import delete_file
from .publish import publish_file


def _cmd_bootstrap(_args: argparse.Namespace) -> None:
    config = DeployConfig.from_env()
    bootstrap_zone(config)
    print(f"bootstrapped zone {config.origin} on {config.vps_ip}")


def _cmd_publish(args: argparse.Namespace) -> None:
    config = DeployConfig.from_env()
    path = Path(args.path)
    file_name = args.name or path.name

    pointer_hash, key = publish_file(path, file_name, config)

    print(f"pointer_hash: {pointer_hash}")
    print(f"key (base64): {base64.b64encode(key).decode('ascii')}")
    print("save this now -- nothing else stores it")


def _cmd_delete(args: argparse.Namespace) -> None:
    config = DeployConfig.from_env()
    key = base64.b64decode(args.key)

    count = delete_file(args.pointer_hash, key, config)
    print(f"deleted {count} records")


def _cmd_verify(args: argparse.Namespace) -> None:
    config = DeployConfig.from_env()
    key = base64.b64decode(args.key)
    resolver_ip = args.resolver_ip or config.vps_ip

    file_name, plaintext = download_from_dns(config.origin, args.pointer_hash, key, resolver_ip)
    print(f"OK: recovered {file_name!r} ({len(plaintext)} bytes)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deploy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap").set_defaults(func=_cmd_bootstrap)

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("path")
    publish_parser.add_argument("--name", default=None)
    publish_parser.set_defaults(func=_cmd_publish)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("pointer_hash")
    verify_parser.add_argument("key")
    verify_parser.add_argument("--resolver-ip", default=None)
    verify_parser.set_defaults(func=_cmd_verify)

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("pointer_hash")
    delete_parser.add_argument("key")
    delete_parser.set_defaults(func=_cmd_delete)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
