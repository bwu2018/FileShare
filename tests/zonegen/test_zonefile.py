import re

import dns.rdataclass
import dns.rdatatype
import dns.zone

from core import ChunkStore
from zonegen.constants import RECORD_TTL
from zonegen.txt_packing import unpack_txt_strings
from zonegen.zonefile import build_zone, generate_zone_file

ORIGIN = "dnsstore.test."


def _zone(serial: int = 2026071201, ns_ip: str = "127.0.0.1") -> dns.zone.Zone:
    # dns.zone.Zone is mutable and generate_zone_file() adds records into it in
    # place, so every test needs its own fresh instance -- never share one across tests.
    return build_zone(origin=ORIGIN, serial=serial, ns_ip=ns_ip)


HEADER_LINE_COUNT = 5  # $ORIGIN, SOA, NS, apex A, glue A


def _record_lines(zone_text: str) -> list[str]:
    # test-only line scan, not a general zone-file parser
    return zone_text.splitlines()[HEADER_LINE_COUNT:]


def test_empty_store_header_only():
    store = ChunkStore()
    zone_text = generate_zone_file(store, _zone())

    assert "$ORIGIN dnsstore.test." in zone_text
    assert "$TTL" not in zone_text  # every rrset carries an explicit TTL instead
    assert "IN SOA" in zone_text
    assert "IN NS" in zone_text
    assert _record_lines(zone_text) == []


def test_non_empty_store_one_record_per_entry_hash_sorted():
    store = ChunkStore()
    store.put("hash_c", "payload_c")
    store.put("hash_a", "payload_a")
    store.put("hash_b", "payload_b")

    zone_text = generate_zone_file(store, _zone())
    lines = _record_lines(zone_text)

    assert len(lines) == 3
    owners = [line.split()[0] for line in lines]
    assert owners == ["hash_a.chunks", "hash_b.chunks", "hash_c.chunks"]


def test_full_round_trip_through_generated_text():
    store = ChunkStore()
    store.put("hash_x", "payload-short")
    store.put("hash_y", "y" * 600)  # forces multi-string packing

    zone_text = generate_zone_file(store, _zone())

    for chunk_hash, expected_payload in store.items():
        line = next(line for line in _record_lines(zone_text) if line.startswith(f"{chunk_hash}.chunks"))
        strings = re.findall(r'"([^"]*)"', line)
        assert unpack_txt_strings(strings) == expected_payload


def test_header_contains_configured_fields():
    zone_text = generate_zone_file(ChunkStore(), _zone())

    assert "$ORIGIN dnsstore.test." in zone_text
    assert "2026071201" in zone_text
    assert "3600" in zone_text
    assert "900" in zone_text
    assert str(RECORD_TTL) in zone_text
    assert "IN SOA ns1 admin" in zone_text
    assert "IN NS ns1" in zone_text
    assert f"@ {RECORD_TTL} IN A 127.0.0.1" in zone_text
    assert f"ns1 {RECORD_TTL} IN A 127.0.0.1" in zone_text


def test_generated_zone_parses_as_valid_bind_zone_syntax():
    # independent cross-check via dnspython's own zone parser, not just the line scan above
    store = ChunkStore()
    store.put("hash_x", "payload-short")
    store.put("hash_y", "y" * 600)  # forces multi-string packing

    zone_text = generate_zone_file(store, _zone())
    parsed = dns.zone.from_text(zone_text, origin=ORIGIN, check_origin=True)

    for chunk_hash, expected_payload in store.items():
        node = parsed.find_node(f"{chunk_hash}.chunks")
        rdataset = node.find_rdataset(dns.rdataclass.IN, dns.rdatatype.TXT)
        strings = [s.decode("ascii") for s in rdataset[0].strings]
        assert unpack_txt_strings(strings) == expected_payload


def test_custom_ns_ip_is_honored():
    zone_text = generate_zone_file(ChunkStore(), _zone(serial=1, ns_ip="203.0.113.10"))

    assert f"ns1 {RECORD_TTL} IN A 203.0.113.10" in zone_text
    assert f"@ {RECORD_TTL} IN A 203.0.113.10" in zone_text
    assert "127.0.0.1" not in zone_text


def test_web_ip_defaults_to_ns_ip():
    zone_text = generate_zone_file(
        ChunkStore(), build_zone(origin=ORIGIN, serial=1, ns_ip="203.0.113.10")
    )

    assert f"@ {RECORD_TTL} IN A 203.0.113.10" in zone_text
    assert f"ns1 {RECORD_TTL} IN A 203.0.113.10" in zone_text


def test_web_ip_can_differ_from_ns_ip():
    zone_text = generate_zone_file(
        ChunkStore(),
        build_zone(origin=ORIGIN, serial=1, ns_ip="203.0.113.10", web_ip="198.51.100.20"),
    )

    assert f"@ {RECORD_TTL} IN A 198.51.100.20" in zone_text
    assert f"ns1 {RECORD_TTL} IN A 203.0.113.10" in zone_text


def test_differing_serial_only_changes_serial_line():
    store = ChunkStore()
    store.put("hash_a", "payload_a")

    store_b = ChunkStore()
    store_b.put("hash_a", "payload_a")

    zone_a = generate_zone_file(store, _zone(serial=1))
    zone_b = generate_zone_file(store_b, _zone(serial=2))

    records_a = _record_lines(zone_a)
    records_b = _record_lines(zone_b)
    assert records_a == records_b

    lines_a = zone_a.splitlines()
    lines_b = zone_b.splitlines()
    diff_lines = [a for a, b in zip(lines_a, lines_b) if a != b]
    assert len(diff_lines) == 1
    assert "SOA" in diff_lines[0]
