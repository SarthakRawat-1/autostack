# File: workflows/state.py
"""
Workflow State Schema

Defines the state structure for LangGraph workflow orchestration.
Includes state types, enums, and helper functions.

Implements: Requirements 1.2, 1.3, 8.1
"""

from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class WorkflowPhase(str, Enum):
    """
    Workflow execution phases
    
    Defines the sequential phases of the AutoStack workflow.
    """
    INITIALIZING = "initializing"
    PLANNING = "planning"
    DEVELOPING = "developing"
    TESTING = "testing"
    DOCUMENTING = "documenting"
    REVIEWING = "reviewing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    
    # Infrastructure Phases
    INFRA_PLANNING = "infra_planning"
    INFRA_GENERATION = "infra_generation"
    INFRA_VALIDATION = "infra_validation"
    INFRA_APPLYING = "infra_applying"
    
    def __str__(self) -> str:
        return self.value


class WorkflowStatus(str, Enum):
    """
    Workflow execution status
    
    Indicates the current status of workflow execution.
    """
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
    def __str__(self) -> str:
        return self.value


class WorkflowState(TypedDict, total=False):
    """
    LangGraph workflow state
    
    Complete state structure for workflow orchestration.
    LangGraph will manage state transitions between nodes.
    
    Implements: Requirements 1.2, 1.3, 8.1
    
    Attributes:
        project_id: Unique project identifier
        project_name: Human-readable project name
        project_description: Full project description
        repository: GitHub repository name (owner/repo)
        repository_url: Full GitHub repository URL
        
        current_phase: Current workflow phase
        status: Current workflow status
        
        tasks: List of all task IDs for this project
        pending_tasks: List of pending task IDs
        in_progress_tasks: List of in-progress task IDs
        completed_tasks: List of completed task IDs
        failed_tasks: List of failed task IDs
        
        current_task_id: ID of task currently being processed
        
        agents: Dictionary of initialized agent instances by role
        
        errors: List of error messages encountered
        retry_count: Number of retry attempts for current operation
        max_retries: Maximum retry attempts allowed
        
        results: Accumulated results from each phase
        phase_history: History of phase transitions
        
        started_at: Workflow start timestamp
        updated_at: Last update timestamp
        completed_at: Workflow completion timestamp
        
        metadata: Additional metadata for workflow execution
    """
    # Project information
    project_id: str
    project_name: str
    project_description: str
    repository: Optional[str]
    repository_url: Optional[str]
    source_branch: Optional[str]  # Branch for import mode
    
    # PR information (set after developer creates PR)
    pr_number: Optional[int]
    pr_url: Optional[str]
    branch_name: Optional[str]
    
    # Workflow state
    current_phase: WorkflowPhase
    status: WorkflowStatus
    
    # Task tracking
    tasks: List[str]
    pending_tasks: List[str]
    in_progress_tasks: List[str]
    completed_tasks: List[str]
    failed_tasks: List[str]
    current_task_id: Optional[str]
    
    # Agent instances (not serialized to DB)
    agents: Dict[str, Any]
    
    # Error handling
    errors: List[Dict[str, Any]]
    retry_count: int
    max_retries: int
    
    # Results and history
    results: Dict[str, Any]
    phase_history: List[Dict[str, Any]]
    
    # Timestamps
    started_at: str
    updated_at: str
    completed_at: Optional[str]
    
    # Additional metadata
    metadata: Dict[str, Any]
    
    # Human-in-the-Loop Feedback
    user_feedback: List[str]

    # Feedback Loop Tracking
    requires_feedback_approval: bool  # Whether current phase requires feedback approval
    feedback_loop_target: Optional[str]  # Target node for feedback loop (e.g., "plan", "develop", "test", "document")

    # Import Mode - True if using existing repository
    is_import_mode: bool


