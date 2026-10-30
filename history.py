
import logging
from flask import Blueprint, request

from config import Config
from database_manager.db import (
    get_all_analyses,
    get_analysis_by_id,
    count_analyses,
)
from utils.helpers import success_response, error_response, get_user_id

logger = logging.getLogger(__name__)

history_bp = Blueprint("history", __name__, url_prefix="/api/v1")


#  GET /api/v1/history

@history_bp.route("/history", methods=["GET"])
def get_history():

    user_id = get_user_id()
    if not user_id:
        return error_response("Please sign in first.", 401)

    try:
        page     = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", Config.DEFAULT_PAGE_SIZE))))
    except ValueError:
        return error_response("'page' and 'per_page' must be integers.", 400)

    try:
        records = get_all_analyses(page=page, per_page=per_page, user_id=user_id)
        total   = count_analyses(user_id=user_id)
    except Exception as exc:
        logger.error("History fetch failed: %s", exc)
        return error_response("Failed to retrieve analysis history.", 500, str(exc))

    return success_response(
        {
            "records":   records,
            "total":     total,
            "page":      page,
            "per_page":  per_page,
            "pages":     (total + per_page - 1) // per_page,
        },
        "History retrieved successfully",
    )


#  GET /api/v1/history/<id>

@history_bp.route("/history/<int:analysis_id>", methods=["GET"])
def get_analysis(analysis_id: int):
    """Return the full detail for one of the signed-in user's records."""
    user_id = get_user_id()
    if not user_id:
        return error_response("Please sign in first.", 401)

    try:
        record = get_analysis_by_id(analysis_id, user_id=user_id)
    except Exception as exc:
        logger.error("get_analysis_by_id(%d) failed: %s", analysis_id, exc)
        return error_response("Database error while fetching record.", 500, str(exc))

    # A record that belongs to someone else is reported as not found.
    if record is None:
        return error_response(f"No analysis found with id {analysis_id}.", 404)

    return success_response(record, "Analysis record retrieved.")


#  GET /api/v1/stats

@history_bp.route("/stats", methods=["GET"])
def get_stats():
    user_id = get_user_id()
    if not user_id:
        return error_response("Please sign in first.", 401)

    try:
        from database_manager.db import db_connection
        with db_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM analysis_history WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]

            # Stored status values are lowercase 3-class:
            # 'healthy', 'infested', 'pest'.
            status_rows = conn.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM analysis_history
                WHERE user_id = ?
                GROUP BY status
                """,
                (user_id,),
            ).fetchall()
            status_counts = {row["status"]: row["cnt"] for row in status_rows}

            healthy = status_counts.get("healthy", 0)
            infested = status_counts.get("infested", 0)
            pest = status_counts.get("pest", 0)

            severity_rows = conn.execute(
                """
                SELECT severity, COUNT(*) AS cnt
                FROM analysis_history
                WHERE user_id = ?
                GROUP BY severity
                """,
                (user_id,),
            ).fetchall()

            severity_breakdown = {row["severity"]: row["cnt"] for row in severity_rows}

            avg_conf_row = conn.execute(
                "SELECT AVG(confidence) FROM analysis_history WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            avg_confidence = round(avg_conf_row[0] or 0.0, 2)

    except Exception as exc:
        logger.error("Stats query failed: %s", exc)
        return error_response("Failed to compute statistics.", 500, str(exc))

    return success_response(
        {
            "total_analyses":     total,
            "healthy_count":      healthy,
            "infested_count":     infested,
            "pest_count":         pest,
            "average_confidence": avg_confidence,
            "severity_breakdown": severity_breakdown,
        },
        "Statistics retrieved.",
    )