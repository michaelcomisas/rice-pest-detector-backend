import os
import hmac
import hashlib
import uuid
import logging
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

from config import Config

logger = logging.getLogger(__name__)


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    )


def save_uploaded_file(file_storage) -> tuple[str, str]:
    original_name   = secure_filename(file_storage.filename)
    extension       = original_name.rsplit(".", 1)[-1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{extension}"
    full_path       = os.path.join(Config.UPLOAD_FOLDER, unique_filename)

    file_storage.save(full_path)
    logger.debug("Saved upload to '%s'.", full_path)
    return unique_filename, full_path


def delete_file_safely(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        logger.warning("Could not delete file '%s': %s", path, exc)


# Response helpers

def success_response(data: dict, message: str = "Success", status_code: int = 200):
    from flask import jsonify
    return jsonify({
        "success": True,
        "message": message,
        "data":    data,
    }), status_code


def error_response(message: str, status_code: int = 400, details: str = ""):

    from flask import jsonify
    payload = {
        "success": False,
        "message": message,
    }
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


#  Date/time

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


#  User identity

def make_token(mobile: str) -> str:
    return hmac.new(
        Config.SECRET_KEY.encode("utf-8"),
        mobile.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def get_user_id() -> str:

    from flask import request
    mobile = (request.headers.get("X-User-Id") or "").strip()
    token  = (request.headers.get("X-Auth-Token") or "").strip()
    if not mobile or not token:
        return ""
    if not hmac.compare_digest(make_token(mobile), token):
        return ""
    return mobile