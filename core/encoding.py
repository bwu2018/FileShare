import base64


def encode_chunk(chunk: bytes) -> str:
    return base64.b64encode(chunk).decode("ascii")


def decode_chunk(encoded: str) -> bytes:
    return base64.b64decode(encoded.encode("ascii"))