class InfrastructureState(TypedDict, total=False):
    """
    State for Infrastructure Provisioning Workflow.
    """
    project_id: str
    project_name: str
    request: str
    repository: Optional[str]
    repository_url: Optional[str]
    credentials_path: Optional[str] # Path to Azure credentials (deprecated, use azure_credentials)
    azure_credentials: Dict[str, str] # Azure Service Principal: tenant_id, client_id, client_secret
    
    # Infrastructure Data
    resource_plan: Dict[str, Any]      # JSON from InfraArchitect
    terraform_code: Dict[str, str]     # Files from DevOps
    security_report: Dict[str, Any]    # JSON from SecOps
    cost_estimate: Dict[str, Any]      # JSON from SecOps
    provisioning_output: Dict[str, Any] # Stdout/Stderr from terraform apply
    
    # Workflow Status
    current_phase: WorkflowPhase
    status: WorkflowStatus
    errors: List[Dict[str, Any]]
    
    # Human Feedback
    user_feedback: List[str]
    requires_approval: bool
    
    # Branch where Terraform code was committed (for apply phase)
    terraform_branch: Optional[str]
    
    metadata: Dict[str, Any]
    


def create_initial_state(
    project_id: str,
    project_name: str,
    project_description: str,
    repository: Optional[str] = None,
    repository_url: Optional[str] = None,
    source_branch: Optional[str] = None,
    max_retries: int = 3,
    is_import_mode: bool = False
) -> WorkflowState:
    """
    Create initial workflow state
    
    Args:
        project_id: Project identifier
        project_name: Project name
        project_description: Project description
        repository: Optional repository name
        repository_url: Optional repository URL
        max_retries: Maximum retry attempts
        is_import_mode: True if importing existing repo, False for new project
        
    Returns:
        Initial WorkflowState dictionary
    """
    now = datetime.utcnow().isoformat()
    
    return WorkflowState(
        project_id=project_id,
        project_name=project_name,
        project_description=project_description,
        repository=repository,
        repository_url=repository_url,
        source_branch=source_branch,
        
        # PR fields (set during development phase)
        pr_number=None,
        pr_url=None,
        branch_name=None,
        
        current_phase=WorkflowPhase.INITIALIZING,
        status=WorkflowStatus.PENDING,
        
        tasks=[],
        pending_tasks=[],
        in_progress_tasks=[],
        completed_tasks=[],
        failed_tasks=[],
        current_task_id=None,
        
        agents={},
        
        errors=[],
        retry_count=0,
        max_retries=max_retries,
        
        results={},
        phase_history=[],
        
        started_at=now,
        updated_at=now,
        completed_at=None,
        
        metadata={},
        
        # Human-in-the-Loop
        user_feedback=[],

        # Feedback Loop Tracking
        requires_feedback_approval=False,
        feedback_loop_target=None,

        # Import mode flag
        is_import_mode=is_import_mode
    )


def update_phase(
    state: WorkflowState,
    new_phase: WorkflowPhase,
    status: Optional[WorkflowStatus] = None
) -> WorkflowState:
    """
    Update workflow phase and record in history
    
    Args:
        state: Current workflow state
        new_phase: New phase to transition to
        status: Optional new status
        
    Returns:
        Updated workflow state
    """
    now = datetime.utcnow().isoformat()
    
    # Record phase transition in history
    phase_history = state.get("phase_history", [])
    phase_history.append({
        "from_phase": str(state.get("current_phase", "")),
        "to_phase": str(new_phase),
        "timestamp": now
    })
    
    # Update state
    state["current_phase"] = new_phase
    state["phase_history"] = phase_history
    state["updated_at"] = now
    
    if status:
        state["status"] = status
    
    return state


def add_error(state: WorkflowState, error: str) -> WorkflowState:
    """
    Add error to workflow state
    
    Args:
        state: Current workflow state
        error: Error message
        
    Returns:
        Updated workflow state
    """
    errors = state.get("errors", [])
    errors.append({
        "message": error,
        "timestamp": datetime.utcnow().isoformat(),
        "phase": str(state.get("current_phase", "unknown"))
    })
    state["errors"] = errors
    state["updated_at"] = datetime.utcnow().isoformat()
    
    return state


