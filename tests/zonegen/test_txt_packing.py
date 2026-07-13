import base64
import math

from zonegen.txt_packing import pack_txt_strings, unpack_txt_strings


def test_short_payload_not_split():
    payload = "x" * 254
    strings = pack_txt_strings(payload)

    assert strings == [payload]


def test_payload_exactly_255_chars_one_string():
    payload = "x" * 255
    strings = pack_txt_strings(payload)

    assert strings == [payload]


def test_payload_exactly_510_chars_two_full_strings():
    payload = "x" * 510
    strings = pack_txt_strings(payload)

    assert strings == ["x" * 255, "x" * 255]


def test_payload_256_chars_two_strings_short_trailer():
    payload = "x" * 256
    strings = pack_txt_strings(payload)

    assert strings == ["x" * 255, "x"]


def test_realistic_content_chunk_payload():
    # CHUNK_SIZE=1200 raw bytes -> 1600 base64 chars, no padding
    payload = base64.b64encode(b"x" * 1200).decode("ascii")
    assert len(payload) == 1600

    strings = pack_txt_strings(payload)

    assert len(strings) == math.ceil(1600 / 255) == 7
    assert unpack_txt_strings(strings) == payload


def test_empty_payload_round_trips():
    strings = pack_txt_strings("")

    assert strings == [""]
    assert unpack_txt_strings(strings) == ""


def test_all_strings_within_max_length():
    for payload in ["x" * 254, "x" * 255, "x" * 510, "x" * 256, "x" * 1600]:
        for s in pack_txt_strings(payload):
            assert len(s) <= 255


def test_very_long_payload_round_trips():
    # Simulates the max 65535-byte UTF-8 file_name case pushing the manifest blob large
    payload = "y" * 65_535
    strings = pack_txt_strings(payload)

    assert unpack_txt_strings(strings) == payload
