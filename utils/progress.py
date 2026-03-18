# File: utils/progress.py
"""
Shared progress calculation utility.

Provides a single ``calculate_progress`` function used by both the
projects route and workflow route to avoid code duplication.
"""

from typing import Any, Dict, List


def calculate_progress(tasks: List[Any]) -> Dict[str, Any]:
    """
    Calculate workflow progress from a list of task objects.

    Accepts either SQLAlchemy Task model instances or any object whose
    ``status`` attribute (or ``.value``) is one of
    ``"COMPLETED"``, ``"FAILED"``, ``"PENDING"``.

    Returns:
        Dict with total_tasks, completed_tasks, failed_tasks,
        pending_tasks, and percentage.
    """
    total = len(tasks)
    if total == 0:
        return {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "pending_tasks": 0,
            "percentage": 0,
        }

    def _status(t: Any) -> str:
        s = t.status
        return s.value if hasattr(s, "value") else str(s)

    completed = sum(1 for t in tasks if _status(t) == "COMPLETED")
    failed = sum(1 for t in tasks if _status(t) == "FAILED")
    pending = sum(1 for t in tasks if _status(t) == "PENDING")
    percentage = (completed / total * 100) if total > 0 else 0

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "pending_tasks": pending,
        "percentage": round(percentage, 2),
    }
