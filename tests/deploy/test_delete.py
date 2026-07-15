import dns.name
import dns.rdatatype

from deploy.constants import DNS_UPDATE_BATCH_SIZE
from deploy.dynamic_update import build_delete_update, build_delete_update_batches

ORIGIN = "dnsfileshare.com."


def test_build_delete_update_targets_correct_zone_and_key():
    update = build_delete_update(ORIGIN, ["HASHVALUE"], "update-key", "c2VjcmV0Cg==")

    assert update.origin == dns.name.from_text(ORIGIN)
    assert update.keyname == dns.name.from_text("update-key")


def test_build_delete_update_contains_deleted_rrset():
    update = build_delete_update(ORIGIN, ["HASHVALUE"], "update-key", "c2VjcmV0Cg==")

    names = [str(r.name) for r in update.update]
    assert names == ["HASHVALUE.chunks.dnsfileshare.com."]


def test_build_delete_update_uses_txt_rdtype_with_no_payload():
    update = build_delete_update(ORIGIN, ["HASHVALUE"], "update-key", "c2VjcmV0Cg==")

    rrset = list(update.update)[0]
    assert rrset.rdtype == dns.rdatatype.TXT
    assert list(rrset) == []  # a delete-rrset entry carries no rdata


def test_build_delete_update_multiple_addresses_all_deleted():
    update = build_delete_update(ORIGIN, ["HASHA", "HASHB"], "update-key", "c2VjcmV0Cg==")

    assert len(update.update) == 2


def test_build_delete_update_empty_address_list():
    update = build_delete_update(ORIGIN, [], "update-key", "c2VjcmV0Cg==")

    assert list(update.update) == []


def test_build_delete_update_batches_splits_into_expected_batch_sizes():
    address_count = DNS_UPDATE_BATCH_SIZE * 2 + 3
    addresses = [f"HASH{i}" for i in range(address_count)]

    batches = list(build_delete_update_batches(ORIGIN, addresses, "update-key", "c2VjcmV0Cg=="))

    assert [len(list(b.update)) for b in batches] == [DNS_UPDATE_BATCH_SIZE, DNS_UPDATE_BATCH_SIZE, 3]


def test_build_delete_update_batches_covers_every_address_exactly_once_in_order():
    address_count = DNS_UPDATE_BATCH_SIZE * 2 + 3
    addresses = [f"HASH{i}" for i in range(address_count)]

    batches = list(build_delete_update_batches(ORIGIN, addresses, "update-key", "c2VjcmV0Cg=="))

    names = [str(r.name) for batch in batches for r in batch.update]
    expected = [f"{address}.chunks.dnsfileshare.com." for address in addresses]
    assert names == expected


def test_build_delete_update_batches_empty_list_yields_no_batches():
    assert list(build_delete_update_batches(ORIGIN, [], "update-key", "c2VjcmV0Cg==")) == []
