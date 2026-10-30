
import re
import time
import logging
from flask import Blueprint, request
from werkzeug.security import generate_password_hash, check_password_hash

from database_manager.db import create_user, get_user, set_user_fails
from utils.helpers import success_response, error_response, now_str, make_token

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

MAX_FAILS    = 5
LOCK_SECONDS = 60


def _normalize_mobile(raw: str) -> str | None:
    """'+63 917 123 4567' / '0917-123-4567' -> '09171234567' (or None)."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("63") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    return digits if re.fullmatch(r"09\d{9}", digits) else None


def _auth_payload(mobile: str, name: str) -> dict:
    return {"mobile": mobile, "name": name, "token": make_token(mobile)}


#  POST /api/v1/auth/register

@auth_bp.route("/register", methods=["POST"])
def register():
    body   = request.get_json(silent=True) or {}
    name   = str(body.get("name", "")).strip()
    pin    = str(body.get("pin", "")).strip()
    mobile = _normalize_mobile(str(body.get("mobile", "")))

    if len(name) < 2:
        return error_response("Please enter your full name.", 400)
    if mobile is None:
        return error_response("Enter a valid mobile number,", 400)
    if not re.fullmatch(r"\d{4}", pin):
        return error_response("PIN must be exactly 4 digits.", 400)

    created = create_user(mobile, name, generate_password_hash(pin), now_str())
    if not created:
        return error_response(
            "This mobile number is already registered. Please sign in.", 409
        )

    logger.info("New user registered: %s", mobile)
    return success_response(_auth_payload(mobile, name), "Account created.", 200)


#  POST /api/v1/auth/login

@auth_bp.route("/login", methods=["POST"])
def login():
    body   = request.get_json(silent=True) or {}
    pin    = str(body.get("pin", "")).strip()
    mobile = _normalize_mobile(str(body.get("mobile", "")))

    if mobile is None:
        return error_response("Enter a valid mobile number.", 400)

    user = get_user(mobile)
    if user is None:
        return error_response(
            'No account for this number yet. Tap "Create account".', 404
        )

    now = time.time()
    if user["lock_until"] > now:
        secs = int(user["lock_until"] - now) + 1
        return error_response(
            f"Too many wrong attempts. Try again in {secs} seconds.", 429
        )

    if not check_password_hash(user["pin_hash"], pin):
        fails = user["fails"] + 1
        if fails >= MAX_FAILS:
            set_user_fails(mobile, 0, now + LOCK_SECONDS)
            return error_response(
                "Too many wrong attempts. Try again in 1 minute.", 429
            )
        set_user_fails(mobile, fails, 0)
        return error_response(f"Wrong PIN. {MAX_FAILS - fails} tries left.", 401)

    set_user_fails(mobile, 0, 0)
    return success_response(_auth_payload(mobile, user["name"]), "Signed in.", 200)