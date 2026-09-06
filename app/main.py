import os
import sys

# Ensure root directory is on Python path so root main.py is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app, create_application, lifespan

__all__ = ["app", "create_application", "lifespan"]
