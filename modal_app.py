import modal

app = modal.App("rice-pest-detector")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install_from_requirements("requirements.txt")
    # add_local_dir must stay LAST
    .add_local_dir(".", remote_path="/app", ignore=[
        ".venv", "venv", "__pycache__", ".git", ".env",
        "database", "uploads", "runs",
    ])
)

# ── Persistent storage ──────────────────────────────────────────────────────
db_volume      = modal.Volume.from_name("rice-pest-db", create_if_missing=True)
uploads_volume = modal.Volume.from_name("rice-pest-uploads", create_if_missing=True)


@app.function(
    image=image,
    timeout=300,
    cpu=4,
    memory=4096,
    scaledown_window=300,
    max_containers=1,
    secrets=[modal.Secret.from_name("rice-pest-secret")],
    volumes={
        "/app/database": db_volume,
        "/app/uploads": uploads_volume,
    },
)
@modal.concurrent(max_inputs=3)
@modal.wsgi_app()
def flask_app():
    import sys
    sys.path.insert(0, "/app")

    # Load YOLO model once at container startup
    try:
        from services.yolo_service import load_model
        load_model()
    except Exception as err:
        print("Model preload warning:", err)

    from app import create_app
    return create_app("production")