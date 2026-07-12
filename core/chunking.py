from .constants import CHUNK_SIZE


def split_into_chunks(data: bytes, chunk_size: int = CHUNK_SIZE) -> list[bytes]:
    if not data:
        return [data]
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]


def join_chunks(chunks: list[bytes]) -> bytes:
    return b"".join(chunks)
