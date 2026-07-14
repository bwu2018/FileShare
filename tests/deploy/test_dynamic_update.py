import dns.name

from deploy.dynamic_update import build_update
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
