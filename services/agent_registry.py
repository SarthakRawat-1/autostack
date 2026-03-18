# File: services/agent_registry.py
"""
Per-workflow agent registry.

Replaces the global ``_AGENT_REGISTRY`` / ``_CLOUD_AGENT_REGISTRY`` module dicts
with a thread-safe, per-project scoped registry that cleans up after workflow
completion.  This avoids unbounded memory growth and eliminates the risk of
concurrent workflows leaking agents between projects.
"""

import logging
import threading
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Thread-safe, per-project agent registry."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    # -- read --
    def get(self, project_id: str) -> Dict[str, Any]:
        """Return agent map for *project_id* (empty dict if missing)."""
        with self._lock:
            return self._store.get(project_id, {})

    # -- write --
    def register(self, project_id: str, agents: Dict[str, Any]) -> None:
        """Store *agents* keyed by *project_id*."""
        with self._lock:
            self._store[project_id] = agents
        logger.debug("Registered %d agents for project %s", len(agents), project_id)

    # -- cleanup --
    def remove(self, project_id: str) -> None:
        """Remove all agents for *project_id*, releasing memory."""
        with self._lock:
            removed = self._store.pop(project_id, None)
        if removed:
            logger.debug("Removed agents for project %s", project_id)

    @contextmanager
    def scoped(self, project_id: str, agents: Dict[str, Any]):
        """
        Context manager that registers agents and guarantees cleanup.

        Usage::

            with registry.scoped(project_id, agents):
                final = await graph.ainvoke(state, config)
        """
        self.register(project_id, agents)
        try:
            yield
        finally:
            self.remove(project_id)

    def __len__(self) -> int:  # pragma: no cover – diagnostics
        with self._lock:
            return len(self._store)


# Singleton instances – one per workflow type
software_registry = AgentRegistry()
cloud_registry = AgentRegistry()
