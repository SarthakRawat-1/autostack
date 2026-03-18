"""
Project endpoints for AutoStack API

Implements CRUD operations for projects and initiates workflows.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from api.schemas import ProjectCreateRequest, ProjectResponse, SuccessResponse, BranchInfo
from models.database import get_db
from models.models import Project, ProjectStatus, Task, User
from workflows.graph import execute_workflow
from workflows.cloud_graph import execute_cloud_workflow
from services.credentials import get_credential_manager
from utils.progress import calculate_progress
from api.deps import get_current_user

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

import re
import logging
logger = logging.getLogger(__name__)


def parse_repo_from_url(repo_url: str) -> str:
    """Extract owner/repo from GitHub URL"""
    repo_url = repo_url.rstrip("/").replace(".git", "")
    match = re.search(r"github\.com[/:]([^/]+/[^/]+)", repo_url)
    if match:
        return match.group(1)
    raise ValueError(f"Invalid GitHub URL: {repo_url}")


@router.get("/github/branches", response_model=List[BranchInfo])
async def get_repo_branches(repo_url: str, current_user: User = Depends(get_current_user)):
    """
    Fetch branches from a GitHub repository URL.
    Used by import flow to let user select a branch.
    """
    from services.github_client import GitHubClient, GitHubClientError
    from api.config import settings

    try:
        repo = parse_repo_from_url(repo_url)
        github_client = GitHubClient(token=settings.github_token)
        
        # Get repo info for default branch
        repo_info = await github_client.get_repository(repo)
        default_branch = repo_info.default_branch
        
        # Get all branches
        branches = await github_client.list_branches(repo)
        
        return [
            BranchInfo(name=b.name, is_default=(b.name == default_branch))
            for b in branches
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GitHubClientError as e:
        raise HTTPException(status_code=400, detail=f"GitHub error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch branches: {str(e)}")

async def run_workflow_background(
    project_id: str, 
    project_name: str, 
    description: str, 
    execution_mode: str, 
    credentials: dict,
    is_import_mode: bool = False,
    project_type: str = "software",
    repository_url: Optional[str] = None,
    source_branch: Optional[str] = None
):
    """Run workflow in background with detailed logging"""
    from utils.logging import log_to_db, log_exception
    
    logger.info(f"=== STARTING WORKFLOW for project {project_id} ===")
    logger.info(f"Project: {project_name}")
    logger.info(f"Mode: {execution_mode}")
    logger.info(f"Type: {project_type}")
    
    log_to_db(project_id, "INFO", f"Starting {project_type} workflow for {project_name}")
    
    try:
        if project_type == "infrastructure":
            result = await execute_cloud_workflow(
                project_id=project_id,
                project_name=project_name,
                request=description,
                credentials=credentials,
                repository_url=repository_url
            )
        else:
            result = await execute_workflow(
                project_id=project_id,
                project_name=project_name,
                project_description=description,
                execution_mode=execution_mode,
                credentials=credentials,
                is_import_mode=is_import_mode,
                repository_url=repository_url,
                source_branch=source_branch
            )
            
        logger.info(f"=== WORKFLOW COMPLETED for project {project_id} ===")
        logger.info(f"Final status: {result.get('status', 'unknown')}")
        log_to_db(project_id, "INFO", f"Workflow completed with status: {result.get('status', 'unknown')}")
        
    except Exception as e:
        logger.error(f"=== WORKFLOW FAILED for project {project_id} ===")
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        log_exception(project_id, "Workflow execution failed", e)
        
        # Update project status to FAILED
        from models.database import get_db_context
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=project_id).first()
            if project:
                project.status = ProjectStatus.FAILED
                db.commit()
                logger.info(f"Project {project_id} marked as FAILED")


def ensure_timezone(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime has timezone info (UTC)"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: ProjectCreateRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new project and start the workflow
    
    - **name**: Project name
    - **description**: Detailed project description
    - **execution_mode**: "auto" (full workflow) or "manual" (step-by-step)
    - **credentials**: Optional user credentials (GitHub token, webhooks)
    
    Returns the created project. Workflow runs in background.
    """
    try:
        # Generate project ID
        project_id = str(uuid.uuid4())
        
        # Create Project in database with execution_mode
        project = Project(
            id=project_id,
            user_id=current_user.id,
            name=request.name,
            description=request.description,
            repository_url=request.repository_url,
            source_branch=request.source_branch,
            execution_mode=request.execution_mode,
            requires_approval=0,
            use_system_credentials=1,
            project_type=request.project_type
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Create initial Project Manager task ONLY for software projects
        # Infra projects use specific nodes
        if request.project_type != "infrastructure":
            from models.models import Task, TaskStatus
            pm_task = Task(
                project_id=project.id,
                agent_role="project_manager",
                status=TaskStatus.PENDING,
                priority=1,
                description="Analyze requirements and create task breakdown",
                requirements=request.description
            )
            db.add(pm_task)
            db.commit()
        
        # Store credentials if provided (use credential_manager)
        credentials_dict = {}
        if request.credentials:
            credential_manager = get_credential_manager()
            credential_manager.store_credentials(
                project,
                github_token=request.credentials.get("github_token"),
                slack_webhook=request.credentials.get("slack_webhook_url"),
                discord_webhook=request.credentials.get("discord_webhook_url")
            )

            # Pass all credentials (including Azure) for cloud workflows
            credentials_dict = request.credentials.copy()
        
        # Start workflow in background
        logger.info(f"Adding background task for project {project.id}")
        
        # Determine if this is an import (existing repo) or new project
        is_import_mode = bool(request.repository_url)
        
        background_tasks.add_task(
            run_workflow_background,
            project_id=project.id,
            project_name=project.name,
            description=project.description,
            execution_mode=project.execution_mode,
            credentials=credentials_dict,
            is_import_mode=is_import_mode,
            project_type=request.project_type,
            repository_url=request.repository_url,
            source_branch=request.source_branch
        )
        
        logger.info(f"Background task added for project {project.id}")
        
        # Return project response
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status.value,
            current_phase=project.current_phase,
            execution_mode=project.execution_mode,
            requires_approval=bool(project.requires_approval),
            current_interrupt=project.current_interrupt,
            repository_url=project.repository_url,
            project_type=project.project_type,
            created_at=ensure_timezone(project.created_at),
            updated_at=ensure_timezone(project.updated_at),
            completed_at=ensure_timezone(project.completed_at),
            progress=calculate_progress(project.tasks)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all projects with optional filtering
    
    - **status**: Filter by status (INITIALIZING, DEVELOPING, etc.)
    - **limit**: Number of results (default 10)
    - **offset**: Pagination offset (default 0)
    """
    try:
        query = db.query(Project).filter(Project.user_id == current_user.id)
        
        if status:
            query = query.filter(Project.status == status)
        
        projects = query.order_by(Project.created_at.desc()).offset(offset).limit(limit).all()
        
        # Calculate progress for each project
        responses = []
        for project in projects:
            responses.append(ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                status=project.status.value,
                current_phase=project.current_phase,
                execution_mode=project.execution_mode,
                requires_approval=bool(project.requires_approval),
                current_interrupt=project.current_interrupt,
                repository_url=project.repository_url,
                project_type=project.project_type,
                created_at=ensure_timezone(project.created_at),
                updated_at=ensure_timezone(project.updated_at),
                completed_at=ensure_timezone(project.completed_at),
                progress=calculate_progress(project.tasks)
            ))
        
        return responses
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get detailed project information
    
    Returns project with progress information.
    """
    try:
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Calculate progress
        progress = calculate_progress(project.tasks)
        
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status.value,
            current_phase=project.current_phase,
            execution_mode=project.execution_mode,
            requires_approval=bool(project.requires_approval),
            current_interrupt=project.current_interrupt,
            repository_url=project.repository_url,
            project_type=project.project_type,
            created_at=ensure_timezone(project.created_at),
            updated_at=ensure_timezone(project.updated_at),
            completed_at=ensure_timezone(project.completed_at),
            progress=progress
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")


@router.delete("/{project_id}", response_model=SuccessResponse)
async def delete_project(project_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Cancel and delete a project
    
    Cancels the workflow if running and deletes the project.
    """
    try:
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Call cancel_workflow(project_id)
        from workflows.graph import cancel_workflow
        await cancel_workflow(project_id)
        
        # Delete project from database
        db.delete(project)
        db.commit()
        
        # Return success message
        return SuccessResponse(
            message="Project deleted successfully",
            data={"project_id": project_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")