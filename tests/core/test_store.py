from core import ChunkStore


def test_items_returns_all_pairs():
    store = ChunkStore()
    store.put("hash_a", "payload_a")
    store.put("hash_b", "payload_b")

    assert set(store.items()) == {("hash_a", "payload_a"), ("hash_b", "payload_b")}


def test_items_on_empty_store_returns_nothing():
    store = ChunkStore()

    assert list(store.items()) == []


def test_sorted_items_is_deterministic_regardless_of_insertion_order():
    store_a = ChunkStore()
    store_a.put("hash_c", "payload_c")
    store_a.put("hash_a", "payload_a")
    store_a.put("hash_b", "payload_b")

    store_b = ChunkStore()
    store_b.put("hash_a", "payload_a")
    store_b.put("hash_b", "payload_b")
    store_b.put("hash_c", "payload_c")

    assert sorted(store_a.items()) == sorted(store_b.items())
    assert sorted(store_a.items()) == [
        ("hash_a", "payload_a"),
        ("hash_b", "payload_b"),
        ("hash_c", "payload_c"),
    ]
