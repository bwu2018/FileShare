from core.encoding import decode_chunk, encode_chunk
from core.exceptions import ChunkHashMismatchError
from core.hashing import compute_chunk_hash
from core.store import ChunkStore

from .constants import MAX_HASHES_PER_NODE
from .models import IndexNode
from .serialization import deserialize_index_node, serialize_index_node


def _store_index_node(node: IndexNode, store: ChunkStore) -> str:
    serialized = serialize_index_node(node)
    node_hash = compute_chunk_hash(serialized)
    store.put(node_hash, encode_chunk(serialized))
    return node_hash


def _fetch_index_node(node_hash: str, store: ChunkStore) -> IndexNode:
    encoded = store.get(node_hash)
    serialized = decode_chunk(encoded)
    if compute_chunk_hash(serialized) != node_hash:
        raise ChunkHashMismatchError(node_hash)
    return deserialize_index_node(serialized)


def _build_level(hashes: list[str], store: ChunkStore, is_leaf: bool) -> str:
    if len(hashes) <= MAX_HASHES_PER_NODE:
        return _store_index_node(IndexNode(is_leaf=is_leaf, hashes=hashes), store)

    next_level_hashes = [
        _store_index_node(IndexNode(is_leaf=is_leaf, hashes=hashes[i : i + MAX_HASHES_PER_NODE]), store)
        for i in range(0, len(hashes), MAX_HASHES_PER_NODE)
    ]
    return _build_level(next_level_hashes, store, is_leaf=False)


def build_index_tree(chunk_hashes: list[str], store: ChunkStore) -> str:
    return _build_level(chunk_hashes, store, is_leaf=True)


def walk_index_tree(root_hash: str, store: ChunkStore) -> list[str]:
    node = _fetch_index_node(root_hash, store)
    if node.is_leaf:
        return node.hashes

    result = []
    for child_hash in node.hashes:
        result.extend(walk_index_tree(child_hash, store))
    return result
