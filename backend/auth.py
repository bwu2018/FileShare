from werkzeug.datastructures import Headers

from .exceptions import UploadAuthError


def check_auth(headers: Headers) -> None:
    # Fully open in v1 -- no token/login required, a deliberate choice for this
    # phase. Kept as its own function, called from app.py and reacted to only via
    # UploadAuthError, so a real check (e.g. a bearer token or OAuth) can replace
    # this body later without reshaping the request handler or any caller.
    return None
