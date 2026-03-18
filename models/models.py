from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship
import enum
import uuid
from models.database import Base

class ProjectStatus(str, enum.Enum):
    INITIALIZING = "INITIALIZING"
    PLANNING = "PLANNING"
    DEVELOPING = "DEVELOPING"
    TESTING = "TESTING"
    REVIEWING = "REVIEWING"
    DOCUMENTING = "DOCUMENTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    settings = relationship("SystemSettings", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    repository_url = Column(String(512), nullable=True)
    source_branch = Column(String(255), nullable=True)  # Branch for import mode
    status = Column(SQLEnum(ProjectStatus), nullable=False, default=ProjectStatus.INITIALIZING)
    current_phase = Column(String(100), nullable=True)
    notification_channel = Column(String(255), nullable=True)
    project_type = Column(String(50), nullable=False, default="software") # software or infrastructure

    execution_mode = Column(String(20), nullable=False, default="auto")
    requires_approval = Column(Integer, nullable=False, default=0)  
    current_interrupt = Column(String(100), nullable=True)  
 
    github_token = Column(Text, nullable=True)  
    slack_webhook_url = Column(String(512), nullable=True)  
    discord_webhook_url = Column(String(512), nullable=True) 
    use_system_credentials = Column(Integer, nullable=False, default=1)  
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    workflow_states = relationship("WorkflowState", back_populates="project", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="project", cascade="all, delete-orphan")
    metrics = relationship("Metric", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, status={self.status})>"


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_role = Column(String(100), nullable=False)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    priority = Column(Integer, default=0, nullable=False)
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)
    dependencies = Column(JSON, default=list, nullable=False) 
    result = Column(JSON, nullable=True)  
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="tasks")
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, agent_role={self.agent_role}, status={self.status})>"


class WorkflowState(Base):
    __tablename__ = "workflow_states"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    state_data = Column(JSON, nullable=False)  
    phase = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="workflow_states")
    
    def __repr__(self) -> str:
        return f"<WorkflowState(id={self.id}, project_id={self.project_id}, phase={self.phase})>"


class Log(Base):
    __tablename__ = "logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_role = Column(String(100), nullable=True)
    level = Column(SQLEnum(LogLevel), nullable=False, default=LogLevel.INFO)
    message = Column(Text, nullable=False)
    extra_data = Column(JSON, nullable=True)  
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="logs")
    
    def __repr__(self) -> str:
        return f"<Log(id={self.id}, level={self.level}, message={self.message[:50]})>"


class Metric(Base):
    __tablename__ = "metrics"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    metric_type = Column(String(100), nullable=False)  
    metric_name = Column(String(255), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)  
    extra_data = Column(JSON, nullable=True)  
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="metrics")
    
    def __repr__(self) -> str:
        return f"<Metric(id={self.id}, type={self.metric_type}, name={self.metric_name}, value={self.value})>"


class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    groq_api_key = Column(Text, nullable=True)
    openrouter_api_key = Column(Text, nullable=True)

    github_token = Column(Text, nullable=True)

    slack_webhook_url = Column(String(512), nullable=True)
    discord_webhook_url = Column(String(512), nullable=True)

    azure_subscription_id = Column(String(255), nullable=True)
    azure_tenant_id = Column(String(255), nullable=True)
    azure_client_id = Column(String(255), nullable=True)
    azure_client_secret = Column(Text, nullable=True)

    is_configured = Column(Integer, nullable=False, default=0) 
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="settings")
    
    def __repr__(self) -> str:
        return f"<SystemSettings(id={self.id}, is_configured={bool(self.is_configured)})>"
