"""
Task endpoints for AutoStack API

Manage project tasks and their status.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from api.schemas import TaskResponse, PaginatedTaskResponse
from models.database import get_db
from models.models import Task, Project, User
from api.deps import get_current_user

router = APIRouter(prefix="/api/v1", tags=["tasks"])


@router.get("/projects/{project_id}/tasks", response_model=PaginatedTaskResponse)
async def list_project_tasks(
    project_id: str,
    agent_role: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all tasks for a project
    
    - **agent_role**: Filter by agent (developer, qa, documentation)
    - **status**: Filter by status (PENDING, COMPLETED, etc.)
    - **limit**: Number of results per page (default 50, max 200)
    - **offset**: Pagination offset (default 0)
    """
    try:
        # Verify project belongs to user
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        query = db.query(Task).filter(Task.project_id == project_id)
        
        if agent_role:
            query = query.filter(Task.agent_role == agent_role)
        
        if status:
            query = query.filter(Task.status == status)
        
        total = query.count()
        tasks = query.order_by(Task.priority).offset(offset).limit(limit).all()
        
        # Return list of TaskResponse
        task_responses = []
        for task in tasks:
            task_responses.append(TaskResponse(
                id=task.id,
                project_id=task.project_id,
                description=task.description,
                agent_role=task.agent_role,
                status=task.status.value,
                priority=task.priority,
                result=task.result,
                error_message=task.error_message,
                created_at=task.created_at,
                completed_at=task.completed_at
            ))
        
        return PaginatedTaskResponse(
            items=task_responses,
            total=total,
            limit=limit,
            offset=offset,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get detailed task information
    
    Returns task with result data if completed.
    """
    try:
        task = db.query(Task).join(Project).filter(
            Task.id == task_id,
            Project.user_id == current_user.id
        ).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Return TaskResponse
        return TaskResponse(
            id=task.id,
            project_id=task.project_id,
            description=task.description,
            agent_role=task.agent_role,
            status=task.status.value,
            priority=task.priority,
            result=task.result,
            error_message=task.error_message,
            created_at=task.created_at,
            completed_at=task.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")