import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_DIR = BASE_DIR / "database"
MODEL_DIR = BASE_DIR / "models"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)



class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "rice-pest-secret-key-change-in-prod")

    # Upload settings
    UPLOAD_FOLDER = str(UPLOAD_DIR)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}


    ALLOWED_VIDEO_EXTENSIONS = set()
    DATABASE_PATH = str(DB_DIR / "rice_pest.db")
    MIN_RICE_CONFIDENCE = 10.0
    MODEL_PATH = str(MODEL_DIR / "best(final).pt")
    YOLO_CONF_THRESHOLD = 0.10
    YOLO_IOU_THRESHOLD = 0.15

    # Severity thresholds (confidence %)
    SEVERITY_LOW_MAX = 50  # 0–50  → Yellow Alert
    SEVERITY_MODERATE_MAX = 75  # 51–75 → Orange Alert
    # 76–100 → Red Alert

    # CORS – set to your Flutter app's origin in production
    CORS_ORIGINS = "*"

    # Pagination default
    DEFAULT_PAGE_SIZE = 20

    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}