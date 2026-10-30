
import os
import logging
from flask import Blueprint, request, jsonify, send_from_directory, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from config import Config
from database_manager.db import get_all_records_unlimited
from services.report_service import (
    compute_majority_type,
    generate_consolidated_report,
    records_to_csv,
)

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")

_serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60  # 8-hour admin session


def get_all_records() -> list[dict]:

    return get_all_records_unlimited()


def _generate_token() -> str:
    return _serializer.dumps({"role": "admin"})


def _verify_token(token: str) -> bool:
    try:
        data = _serializer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        return data.get("role") == "admin"
    except (BadSignature, SignatureExpired):
        return False


def _require_admin():
    """Returns None if authorized, or an error Flask response if not."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"success": False, "message": "Missing admin token."}), 401

    token = auth_header.replace("Bearer ", "", 1)
    if not _verify_token(token):
        return jsonify({"success": False, "message": "Invalid or expired admin session."}), 401

    return None


# ── Serve the admin panel HTML itself
@admin_bp.route("/", methods=["GET"])
def admin_panel():
    return send_from_directory("static/admin", "index.html")


# ── Login ────────────────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        logger.error("ADMIN_PASSWORD is not set in .env — admin login is disabled.")
        return jsonify({"success": False, "message": "Admin login is not configured."}), 500

    if password != admin_password:
        return jsonify({"success": False, "message": "Incorrect password."}), 401

    token = _generate_token()
    return jsonify({"success": True, "token": token})


# ── Dashboard data (protected) ──────────────────────────────────────────────

@admin_bp.route("/dashboard", methods=["GET"])
def admin_dashboard():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized

    try:
        records = get_all_records()
        total = len(records)
        counts = {}
        for r in records:
            status = r.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
    except Exception as exc:
        logger.error("Admin dashboard data fetch failed: %s", exc)
        return jsonify({"success": False, "message": "Failed to load dashboard data.", "details": str(exc)}), 500

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "total_analyses": total,
                "healthy_count": counts.get("healthy", 0),
                "infested_count": counts.get("infested", 0),
                "pest_count": counts.get("pest", 0),
            },
            "recent_analyses": records[:50],
        }
    })


# ── Majority pest type (protected) ──────────────────────────────────────────

@admin_bp.route("/majority-type", methods=["GET"])
def admin_majority_type():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized

    records = get_all_records()
    result = compute_majority_type(records)
    return jsonify({"success": True, "data": result})


# ── Consolidated report (protected) ─────────────────────────────────────────

@admin_bp.route("/report", methods=["GET"])
def admin_report():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized

    records = get_all_records()
    result = generate_consolidated_report(records)
    return jsonify({"success": True, "data": result})


# ── Report CSV download (protected) ─────────────────────────────────────────

@admin_bp.route("/report/download", methods=["GET"])
def admin_report_download():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized

    records = get_all_records()
    csv_text = records_to_csv(records)

    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=pest_detection_report.csv"},
    )