import logging
import sys
import traceback
from typing import Optional, Dict, Any
from enum import Enum
from models.database import get_db_context
from models.models import Log, LogLevel

def setup_console_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

setup_console_logging()

logger = logging.getLogger(__name__)


class LogType(str, Enum):
    WORKFLOW_START = "workflow_start"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_FAILED = "workflow_failed"
    PHASE_CHANGE = "phase_change"

    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"

    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    TASK_PROGRESS = "task_progress"

    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    LLM_ERROR = "llm_error"

    GITHUB_REPO_CREATE = "github_repo_create"
    GITHUB_BRANCH_CREATE = "github_branch_create"
    GITHUB_COMMIT = "github_commit"
    GITHUB_PR_CREATE = "github_pr_create"
    GITHUB_ERROR = "github_error"

    MEMORY_STORE = "memory_store"
    MEMORY_RETRIEVE = "memory_retrieve"

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"

LOG_TYPE_ICONS = {
    LogType.WORKFLOW_START: "",
    LogType.WORKFLOW_COMPLETE: "",
    LogType.WORKFLOW_FAILED: "",
    LogType.PHASE_CHANGE: "",
    LogType.AGENT_START: "",
    LogType.AGENT_COMPLETE: "",
    LogType.AGENT_ERROR: "",
    LogType.TASK_START: "",
    LogType.TASK_COMPLETE: "",
    LogType.TASK_FAILED: "",
    LogType.TASK_PROGRESS: "",
    LogType.LLM_REQUEST: "",
    LogType.LLM_RESPONSE: "",
    LogType.LLM_ERROR: "",
    LogType.GITHUB_REPO_CREATE: "",
    LogType.GITHUB_BRANCH_CREATE: "",
    LogType.GITHUB_COMMIT: "",
    LogType.GITHUB_PR_CREATE: "",
    LogType.GITHUB_ERROR: "",
    LogType.MEMORY_STORE: "",
    LogType.MEMORY_RETRIEVE: "",
    LogType.INFO: "",
    LogType.WARNING: "",
    LogType.ERROR: "",
    LogType.DEBUG: "",
}


def log_to_db(
    project_id: Optional[str],
    level: str,
    message: str,
    agent_role: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    log_type: Optional[LogType] = None
) -> None:
    log_level_num = getattr(logging, level.upper(), logging.INFO)

    prefix = ""
    if project_id:
        prefix += f"[{project_id[:8]}]"
    if agent_role:
        prefix += f"[{agent_role}]"
    if log_type:
        icon = LOG_TYPE_ICONS.get(log_type, "")
        prefix += f" {icon}"
    
    console_msg = f"{prefix} {message}" if prefix else message
    logger.log(log_level_num, console_msg)
    
    # Store to database
    if not project_id:
        return
    
    try:
        db_log_level = LogLevel[level.upper()]
        
        # Build extra_data with log_type for frontend
        full_extra_data = extra_data.copy() if extra_data else {}
        if log_type:
            full_extra_data["log_type"] = log_type.value
            # Don't add icons since we're removing emojis
            # full_extra_data["icon"] = LOG_TYPE_ICONS.get(log_type, "")

        with get_db_context() as db:
            log_entry = Log(
                project_id=project_id,
                agent_role=agent_role,
                level=db_log_level,
                message=message,
                extra_data=full_extra_data if full_extra_data else None
            )
            db.add(log_entry)
            
    except Exception as e:
        # Log the error to console so we know logging failed
        logger.warning(f"Failed to log to database: {e}")


def log_workflow_event(
    project_id: str,
    event_type: LogType,
    message: str,
    extra_data: Optional[Dict[str, Any]] = None
) -> None:
    """Log a workflow event with structured type"""
    level = "ERROR" if "error" in event_type.value or "failed" in event_type.value else "INFO"
    log_to_db(
        project_id=project_id,
        level=level,
        message=message,
        log_type=event_type,
        extra_data=extra_data
    )


def log_agent_event(
    project_id: str,
    agent_role: str,
    event_type: LogType,
    message: str,
    extra_data: Optional[Dict[str, Any]] = None
) -> None:
    """Log an agent event with structured type"""
    level = "ERROR" if "error" in event_type.value else "INFO"
    log_to_db(
        project_id=project_id,
        level=level,
        message=message,
        agent_role=agent_role,
        log_type=event_type,
        extra_data=extra_data
    )


def log_task_event(
    project_id: str,
    agent_role: str,
    task_id: str,
    event_type: LogType,
    message: str,
    extra_data: Optional[Dict[str, Any]] = None
) -> None:
    """Log a task event with structured type"""
    level = "ERROR" if "failed" in event_type.value else "INFO"
    full_extra = {"task_id": task_id}
    if extra_data:
        full_extra.update(extra_data)
    log_to_db(
        project_id=project_id,
        level=level,
        message=message,
        agent_role=agent_role,
        log_type=event_type,
        extra_data=full_extra
    )


def log_exception(
    project_id: Optional[str],
    message: str,
    exception: Exception,
    agent_role: Optional[str] = None,
    log_type: LogType = LogType.ERROR
) -> None:
    """Log an exception with full traceback"""
    tb_str = traceback.format_exc()
    full_message = f"{message}: {str(exception)}"
    
    # Log to console with traceback
    prefix = f"[{project_id[:8]}]" if project_id else ""
    logger.error(f"{prefix} {full_message}")
    logger.error(f"Traceback:\n{tb_str}")
    
    # Log to database
    log_to_db(
        project_id=project_id,
        level="ERROR",
        message=full_message,
        agent_role=agent_role,
        log_type=log_type,
        extra_data={"traceback": tb_str}
    )