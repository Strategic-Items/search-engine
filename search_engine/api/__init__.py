"""HTTP 서피스. ``search_engine.api:app``는 uvicorn 진입점으로 유지된다."""

from search_engine.api.routes import app

__all__ = ["app"]
