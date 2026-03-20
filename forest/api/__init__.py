"""
FastAPI application factory (health and readiness endpoints only in MVP).
"""

from forest.api.app import create_app

__all__ = ["create_app"]
