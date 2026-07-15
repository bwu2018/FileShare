import base64
import os

import dns.name

from backend.app import create_app
from backend.constants import MAX_RECORDS_PER_REQUEST
from core import crypto
from core.store import ChunkStore
from deploy.config import DeployConfig
from deploy.exceptions import DeployError
from manifest.pipeline import create_manifest, resolve_manifest
from zonegen.txt_packing import unpack_txt_strings

VALID_HASH = "GSRSYUZXNPIYZBQ7XYX3KSI7D4GDO2VPKG3XF4LIUVAT4F3XVA6A===="
ORIGIN = "dnsfileshare.com."


def _config() -> DeployConfig:
    return DeployConfig(origin=ORIGIN, vps_ip="127.0.0.1", tsig_secret="c2VjcmV0Cg==")


def _payload_b64(n_bytes: int = 10) -> str:
    return base64.b64encode(b"x" * n_bytes).decode("ascii")


def _rrset_to_pair(rrset, origin: str) -> tuple[str, str]:
    origin_name = dns.name.from_text(origin)
    relative = rrset.name.relativize(origin_name)
    chunk_hash = str(relative).split(".")[0]
    txt_rdata = rrset[0]
    strings = [s.decode("ascii") for s in txt_rdata.strings]
    return chunk_hash, unpack_txt_strings(strings)


def test_publish_success(monkeypatch):
    captured = []
    monkeypatch.setattr(
        "backend.app.send_update",
        lambda origin, rrsets, vps_ip, tsig_key_name, tsig_secret, port=53: captured.append(rrsets),
    )

    client = create_app(_config()).test_client()
    resp = client.post(
        "/api/v1/publish",
        json={"records": [{"hash": VALID_HASH, "payload": _payload_b64()}]},
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "record_count": 1}
    assert len(captured) == 1
    assert len(captured[0]) == 1


def test_publish_validation_error_returns_400(monkeypatch):
    monkeypatch.setattr("backend.app.send_update", lambda *a, **k: None)
    client = create_app(_config()).test_client()

    resp = client.post("/api/v1/publish", json={"records": []})
    assert resp.status_code == 400


def test_publish_malformed_json_returns_400(monkeypatch):
    monkeypatch.setattr("backend.app.send_update", lambda *a, **k: None)
    client = create_app(_config()).test_client()

    resp = client.post("/api/v1/publish", data="not json", content_type="application/json")
    assert resp.status_code == 400


def test_publish_deploy_error_returns_502_without_leaking_detail(monkeypatch):
    def failing_send_update(*args, **kwargs):
        raise DeployError("dynamic update rejected: TSIG error (bad secret)")

    monkeypatch.setattr("backend.app.send_update", failing_send_update)
    client = create_app(_config()).test_client()

    resp = client.post(
        "/api/v1/publish",
        json={"records": [{"hash": VALID_HASH, "payload": _payload_b64()}]},
    )
    assert resp.status_code == 502
    assert "TSIG" not in resp.get_data(as_text=True)


def test_publish_zone_generation_error_returns_422(monkeypatch):
    monkeypatch.setattr("backend.app.send_update", lambda *a, **k: None)
    client = create_app(_config()).test_client()

    too_long_hash = "A" * 100  # valid base32, but overflows the 63-char DNS label limit
    resp = client.post(
        "/api/v1/publish",
        json={"records": [{"hash": too_long_hash, "payload": _payload_b64()}]},
    )
    assert resp.status_code == 422


def test_publish_rate_limit_returns_429(monkeypatch):
    monkeypatch.setattr("backend.app.send_update", lambda *a, **k: None)
    monkeypatch.setattr("backend.app.RATE_LIMIT_MAX_REQUESTS", 1)
    client = create_app(_config()).test_client()

    body = {"records": [{"hash": VALID_HASH, "payload": _payload_b64()}]}
    first = client.post("/api/v1/publish", json=body)
    second = client.post("/api/v1/publish", json=body)

    assert first.status_code == 200
    assert second.status_code == 429


def test_publish_open_auth_requires_no_header(monkeypatch):
    monkeypatch.setattr("backend.app.send_update", lambda *a, **k: None)
    client = create_app(_config()).test_client()

    resp = client.post(
        "/api/v1/publish",
        json={"records": [{"hash": VALID_HASH, "payload": _payload_b64()}]},
    )
    assert resp.status_code == 200


def test_large_file_requires_multiple_batches_and_reassembles_correctly(monkeypatch):
    # Regression test for the 65,535-byte RFC 2136 UPDATE message ceiling identified
    # during planning: a single send_update() call is capped at roughly MAX_RECORDS_
    # PER_REQUEST records, so a large file must be split into multiple sequential
    # POSTs (the same contract webapp/upload.js implements client-side). This must
    # fail loudly if a future change accidentally reverts to one giant request.
    received_batches: list[list] = []

    def fake_send_update(origin, rrsets, vps_ip, tsig_key_name, tsig_secret, port=53):
        assert len(rrsets) <= MAX_RECORDS_PER_REQUEST
        received_batches.append(list(rrsets))

    monkeypatch.setattr("backend.app.send_update", fake_send_update)
    client = create_app(_config()).test_client()

    key = crypto.generate_key()
    # Enough chunks (core.constants.CHUNK_SIZE=1200) to need several batches, plus
    # one manifest record.
    plaintext = os.urandom(1200 * (MAX_RECORDS_PER_REQUEST * 3 + 2))
    store = ChunkStore()
    pointer_hash = create_manifest(plaintext, key, "large-test-file.bin", store)

    all_pairs = list(store.items())
    assert len(all_pairs) > MAX_RECORDS_PER_REQUEST  # sanity: really forces multiple batches

    batches = [
        all_pairs[i : i + MAX_RECORDS_PER_REQUEST]
        for i in range(0, len(all_pairs), MAX_RECORDS_PER_REQUEST)
    ]
    assert len(batches) > 1

    for batch in batches:
        resp = client.post(
            "/api/v1/publish",
            json={"records": [{"hash": h, "payload": p} for h, p in batch]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["record_count"] == len(batch)

    assert len(received_batches) == len(batches)

    # Reassemble a fresh store purely from what the mocked send_update received,
    # and confirm the exact original plaintext round-trips -- proves nothing was
    # dropped, duplicated, or corrupted by splitting across requests.
    reconstructed = ChunkStore()
    for rrsets in received_batches:
        for rrset in rrsets:
            chunk_hash, payload = _rrset_to_pair(rrset, ORIGIN)
            reconstructed.put(chunk_hash, payload)

    recovered = resolve_manifest(pointer_hash, key, reconstructed)
    assert recovered == plaintext
