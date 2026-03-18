"""
Workflow control endpoints for AutoStack API

Manage workflow state, continuation, and cancellation.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from api.schemas import WorkflowStateResponse, WorkflowContinueRequest, SuccessResponse, TaskResponse
from models.database import get_db
from models.models import Project, Task, User
from workflows.graph import resume_workflow, cancel_workflow
from utils.progress import calculate_progress
from api.deps import get_current_user

router = APIRouter(prefix="/api/v1/projects/{project_id}/workflow", tags=["workflow"])


@router.get("", response_model=WorkflowStateResponse)
async def get_workflow_state(project_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get current workflow state
    
    Returns workflow status, current phase, and whether approval is needed.
    """
    try:
        # Query project and tasks
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        
        # Build task responses
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
        
        # Calculate progress
        progress = calculate_progress(tasks)
        
        # Build WorkflowStateResponse
        return WorkflowStateResponse(
            project_id=project.id,
            status=project.status.value,
            current_phase=project.current_phase,
            requires_approval=bool(project.requires_approval),
            current_interrupt=project.current_interrupt,
            execution_mode=project.execution_mode,
            tasks=task_responses,
            progress=progress
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow state: {str(e)}")


@router.post("/continue", response_model=SuccessResponse)
async def continue_workflow(
    project_id: str, 
    request: WorkflowContinueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Continue an interrupted workflow after user approval
    
    - **approved**: Whether user approved continuation (default true)
    
    Only works if workflow is in interrupted state (requires_approval=true).
    """
    try:
        # Check if project requires approval
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if not project.requires_approval:
            raise HTTPException(status_code=400, detail="Project does not require approval")
        
        if project.project_type == "infrastructure":
             from workflows.cloud_graph import resume_cloud_workflow
             
             result = await resume_cloud_workflow(project_id, action=request.decision)
             
             return SuccessResponse(
                message="Cloud workflow resumed",
                data=result
             )

        # Call resume_workflow(project_id, request.approved)
        from services.credentials import get_credential_manager
        credential_manager = get_credential_manager()
        credentials = credential_manager.get_credentials_for_project(project)
        
        result = await resume_workflow(
            project_id=project_id,
            approved=(request.decision == "approve"),
            decision=request.decision,
            feedback=request.feedback,
            credentials=credentials
        )
        
        # Return success message with next phase info
        return SuccessResponse(
            message="Workflow continued successfully",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to continue workflow: {str(e)}")


@router.post("/cancel", response_model=SuccessResponse)
async def cancel_workflow_endpoint(project_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Cancel a running or interrupted workflow
    
    Sets project status to CANCELLED.
    """
    try:
        # Check if project exists
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Call cancel_workflow(project_id)
        result = await cancel_workflow(project_id)
        
        # Return success message
        return SuccessResponse(
            message="Workflow cancelled successfully",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel workflow: {str(e)}")