def increment_retry(state: WorkflowState) -> WorkflowState:
    """
    Increment retry counter
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    state["retry_count"] = state.get("retry_count", 0) + 1
    state["updated_at"] = datetime.utcnow().isoformat()
    
    return state


def reset_retry(state: WorkflowState) -> WorkflowState:
    """
    Reset retry counter
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    state["retry_count"] = 0
    state["updated_at"] = datetime.utcnow().isoformat()
    
    return state


def is_retry_exhausted(state: WorkflowState) -> bool:
    """
    Check if retry attempts are exhausted
    
    Args:
        state: Current workflow state
        
    Returns:
        True if retries exhausted, False otherwise
    """
    return state.get("retry_count", 0) >= state.get("max_retries", 3)


def mark_task_completed(state: WorkflowState, task_id: str) -> WorkflowState:
    """
    Mark task as completed
    
    Args:
        state: Current workflow state
        task_id: Task identifier
        
    Returns:
        Updated workflow state
    """
    # Remove from pending
    pending = state.get("pending_tasks", [])
    if task_id in pending:
        pending.remove(task_id)
    state["pending_tasks"] = pending
    
    # Remove from in-progress
    in_progress = state.get("in_progress_tasks", [])
    if task_id in in_progress:
        in_progress.remove(task_id)
    state["in_progress_tasks"] = in_progress
    
    # Remove from failed (important for feedback-loop retries)
    failed = state.get("failed_tasks", [])
    if task_id in failed:
        failed.remove(task_id)
    state["failed_tasks"] = failed
    
    # Add to completed
    completed = state.get("completed_tasks", [])
    if task_id not in completed:
        completed.append(task_id)
    state["completed_tasks"] = completed
    
    state["updated_at"] = datetime.utcnow().isoformat()
    
    return state


def mark_task_failed(state: WorkflowState, task_id: str) -> WorkflowState:
    """
    Mark task as failed
    
    Args:
        state: Current workflow state
        task_id: Task identifier
        
    Returns:
        Updated workflow state
    """
    # Remove from pending
    pending = state.get("pending_tasks", [])
    if task_id in pending:
        pending.remove(task_id)
    state["pending_tasks"] = pending
    
    # Remove from in-progress
    in_progress = state.get("in_progress_tasks", [])
    if task_id in in_progress:
        in_progress.remove(task_id)
    state["in_progress_tasks"] = in_progress
    
    # Add to failed
    failed = state.get("failed_tasks", [])
    if task_id not in failed:
        failed.append(task_id)
    state["failed_tasks"] = failed
    
    state["updated_at"] = datetime.utcnow().isoformat()
    
    return state


def get_next_pending_task(state: WorkflowState) -> Optional[str]:
    """
    Get next pending task ID
    
    Args:
        state: Current workflow state
        
    Returns:
        Next pending task ID or None
    """
    pending = state.get("pending_tasks", [])
    return pending[0] if pending else None


def has_pending_tasks(state: WorkflowState) -> bool:
    """
    Check if there are pending tasks
    
    Args:
        state: Current workflow state
        
    Returns:
        True if pending tasks exist, False otherwise
    """
    return len(state.get("pending_tasks", [])) > 0


def all_tasks_completed(state: WorkflowState) -> bool:
    """
    Check if all tasks are completed
    
    Args:
        state: Current workflow state
        
    Returns:
        True if all tasks completed, False otherwise
    """
    total_tasks = len(state.get("tasks", []))
    completed_tasks = len(state.get("completed_tasks", []))
    
    return total_tasks > 0 and total_tasks == completed_tasks


def has_failed_tasks(state: WorkflowState) -> bool:
    """
    Check if there are failed tasks
    
    Args:
        state: Current workflow state
        
    Returns:
        True if failed tasks exist, False otherwise
    """
    return len(state.get("failed_tasks", [])) > 0
