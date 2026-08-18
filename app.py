"""Render entrypoint for `gunicorn app:app` from the repository root."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
APP_FILE = BACKEND_DIR / "app.py"

if not APP_FILE.exists():
    raise RuntimeError(f"Flask app not found at {APP_FILE}")

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

spec = importlib.util.spec_from_file_location("flower_shop_backend", APP_FILE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load Flask app from {APP_FILE}")

module = importlib.util.module_from_spec(spec)
sys.modules["flower_shop_backend"] = module
spec.loader.exec_module(module)
app = module.app
