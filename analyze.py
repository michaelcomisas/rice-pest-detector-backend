
import logging
import cv2  # Added for image parsing
import numpy as np  # Added for matrix checking
from flask import Blueprint, request

from config import Config
from database_manager.db import save_analysis
from services.yolo_service import run_inference
from utils.helpers import (
    allowed_file,
    save_uploaded_file,
    delete_file_safely,
    success_response,
    error_response,
    now_str,
    get_user_id,
)

logger = logging.getLogger(__name__)

analyze_bp = Blueprint("analyze", __name__, url_prefix="/api/v1")


#  Blur Detection Helper
def is_image_blurry(image_path: str) -> bool:
    """
    Calculates the Laplacian variance of the image.
    If the variance is below a threshold, the image is considered blurry.
    """
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return True
        variance = cv2.Laplacian(img, cv2.CV_64F).var()

        # Threshold: Below 100 usually means blurry or out of focus
        return variance < 30.0
    except Exception as err:
        logger.error("Blur checking engine failed: %s", err)
        return True


# ── Security Plant Guard Helper ───────────────────────────────────────────────
def verify_is_rice_field(image_path: str) -> bool:
    """
    Analyzes pixel matrices to ensure the image contains an acceptable threshold
    of plant chlorophyll green before recording stats data.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return False

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_green = np.array([35, 80, 40])
        upper_green = np.array([85, 255, 220])

        mask = cv2.inRange(hsv, lower_green, upper_green)
        green_ratio = np.sum(mask > 0) / mask.size

        return green_ratio >= 0.25
    except Exception as err:
        logger.error("Scene checking constraint engine failed: %s", err)
        return False


#  POST /api/v1/analyze

@analyze_bp.route("/analyze", methods=["POST"])
def analyze_image():
    #  Identify the user
    user_id = get_user_id()
    if not user_id:
        return error_response("Please sign in first.", 401)

    #  Validate request
    if "image" not in request.files:
        return error_response("No image file provided. Use form-data key 'image'.", 400)

    file = request.files["image"]

    if file.filename == "":
        return error_response("Empty filename. Please select a valid image file.", 400)

    if not allowed_file(file.filename):
        allowed = ", ".join(Config.ALLOWED_EXTENSIONS)
        return error_response(
            f"Unsupported file type. Allowed types: {allowed}.", 415
        )

    #  Save file
    try:
        saved_filename, image_path = save_uploaded_file(file)
        original_name = file.filename
    except Exception as exc:
        logger.error("File save failed: %s", exc)
        return error_response("Failed to save the uploaded file.", 500, str(exc))

    #  Check Image Quality / Blur
    if is_image_blurry(image_path):
        delete_file_safely(image_path)
        return error_response(
            "The image is not clear. Try capture again.",
            400
        )

    #  Enforce Scene Matching Constraints FIRST

    if not verify_is_rice_field(image_path):
        delete_file_safely(image_path)
        return error_response(
            "Only ricefield can detect.",
            422  # 422 Unprocessable Entity
        )

    #  Run inference
    try:
        inference = run_inference(image_path)

    except FileNotFoundError as exc:
        delete_file_safely(image_path)
        return error_response("Image file not found after upload.", 500, str(exc))
    except RuntimeError as exc:
        delete_file_safely(image_path)
        msg = str(exc)
        if "not clear" in msg:
            return error_response(msg, 400)
        elif "ricefield" in msg.lower():
            return error_response(msg, 422)
        else:
            return error_response("AI model error during inference.", 500, msg)
    except Exception as exc:
        delete_file_safely(image_path)
        logger.exception("Unexpected inference error")
        return error_response("An unexpected error occurred during analysis.", 500, str(exc))

    #  Persist result
    timestamp = now_str()
    record = {
        "user_id":        user_id,
        "filename":       saved_filename,
        "original_name":  original_name,
        "status":         inference["status"],
        "confidence":     inference["confidence"],
        "severity":       inference["severity"],
        "recommendation": inference["recommendation"],
        "detections":     inference["detections"],
        "analysis_date":  timestamp,
        "image_path":     image_path,
    }

    try:
        new_id = save_analysis(record)
    except Exception as exc:
        logger.error("Database save failed: %s", exc)
        return success_response(
            {**inference, "filename": saved_filename, "original_name": original_name,
             "timestamp": timestamp, "db_warning": "Result not saved to database."},
            message="Analysis complete (database unavailable)",
            status_code=200,
        )

    #  Build response
    response_data = {
        "id":             new_id,
        "filename":       saved_filename,
        "original_name":  original_name,
        "status":         inference["status"],
        "confidence":     inference["confidence"],
        "severity":       inference["severity"],
        "recommendation": inference["recommendation"],
        "detections":     inference["detections"],
        "raw_detections": inference["raw_detections"],
        "timestamp":      timestamp,
    }

    logger.info(
        "Analysis #%d complete – status=%s confidence=%.1f%% severity=%s",
        new_id, inference["status"], inference["confidence"], inference["severity"],
    )

    return success_response(response_data, "Analysis complete", 200)