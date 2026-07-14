import pytest

from deploy.config import DeployConfig
from deploy.exceptions import DeployError


def _set_required(monkeypatch):
    monkeypatch.setenv("DNSSTORE_ORIGIN", "dnsfileshare.com.")
    monkeypatch.setenv("DNSSTORE_VPS_IP", "203.0.113.10")
    monkeypatch.setenv("DNSSTORE_TSIG_SECRET", "c2VjcmV0Cg==")


def test_from_env_reads_required_vars(monkeypatch):
    _set_required(monkeypatch)

    config = DeployConfig.from_env()

    assert config.origin == "dnsfileshare.com."
    assert config.vps_ip == "203.0.113.10"
    assert config.tsig_secret == "c2VjcmV0Cg=="


def test_from_env_defaults(monkeypatch):
    _set_required(monkeypatch)
    for name in ("DNSSTORE_SSH_HOST", "DNSSTORE_SSH_USER", "DNSSTORE_SSH_PORT", "DNSSTORE_TSIG_KEY_NAME"):
        monkeypatch.delenv(name, raising=False)

    config = DeployConfig.from_env()

    assert config.ssh_host == "203.0.113.10"  # defaults to vps_ip
    assert config.ssh_user == "deploy"
    assert config.ssh_port == 22
    assert config.tsig_key_name == "update-key"
    assert config.remote_zone_path == "/var/lib/bind/dnsfileshare.com.zone"


def test_from_env_overrides(monkeypatch):
    _set_required(monkeypatch)
    monkeypatch.setenv("DNSSTORE_SSH_HOST", "bastion.example.com")
    monkeypatch.setenv("DNSSTORE_SSH_USER", "operator")
    monkeypatch.setenv("DNSSTORE_SSH_PORT", "2222")

    config = DeployConfig.from_env()

    assert config.ssh_host == "bastion.example.com"
    assert config.ssh_user == "operator"
    assert config.ssh_port == 2222


@pytest.mark.parametrize("missing", ["DNSSTORE_ORIGIN", "DNSSTORE_VPS_IP", "DNSSTORE_TSIG_SECRET"])
def test_from_env_missing_required_var_raises(monkeypatch, missing):
    _set_required(monkeypatch)
    monkeypatch.delenv(missing)

    with pytest.raises(DeployError):
        DeployConfig.from_env()
