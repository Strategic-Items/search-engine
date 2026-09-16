"""HTTP surface. ``search_engine.api:app`` stays the uvicorn entry point."""

from search_engine.api.routes import app

__all__ = ["app"]
