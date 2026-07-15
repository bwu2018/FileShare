import logging

from flask import Flask, jsonify, request

from deploy.config import DeployConfig
from deploy.dynamic_update import send_update
from deploy.exceptions import DeployError
from zonegen.exceptions import ZoneGenerationError
from zonegen.records import format_txt_record

from .auth import check_auth
from .constants import MAX_CONTENT_LENGTH, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
from .exceptions import UploadAuthError, UploadValidationError
from .ratelimit import RateLimiter
from .validation import validate_records

logger = logging.getLogger(__name__)


def create_app(config: DeployConfig) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    limiter = RateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)

    @app.post("/api/v1/publish")
    def publish():
        try:
            check_auth(request.headers)
        except UploadAuthError as exc:
            return jsonify(error=str(exc)), 401

        client_ip = request.remote_addr or "unknown"
        if not limiter.allow(client_ip):
            return jsonify(error="rate limit exceeded"), 429

        data = request.get_json(silent=True)
        try:
            records = validate_records(data)
        except UploadValidationError as exc:
            return jsonify(error=str(exc)), 400

        # The manifest record is just one more (hash, payload) pair here -- format_txt_record
        # and send_update treat it identically to a content chunk, mirroring how
        # deploy/publish.py's ChunkStore never distinguishes them either.
        try:
            rrsets = [
                format_txt_record(chunk_hash, payload, config.origin)
                for chunk_hash, payload in records
            ]
        except ZoneGenerationError as exc:
            return jsonify(error=str(exc)), 422

        try:
            send_update(
                config.origin,
                rrsets,
                config.vps_ip,
                config.tsig_key_name,
                config.tsig_secret,
            )
        except DeployError as exc:
            # Full detail server-side only -- the client just learns the upstream
            # DNS write failed, not TSIG/rcode internals.
            logger.error("dynamic update failed: %s", exc)
            return jsonify(error="upstream DNS update failed"), 502

        logger.info("published %d record(s) from %s", len(records), client_ip)
        return jsonify(status="ok", record_count=len(records)), 200

    return app
