"""
diagnose.py  –  find out WHY a photo gets no result.

Usage (from the backend folder, with your venv active):
    python diagnose.py path\to\photo.jpg

It runs the same three checks as the real server, in the same order, and
prints the numbers, so you can see exactly which one rejects the photo.
"""
import sys
import cv2
import numpy as np
from ultralytics import YOLO
from config import Config

if len(sys.argv) < 2:
    # GI-EDIT: Gamitan ug raw string (r) para mawala ang SyntaxWarning sa path \p
    sys.exit(r"Usage: python diagnose.py path\to\photo.jpg")

path = sys.argv[1]
img_bgr = cv2.imread(path)
if img_bgr is None:
    sys.exit(f"Cannot read image: {path}")

h, w = img_bgr.shape[:2]
print(f"\nImage: {path}  ({w}x{h})")
print("=" * 60)

# ── Check 1: blur ──────────────────────────────────────────────────────────────
gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
blur_var = cv2.Laplacian(gray, cv2.CV_64F).var()
blur_ok = blur_var >= 30.0
print(f"1) Sharpness   : {blur_var:7.1f}   (needs >= 30)        -> {'PASS' if blur_ok else 'FAIL  \"not clear\"'}")

# ── Check 2: green colour ──────────────────────────────────────────────────────
hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
mask = cv2.inRange(hsv, np.array([35, 80, 40]), np.array([85, 255, 220]))
green_ratio = float(np.sum(mask > 0)) / mask.size
loose = cv2.inRange(hsv, np.array([25, 30, 30]), np.array([95, 255, 255]))
loose_ratio = float(np.sum(loose > 0)) / loose.size

# GI-EDIT: Gipaubos gikan 0.25 (25%) ngadto sa 0.15 (15%)
# Tungod kay ang infested/tuyo nga humay mas gamay ug green (daghang brown spots)
green_ok = green_ratio >= 0.15
print(f"2) Green amount: {green_ratio*100:6.1f}%   (needs >= 15%)       -> {'PASS' if green_ok else 'FAIL  \"Only ricefield can detect\"'}")
print(f"   (with a looser colour range it would be {loose_ratio*100:.1f}%)")

# ── Check 3: model ─────────────────────────────────────────────────────────────
print(f"3) Model       : {Config.MODEL_PATH}")
model = YOLO(Config.MODEL_PATH)

# GI-EDIT: Gi-add ang imgsz=1024 ug gipagamyan ang conf
# Makatabang kini aron makita sa YOLO ang maliliit/layo nga spots (1 meter)
res = model.predict(
    source=path,
    conf=0.01,
    imgsz=1024,
    iou=Config.YOLO_IOU_THRESHOLD,
    verbose=False
)

dets = []
for r in res:
    if r.boxes is None:
        continue
    for b in r.boxes:
        dets.append((float(b.conf[0]) * 100, model.names.get(int(b.cls[0]), "?")))
dets.sort(reverse=True)

# GI-EDIT: Override o default sa 5.0% sa halip nga 10% o 55%
min_conf = getattr(Config, "MIN_RICE_CONFIDENCE", 5.0)
if not hasattr(Config, "MIN_RICE_CONFIDENCE"):
    print("   !! Config.MIN_RICE_CONFIDENCE is MISSING in config.py "
          "-> Add: MIN_RICE_CONFIDENCE = 5.0")

if not dets:
    print("   The model found NOTHING in this photo (even at 1% confidence).")
else:
    print("   Top detections (class, confidence):")
    for conf, name in dets[:8]:
        #  Naggamit og fixed 1.0% threshold para ma-consider nga "visible" sa diagnose script
        server_threshold = getattr(Config, "YOLO_CONF_THRESHOLD", 0.01) * 100
        seen = "visible to server" if conf >= server_threshold else "hidden (below server threshold)"
        print(f"     {name:35s} {conf:5.1f}%   {seen}")

# GI-EDIT: Filtering logic adjustments
server_thresh_pct = getattr(Config, "YOLO_CONF_THRESHOLD", 0.50) * 100
visible = [d for d in dets if d[0] >= server_thresh_pct]
top = visible[0][0] if visible else (dets[0][0] if dets else 0.0)


model_ok = bool(dets) and top >= min_conf
print(f"   Top visible confidence {top:.1f}%  (needs >= {min_conf}%)  -> {'PASS' if model_ok else 'FAIL  \"Only ricefield can detect\"'}")

# ── Verdict ────────────────────────────────────────────────────────────────────
print("=" * 60)
if not blur_ok:
    print("RESULT: rejected as 'The image is not clear'.")
elif not green_ok:
    print("RESULT: rejected by the COLOUR check (not enough green).")
elif not model_ok:
    print("RESULT: rejected by the MODEL check (model not confident this is rice).")
else:
    top_class = visible[0][1] if visible else dets[0][1]
    print(f"RESULT: accepted. Top class = {top_class} at {top:.1f}%")
print()