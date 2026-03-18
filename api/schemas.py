"""
Pydantic schemas for AutoStack API

Request/response models for all API endpoints.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# Request schemas
class ProjectCreateRequest(BaseModel):
    name: str
    description: str
    repository_url: Optional[str] = None
    source_branch: Optional[str] = None  # Branch for import mode
    execution_mode: str = "auto"  # "auto" or "manual"
    project_type: str = "software" # "software" or "infrastructure"
    credentials: Optional[Dict[str, str]] = None


class CredentialsInput(BaseModel):
    github_token: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    # Azure credentials
    azure_subscription_id: Optional[str] = None
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None


class WorkflowContinueRequest(BaseModel):
    decision: Literal["approve", "request_changes", "cancel"] = "approve"
    feedback: Optional[str] = None


# Response schemas
class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    current_phase: Optional[str]
    execution_mode: str
    requires_approval: bool
    current_interrupt: Optional[str]
    repository_url: Optional[str]
    project_type: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    progress: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: str
    project_id: str
    description: str
    agent_role: str
    status: str
    priority: int
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PaginatedTaskResponse(BaseModel):
    """Paginated wrapper for task lists"""
    items: List[TaskResponse]
    total: int
    limit: int
    offset: int


class WorkflowStateResponse(BaseModel):
    project_id: str
    status: str
    current_phase: Optional[str]
    requires_approval: bool
    current_interrupt: Optional[str]
    execution_mode: str
    tasks: List[TaskResponse]
    progress: Dict[str, Any]


class LogResponse(BaseModel):
    id: str
    level: str
    message: str
    agent_role: Optional[str]
    timestamp: datetime
    extra_data: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class BranchInfo(BaseModel):
    """Branch information for repository"""
    name: str
    is_default: bool = False


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SuccessResponse(BaseModel):
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# System Settings schemas
class SystemSettingsRequest(BaseModel):
    """Request schema for updating system settings"""
    groq_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    github_token: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    azure_subscription_id: Optional[str] = None
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None


class SystemSettingsResponse(BaseModel):
    """Response schema for system settings (keys are masked)"""
    id: str
    groq_api_key_set: bool = False
    openrouter_api_key_set: bool = False
    github_token_set: bool = False
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    azure_subscription_id: Optional[str] = None
    azure_tenant_id_set: bool = False
    azure_client_id_set: bool = False
    azure_client_secret_set: bool = False
    is_configured: bool = False
    updated_at: datetime
    
    class Config:
        from_attributes = True