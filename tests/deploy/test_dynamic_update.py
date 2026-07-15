import dns.name

from deploy.constants import DNS_UPDATE_BATCH_SIZE
from deploy.dynamic_update import build_update, build_update_batches
from zonegen.records import format_txt_record

ORIGIN = "dnsfileshare.com."


def test_build_update_targets_correct_zone_and_key():
    rrset = format_txt_record("HASHVALUE", "cGF5bG9hZA==", ORIGIN)

    update = build_update(ORIGIN, [rrset], "update-key", "c2VjcmV0Cg==")

    assert update.origin == dns.name.from_text(ORIGIN)
    assert update.keyname == dns.name.from_text("update-key")


def test_build_update_contains_added_rrset():
    rrset = format_txt_record("HASHVALUE", "cGF5bG9hZA==", ORIGIN)

    update = build_update(ORIGIN, [rrset], "update-key", "c2VjcmV0Cg==")

    names = [str(r.name) for r in update.update]
    assert names == ["HASHVALUE.chunks.dnsfileshare.com."]


def test_build_update_multiple_rrsets_all_added():
    rrset_a = format_txt_record("HASHA", "cGF5bG9hZA==", ORIGIN)
    rrset_b = format_txt_record("HASHB", "cGF5bG9hZDI=", ORIGIN)

    update = build_update(ORIGIN, [rrset_a, rrset_b], "update-key", "c2VjcmV0Cg==")

    assert len(update.update) == 2


def test_build_update_empty_rrset_list():
    update = build_update(ORIGIN, [], "update-key", "c2VjcmV0Cg==")

    assert list(update.update) == []


def test_build_update_batches_splits_into_expected_batch_sizes():
    # Deliberately not a round multiple of the batch size, so a partial final batch
    # is exercised too (mirrors webapp/tests/upload.test.js's own batching test sizing).
    record_count = DNS_UPDATE_BATCH_SIZE * 2 + 3
    rrsets = [format_txt_record(f"HASH{i}", "cGF5bG9hZA==", ORIGIN) for i in range(record_count)]

    batches = list(build_update_batches(ORIGIN, rrsets, "update-key", "c2VjcmV0Cg=="))

    assert [len(list(b.update)) for b in batches] == [DNS_UPDATE_BATCH_SIZE, DNS_UPDATE_BATCH_SIZE, 3]


def test_build_update_batches_covers_every_rrset_exactly_once_in_order():
    record_count = DNS_UPDATE_BATCH_SIZE * 2 + 3
    rrsets = [format_txt_record(f"HASH{i}", "cGF5bG9hZA==", ORIGIN) for i in range(record_count)]

    batches = list(build_update_batches(ORIGIN, rrsets, "update-key", "c2VjcmV0Cg=="))

    names = [str(r.name) for batch in batches for r in batch.update]
    expected = [str(rrset.name) for rrset in rrsets]
    assert names == expected


def test_build_update_batches_empty_list_yields_no_batches():
    assert list(build_update_batches(ORIGIN, [], "update-key", "c2VjcmV0Cg==")) == []


def test_build_update_batches_under_one_batch_yields_single_batch():
    rrsets = [format_txt_record("HASH0", "cGF5bG9hZA==", ORIGIN)]

    batches = list(build_update_batches(ORIGIN, rrsets, "update-key", "c2VjcmV0Cg=="))

    assert len(batches) == 1
    assert len(list(batches[0].update)) == 1
