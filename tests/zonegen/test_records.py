import dns.rdatatype
import pytest

from zonegen.constants import RECORD_TTL
from zonegen.exceptions import ZoneGenerationError
from zonegen.records import format_txt_record

ORIGIN = "dnsstore.test."


def test_single_string_payload_record():
    rrset = format_txt_record("HASHVALUE", "short-payload", ORIGIN)

    assert str(rrset.name) == "HASHVALUE.chunks.dnsstore.test."
    assert rrset.rdtype == dns.rdatatype.TXT
    assert rrset.ttl == RECORD_TTL
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


def test_oversized_rdata_raises():
    # Each packed string costs 256 wire bytes (1-byte length prefix + 255 payload bytes),
    # so 257 full-length strings (65,792 wire bytes) safely exceeds the 65,535-byte cap.
    payload = "A" * (257 * 255)

    with pytest.raises(ZoneGenerationError):
        format_txt_record("HASHVALUE", payload, ORIGIN)


def test_large_payload_under_max_does_not_raise():
    # 255 full-length strings -> 255 * 256 = 65,280 wire bytes, safely under the
    # 65,535-byte cap -- confirms the check doesn't false-positive on large-but-valid
    # payloads (e.g. a long manifest file_name), only genuinely oversized ones.
    payload = "A" * (255 * 255)

    rrset = format_txt_record("HASHVALUE", payload, ORIGIN)

    assert len(rrset[0].strings) == 255


def test_no_backslash_in_generated_text():
    rrset = format_txt_record("HASHVALUE", "some+payload/with=chars", ORIGIN)

    assert "\\" not in rrset.to_text()
