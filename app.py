import logging
import os
import sys

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from config import config_map, Config

#  Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def create_app(env: str = "default") -> Flask:
    app = Flask(__name__)

    app.config.from_object(config_map[env])

    CORS(app, origins=app.config.get("CORS_ORIGINS", "*"))

    from database_manager.db import init_db
    init_db()

    from services.yolo_service import load_model
    try:
        load_model()
    except Exception as exc:
        logger.error("Model load warning: %s", exc)

    from routes.analyze import analyze_bp
    from routes.history import history_bp
    from routes.admin import admin_bp
    from routes.auth import auth_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(auth_bp)

    @app.route("/uploads/<path:filename>", methods=["GET"])
    def serve_uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "service": "Rice Pest Detection API",
            "version": "1.0.0",
            "status": "running",
            "docs": "POST /api/v1/analyze  |  GET /api/v1/history  |  GET /api/v1/stats",
        })

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy"}), 200

    @app.errorhandler(400)
    def bad_request(exc):
        return jsonify({"success": False, "message": "Bad request.", "details": str(exc)}), 400

    @app.errorhandler(404)
    def not_found(exc):
        return jsonify({"success": False, "message": "Endpoint not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return jsonify({"success": False, "message": "Method not allowed."}), 405

    @app.errorhandler(413)
    def payload_too_large(exc):
        max_mb = app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024) // (1024 * 1024)
        return jsonify({
            "success": False,
            "message": f"File too large. Maximum allowed size is {max_mb} MB.",
        }), 413

    @app.errorhandler(500)
    def internal_error(exc):
        logger.exception("Unhandled server error")
        return jsonify({"success": False, "message": "Internal server error."}), 500

    logger.info("Rice Pest Detection API ready (env=%s).", env)
    return app


env = os.getenv("FLASK_ENV", "default")
app = create_app(env)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))