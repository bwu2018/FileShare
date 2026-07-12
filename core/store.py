from .exceptions import ChunkNotFoundError


class ChunkStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def put(self, chunk_hash: str, encoded_chunk: str) -> None:
        self._data[chunk_hash] = encoded_chunk

    def get(self, chunk_hash: str) -> str:
        try:
            return self._data[chunk_hash]
        except KeyError:
            raise ChunkNotFoundError(chunk_hash) from None

    def __contains__(self, chunk_hash: str) -> bool:
        return chunk_hash in self._data

    def __len__(self) -> int:
        return len(self._data)
