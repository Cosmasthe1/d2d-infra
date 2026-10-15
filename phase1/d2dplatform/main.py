"""uvicorn entrypoint:  uvicorn d2dplatform.main:app --port 8080"""
import os
from .app import create_app
app = create_app(os.environ.get("D2D_DB", "d2d.db"))
