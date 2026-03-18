"""
Log endpoints for AutoStack API

Retrieve project logs and system events.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from api.schemas import LogResponse
from models.database import get_db
from models.models import Log, Project, User
from api.deps import get_current_user

router = APIRouter(prefix="/api/v1/projects/{project_id}/logs", tags=["logs"])


@router.get("", response_model=List[LogResponse])
async def get_project_logs(
    project_id: str,
    level: Optional[str] = None,
    agent_role: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get logs for a project
    
    - **level**: Filter by log level (INFO, ERROR, etc.)
    - **agent_role**: Filter by agent
    - **limit**: Number of results (default 50)
    - **offset**: Pagination offset
    """
    try:
        # Verify project belongs to user
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        query = db.query(Log).filter(Log.project_id == project_id)
        
        if level:
            query = query.filter(Log.level == level)
        
        if agent_role:
            query = query.filter(Log.agent_role == agent_role)
        
        # Order by timestamp DESC
        logs = query.order_by(Log.created_at.desc()).offset(offset).limit(limit).all()
        
        # Return list of LogResponse
        log_responses = []
        for log in logs:
            log_responses.append(LogResponse(
                id=log.id,
                level=log.level.value,
                message=log.message,
                agent_role=log.agent_role,
                timestamp=log.created_at,
                extra_data=log.extra_data
            ))
        
        return log_responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")