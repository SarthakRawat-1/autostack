"""
Health check endpoints for AutoStack API

Monitor system status and statistics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas import SuccessResponse
from models.database import get_db, check_database_health
from models.models import Project, Task

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """
    Health check endpoint
    
    Verifies database connectivity and returns system status.
    """
    # Test database connection
    db_healthy = check_database_health()
    
    status = "healthy" if db_healthy else "degraded"
    
    return SuccessResponse(
        message=f"System is {status}",
        data={
            "database": "connected" if db_healthy else "disconnected",
            "status": status
        }
    )


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """
    Get system-wide statistics
    
    Returns counts of projects by status, total tasks, etc.
    """
    try:
        # Count projects by status
        project_stats = {}
        for status in ["INITIALIZING", "PLANNING", "DEVELOPING", "TESTING", 
                      "REVIEWING", "DOCUMENTING", "COMPLETED", "FAILED", "CANCELLED"]:
            count = db.query(Project).filter(Project.status == status).count()
            project_stats[status.lower()] = count
        
        # Count total tasks
        total_tasks = db.query(Task).count()
        
        # Count tasks by status
        task_stats = {}
        for status in ["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"]:
            count = db.query(Task).filter(Task.status == status).count()
            task_stats[status.lower()] = count
        
        return {
            "projects": project_stats,
            "tasks": {
                "total": total_tasks,
                "by_status": task_stats
            }
        }
        
    except Exception as e:
        return {
            "error": f"Failed to get stats: {str(e)}"
        }