import pytest

from core.exceptions import ChunkHashMismatchError, ChunkNotFoundError
from core.hashing import compute_chunk_hash
from core.store import ChunkStore
from manifest import index_tree
from manifest.constants import MAX_HASHES_PER_NODE
from manifest.index_tree import build_index_tree, walk_index_tree


def _hash(i: int) -> str:
    return compute_chunk_hash(str(i).encode())


def test_single_leaf_base_case():
    store = ChunkStore()
    hashes = [_hash(i) for i in range(5)]

    root_hash = build_index_tree(hashes, store)
    node = index_tree._fetch_index_node(root_hash, store)

    assert node.is_leaf is True
    assert node.hashes == hashes
    assert walk_index_tree(root_hash, store) == hashes


def test_boundary_exactly_at_max():
    store = ChunkStore()
    hashes = [_hash(i) for i in range(MAX_HASHES_PER_NODE)]

    root_hash = build_index_tree(hashes, store)
    node = index_tree._fetch_index_node(root_hash, store)

    assert node.is_leaf is True
    assert len(store) == 1
    assert walk_index_tree(root_hash, store) == hashes


def test_boundary_one_over_max():
    store = ChunkStore()
    hashes = [_hash(i) for i in range(MAX_HASHES_PER_NODE + 1)]

    root_hash = build_index_tree(hashes, store)
    node = index_tree._fetch_index_node(root_hash, store)

    assert node.is_leaf is False
    assert walk_index_tree(root_hash, store) == hashes


def test_deep_recursion_via_monkeypatched_max(monkeypatch):
    monkeypatch.setattr(index_tree, "MAX_HASHES_PER_NODE", 3)
    store = ChunkStore()
    hashes = [_hash(i) for i in range(10)]

    root_hash = build_index_tree(hashes, store)
    root_node = index_tree._fetch_index_node(root_hash, store)

    assert root_node.is_leaf is False
    assert len(root_node.hashes) == 2
    assert len(store) == 7  # 4 leaves + 2 mid + 1 root
    assert walk_index_tree(root_hash, store) == hashes


def test_walk_missing_node_raises_chunk_not_found():
    store = ChunkStore()
    hashes = [_hash(i) for i in range(5)]
    root_hash = build_index_tree(hashes, store)
    del store._data[root_hash]

    with pytest.raises(ChunkNotFoundError):
        walk_index_tree(root_hash, store)


def test_walk_tampered_node_raises_hash_mismatch():
    store = ChunkStore()
    hashes = [_hash(i) for i in range(5)]
    root_hash = build_index_tree(hashes, store)

    corrupted = list(store._data[root_hash])
    corrupted[0] = "A" if corrupted[0] != "A" else "B"
    store._data[root_hash] = "".join(corrupted)

    with pytest.raises(ChunkHashMismatchError):
        walk_index_tree(root_hash, store)


def test_build_index_tree_empty_list():
    store = ChunkStore()
    root_hash = build_index_tree([], store)
    node = index_tree._fetch_index_node(root_hash, store)

    assert node.is_leaf is True
    assert node.hashes == []
    assert walk_index_tree(root_hash, store) == []
