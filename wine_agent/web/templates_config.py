"""Jinja2 templates configuration for Wine Agent."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Jinja2 templates instance for use in routes
templates = Jinja2Templates(directory=TEMPLATES_DIR)
