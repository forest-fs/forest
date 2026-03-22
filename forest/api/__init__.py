"""
FastAPI application factory (health, readiness, and Slack webhook routes).
"""

from forest.api.app import create_app

__all__ = ["create_app"]
