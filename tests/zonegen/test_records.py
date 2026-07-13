import dns.rdatatype
import pytest

from zonegen.exceptions import ZoneGenerationError
from zonegen.records import format_txt_record

ORIGIN = "dnsstore.test."


def test_single_string_payload_record():
    rrset = format_txt_record("HASHVALUE", "short-payload", ORIGIN)

    assert str(rrset.name) == "HASHVALUE.chunks.dnsstore.test."
    assert rrset.rdtype == dns.rdatatype.TXT
    assert rrset.ttl == 604800
    assert rrset[0].strings == (b"short-payload",)


def test_multi_string_payload_record_preserves_order():
    payload = "A" * 255 + "B" * 255 + "C" * 10
    rrset = format_txt_record("HASHVALUE", payload, ORIGIN)

    assert rrset[0].strings == (b"A" * 255, b"B" * 255, b"C" * 10)


def test_oversized_label_raises():
    with pytest.raises(ZoneGenerationError):
        format_txt_record("H" * 64, "payload", ORIGIN)


def test_oversized_fqdn_raises():
    long_origin = ("sub." * 70) + "test."

    with pytest.raises(ZoneGenerationError):
        format_txt_record("HASHVALUE", "payload", long_origin)


def test_no_backslash_in_generated_text():
    rrset = format_txt_record("HASHVALUE", "some+payload/with=chars", ORIGIN)

    assert "\\" not in rrset.to_text()
