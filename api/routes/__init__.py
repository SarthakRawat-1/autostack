"""
API Routes Package

This package contains all the route handlers for the AutoStack API.
"""

from api.routes import projects, tasks, workflow, logs, health, settings, auth

__all__ = ["projects", "tasks", "workflow", "logs", "health", "settings", "auth"]
