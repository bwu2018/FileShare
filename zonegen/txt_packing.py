from .constants import TXT_STRING_MAX_LEN


def pack_txt_strings(payload: str, max_len: int = TXT_STRING_MAX_LEN) -> list[str]:
    if not payload:
        return [payload]
    return [payload[i : i + max_len] for i in range(0, len(payload), max_len)]


def unpack_txt_strings(strings: list[str]) -> str:
    return "".join(strings)
