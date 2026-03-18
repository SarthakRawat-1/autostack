# File: workflows/cloud_graph.py
"""
Cloud Provisioning Workflow Graph

Defines the LangGraph workflow for infrastructure provisioning.
Orchestrates InfraArchitect -> DevOps -> SecOps.
"""

import logging
import os
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from services.checkpointer import get_checkpointer
from services.agent_registry import cloud_registry

from workflows.state import (
    InfrastructureState, WorkflowPhase, WorkflowStatus
)
from agents.config import AgentFactory, AgentRole
from services.memory import get_agent_memory
from services.github_client import GitHubClient

logger = logging.getLogger(__name__)


def _make_error(message: str, phase: str = "unknown") -> Dict[str, Any]:
    """Create a structured error dict consistent with WorkflowState.errors schema."""
    from datetime import datetime
    return {"message": message, "timestamp": datetime.utcnow().isoformat(), "phase": phase}


def _extract_subscription_id_from_request(request: str) -> str:
    """
    Extract Azure Subscription ID from user request.
    Looks for patterns like 'subscription: <uuid>' or 'in subscription <uuid>'.
    """
    import re

    # Azure subscription IDs are UUIDs
    uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

    patterns = [
        rf'subscription[\s]*[:\s=]\s*({uuid_pattern})',
        rf'in\s+subscription\s+({uuid_pattern})',
        rf'for\s+subscription\s+({uuid_pattern})',
    ]

    for pattern in patterns:
        match = re.search(pattern, request.lower())
        if match:
            return match.group(1)

    return None

def _get_system_azure_credentials(project_id: str) -> Dict[str, Optional[str]]:
    """Helper to fetch Azure credentials from the project owner's System Settings"""
    from models import get_db, SystemSettings
    from models.models import Project
    from services.credentials import get_credential_manager
    
    db = next(get_db())
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {}
        settings = db.query(SystemSettings).filter(
            SystemSettings.user_id == project.user_id
        ).first()
        if not settings:
            return {}
            
        manager = get_credential_manager()
        creds = manager.get_system_credentials(settings)
        return creds
    finally:
        db.close()

def _update_project_db(project_id: str, **fields):
    """Update the Project row in the database."""
    from models.database import get_db_context
    from models.models import Project, ProjectStatus
    # Map string status values to ProjectStatus enum
    if "status" in fields and isinstance(fields["status"], str):
        status_map = {s.value: s for s in ProjectStatus}
        mapped = status_map.get(fields["status"])
        if mapped:
            fields["status"] = mapped
    try:
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=project_id).first()
            if project:
                for attr, value in fields.items():
                    setattr(project, attr, value)
                db.commit()
    except Exception as e:
        logger.warning(f"Failed to update project {project_id} in DB: {e}")

# --- NODES ---

async def define_architecture(state: InfrastructureState) -> InfrastructureState:
    """Node: Infra Architect analyzes request and creates plan."""
    logger.info("Executing Node: define_architecture")
    state["current_phase"] = WorkflowPhase.INFRA_PLANNING
    
    project_id = state["project_id"]
    request = state["request"]
    repo_url = state.get("repository_url")
    
    agents = _get_agents_for_project(project_id)
    architect = agents.get(AgentRole.INFRA_ARCHITECT)
    
    if not architect:
        logger.error(f"InfraArchitect agent not found for project {project_id}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error("InfraArchitect agent not found", "infra_planning")]
        return state
    
    try:
        plan = await architect.analyze_and_plan(request, repo_url)
        
        state["resource_plan"] = plan
        state["metadata"]["intent"] = plan.get("intent")
        return state
    except Exception as e:
        logger.error(f"Architecture definition failed: {e}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error(str(e), "infra_planning")]
        return state

async def generate_terraform(state: InfrastructureState) -> InfrastructureState:
    """Node: DevOps agent writes Terraform code."""
    logger.info("Executing Node: generate_terraform")
    state["current_phase"] = WorkflowPhase.INFRA_GENERATION
    
    project_id = state["project_id"]
    plan = state.get("resource_plan")
    
    agents = _get_agents_for_project(project_id)
    devops = agents.get(AgentRole.DEVOPS)
    
    if not devops:
        logger.error(f"DevOps agent not found for project {project_id}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error("DevOps agent not found", "infra_generation")]
        return state
    
    try:
        repository = state.get("repository")
        
        tf_files = await devops.generate_code(
            resource_plan=plan, 
            github_client=devops.github_client,
            target_repo=repository,
            commit=False
        )
        
        state["terraform_code"] = tf_files
        return state
    except Exception as e:
        logger.error(f"Terraform generation failed: {e}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error(str(e), "infra_generation")]
        return state

async def validate_infrastructure(state: InfrastructureState) -> InfrastructureState:
    """Node: SecOps agent scans code and estimates cost."""
    logger.info("Executing Node: validate_infrastructure")
    state["current_phase"] = WorkflowPhase.INFRA_VALIDATION
    
    project_id = state["project_id"]
    tf_files = state.get("terraform_code")
    
    agents = _get_agents_for_project(project_id)
    secops = agents.get(AgentRole.SECOPS)
    
    if not secops:
        logger.error(f"SecOps agent not found for project {project_id}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error("SecOps agent not found", "infra_validation")]
        return state
    
    try:
        report = await secops.validate_infrastructure(tf_files)
        
        state["security_report"] = report.get("security_summary")
        state["cost_estimate"] = report.get("cost_estimate")
        
        if report.get("status") == "FAILED":
             logger.warning("Security validation failed.")
             state["status"] = WorkflowStatus.FAILED
             recs = report.get("recommendations", [])
             state["errors"] = state.get("errors", []) + [
                 _make_error(f"Security validation failed: {'; '.join(recs) if recs else 'See security report'}", "infra_validation")
             ]
        elif report.get("status") == "WARNING":
             logger.warning("Security validation has warnings (non-strict mode).")
             metadata = state.get("metadata", {})
             metadata["security_warnings"] = report.get("recommendations", [])
             state["metadata"] = metadata
        
        return state
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error(str(e), "infra_validation")]
        return state

async def commit_and_finalize(state: InfrastructureState) -> InfrastructureState:
    """Node: Finalize and commit code if validated."""
    logger.info("Executing Node: commit_and_finalize")
    state["current_phase"] = WorkflowPhase.INFRA_APPLYING
    
    project_id = state["project_id"]
    tf_files = state.get("terraform_code")
    repo = state.get("repository")
    
    agents = _get_agents_for_project(project_id)
    devops = agents.get(AgentRole.DEVOPS)
    
    if not devops:
        logger.error(f"DevOps agent not found for project {project_id}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error("DevOps agent not found", "infra_applying")]
        return state
    
    if state.get("status") != WorkflowStatus.FAILED:
        try:
             if devops.github_client and repo:
                 feature_branch = await devops._commit_to_github(
                     devops.github_client, repo, tf_files
                 )
                 state["terraform_branch"] = feature_branch
                 logger.info(f"Terraform code committed to branch: {feature_branch}")
                 
             state["status"] = WorkflowStatus.RUNNING
             state["requires_approval"] = True
              
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            state["status"] = WorkflowStatus.FAILED
            state["errors"] = state.get("errors", []) + [_make_error(str(e), "infra_applying")]

    return state

async def terraform_apply(state: InfrastructureState) -> InfrastructureState:
    """Node: Apply Terraform code (Provisioning)."""
    logger.info("Executing Node: terraform_apply")
    state["current_phase"] = WorkflowPhase.INFRA_APPLYING
    
    project_id = state["project_id"]
    azure_credentials = state.get("azure_credentials", {})
    
    # If code was committed to a feature branch, fetch the latest files from it
    # so terraform apply uses exactly what's in Git (including any manual edits)
    terraform_branch = state.get("terraform_branch")
    repository = state.get("repository")
    tf_files = state.get("terraform_code")  # fallback
    
    if terraform_branch and repository:
        agents = _get_agents_for_project(project_id)
        devops_for_fetch = agents.get(AgentRole.DEVOPS)
        if devops_for_fetch and devops_for_fetch.github_client:
            try:
                all_files = await devops_for_fetch.github_client.list_repository_files(
                    repository, ref=terraform_branch
                )
                branch_tf_files = {}
                for fpath in all_files:
                    if fpath.endswith(".tf") or fpath.endswith(".yml") or fpath.endswith(".yaml"):
                        try:
                            content = await devops_for_fetch.github_client.get_file_content(
                                repository, fpath, ref=terraform_branch
                            )
                            branch_tf_files[fpath] = content
                        except Exception:
                            pass
                if branch_tf_files:
                    tf_files = branch_tf_files
                    logger.info(f"Fetched {len(tf_files)} files from branch {terraform_branch} for apply")
            except Exception as e:
                logger.warning(f"Failed to fetch files from branch {terraform_branch}, using in-state code: {e}")
    
    azure_subscription_id = state.get("metadata", {}).get("azure_subscription_id")
    if not azure_subscription_id:
        azure_subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")

    if not azure_subscription_id:
         original_request = state.get("request", "")
         azure_subscription_id = _extract_subscription_id_from_request(original_request)

    if not azure_subscription_id:
         logger.warning("No Azure Subscription ID found in state, env, or request. Terraform plan may fail.")
         azure_subscription_id = "unknown-subscription"
    
    # Check credentials
    if not azure_credentials or not azure_credentials.get("tenant_id"):
        logger.error("No Azure credentials provided for apply.")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error("Missing Azure credentials for provisioning.", "infra_applying")]
        return state

    agents = _get_agents_for_project(project_id)
    devops = agents.get(AgentRole.DEVOPS)

    if not devops:
        logger.error(f"DevOps agent not found for project {project_id}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error("DevOps agent not found", "infra_applying")]
        return state

    try:
        result = await devops.apply_code(
            files=tf_files,
            azure_credentials=azure_credentials,
            azure_subscription_id=azure_subscription_id
        )

        state["provisioning_output"] = result
        if result["success"]:
            state["status"] = WorkflowStatus.COMPLETED
            logger.info(f"Infrastructure provisioning completed successfully for subscription {azure_subscription_id}")
        else:
            state["status"] = WorkflowStatus.FAILED
            error_msg = result.get("stderr", "Unknown error")
            logger.error(f"Infrastructure provisioning failed: {error_msg}")
            state["errors"] = state.get("errors", []) + [_make_error(error_msg, "infra_applying")]

        return state

    except Exception as e:
        logger.error(f"Terraform Apply failed: {e}")
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [_make_error(str(e), "infra_applying")]
        return state


# --- GRAPH ---

def create_cloud_workflow_graph() -> StateGraph:
    workflow = StateGraph(InfrastructureState)
    
    workflow.add_node("define_architecture", define_architecture)
    workflow.add_node("generate_terraform", generate_terraform)
    workflow.add_node("validate_infrastructure", validate_infrastructure)
    workflow.add_node("commit_and_finalize", commit_and_finalize)
    workflow.add_node("terraform_apply", terraform_apply)
    
    workflow.set_entry_point("define_architecture")
    
    workflow.add_edge("define_architecture", "generate_terraform")
    workflow.add_edge("generate_terraform", "validate_infrastructure")
    
    def check_validation(state):
        if state.get("status") == WorkflowStatus.FAILED:
            return END
        return "commit_and_finalize"

    workflow.add_conditional_edges(
        "validate_infrastructure",
        check_validation,
        {
            "commit_and_finalize": "commit_and_finalize",
            END: END
        }
    )
    
    workflow.add_edge("commit_and_finalize", "terraform_apply")
    workflow.add_edge("terraform_apply", END)
    
    memory = get_checkpointer()
    return workflow.compile(checkpointer=memory, interrupt_before=["terraform_apply"])

# --- EXECUTION ---

def _get_agents_for_project(project_id: str):
    return cloud_registry.get(project_id)

async def execute_cloud_workflow(
    project_id: str,
    project_name: str,
    request: str,
    repository: Optional[str] = None,
    repository_url: Optional[str] = None,
    github_client: Optional[GitHubClient] = None,
    credentials: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Entry point to run the Cloud Provisioning Workflow."""
    
    # Derive repository (owner/repo) from repository_url if not provided
    if not repository and repository_url and "github.com" in repository_url:
        parts = repository_url.rstrip("/").split("/")
        if len(parts) >= 2:
            repository = f"{parts[-2]}/{parts[-1]}"
    
    memory = get_agent_memory()
    
    if not github_client and credentials:
        github_client = GitHubClient(token=credentials.get("github_token"))
    
    from agents.llm import get_code_llm, get_non_code_llm
    from services.notification import NotificationService

    slack_webhook = credentials.get("slack_webhook") if credentials else None
    discord_webhook = credentials.get("discord_webhook") if credentials else None
    notification_service = NotificationService(
        slack_webhook_url=slack_webhook,
        discord_webhook_url=discord_webhook
    )

    architect = AgentFactory.create_agent(
        role=AgentRole.INFRA_ARCHITECT,
        llm=get_non_code_llm(),
        memory=memory
    )

    devops = AgentFactory.create_agent(
        role=AgentRole.DEVOPS,
        llm=get_code_llm(),
        memory=memory,
        github_client=github_client,
        notification_service=notification_service
    )

    secops = AgentFactory.create_agent(
        role=AgentRole.SECOPS,
        llm=get_non_code_llm(),
        memory=memory
    )
    
    cloud_registry.register(project_id, {
        AgentRole.INFRA_ARCHITECT: architect,
        AgentRole.DEVOPS: devops,
        AgentRole.SECOPS: secops
    })
    
    # Build Azure credentials dict
    sys_creds = _get_system_azure_credentials(project_id)
    azure_creds = {
        "tenant_id": (credentials or {}).get("azure_tenant_id") or
                     sys_creds.get("azure_tenant_id") or
                     os.environ.get("AZURE_TENANT_ID"),
        "client_id": (credentials or {}).get("azure_client_id") or
                     sys_creds.get("azure_client_id") or
                     os.environ.get("AZURE_CLIENT_ID"),
        "client_secret": (credentials or {}).get("azure_client_secret") or
                         sys_creds.get("azure_client_secret") or
                         os.environ.get("AZURE_CLIENT_SECRET"),
    }

    initial_state = InfrastructureState(
        project_id=project_id,
        project_name=project_name,
        request=request,
        repository=repository,
        repository_url=repository_url,
        current_phase=WorkflowPhase.INITIALIZING,
        status=WorkflowStatus.RUNNING,
        errors=[],
        user_feedback=[],
        requires_approval=False,
        terraform_branch=None,
        azure_credentials=azure_creds,
        metadata={
            "azure_subscription_id": (credentials or {}).get("azure_subscription_id") or
                                     sys_creds.get("azure_subscription_id") or
                                     os.environ.get("AZURE_SUBSCRIPTION_ID") or
                                     _extract_subscription_id_from_request(request)
        },
    )
    
    app = create_cloud_workflow_graph()
    
    config = {"configurable": {"thread_id": project_id}}
    try:
        result = await app.ainvoke(initial_state, config=config)
    except Exception:
        cloud_registry.remove(project_id)
        _update_project_db(project_id, status="failed")
        raise
    
    # Update project DB and clean up based on outcome
    graph_state = app.get_state(config)
    if graph_state and graph_state.next:
        # Workflow paused — waiting for human approval before terraform apply
        _update_project_db(project_id, current_phase="infra_applying", requires_approval=1)
    else:
        cloud_registry.remove(project_id)
        final_status = result.get("status")
        if final_status == WorkflowStatus.COMPLETED:
            _update_project_db(project_id, status="completed", current_phase="completed")
        elif final_status == WorkflowStatus.FAILED:
            _update_project_db(project_id, status="failed", current_phase=str(result.get("current_phase", "failed")))
    
    return result

async def resume_cloud_workflow(project_id: str, action: str = "approve") -> Dict[str, Any]:
    """Resumes the workflow (specifically to run apply phase)."""
    
    # Handle rejection — do NOT run terraform apply
    if action != "approve":
        cloud_registry.remove(project_id)
        _update_project_db(project_id, status="cancelled", current_phase="cancelled", requires_approval=0)
        logger.info(f"Cloud workflow for project {project_id} was rejected by user (action={action})")
        return {"status": "cancelled", "message": f"Terraform apply was {action} by user."}
    
    # Re-register agents if missing (registry is in-memory, empty after restart)
    if not cloud_registry.get(project_id):
        from agents.llm import get_code_llm, get_non_code_llm
        from services.notification import NotificationService
        from services.credentials import get_credential_manager
        from models.database import get_db_context
        from models.models import Project
        
        # Fetch credentials for this project
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=project_id).first()
            if project:
                credential_manager = get_credential_manager()
                credentials = credential_manager.get_credentials_for_project(project)
            else:
                credentials = {}
        
        github_client = GitHubClient(token=credentials.get("github_token")) if credentials.get("github_token") else None
        notification_service = NotificationService(
            slack_webhook_url=credentials.get("slack_webhook"),
            discord_webhook_url=credentials.get("discord_webhook")
        )
        memory = get_agent_memory()
        
        architect = AgentFactory.create_agent(
            role=AgentRole.INFRA_ARCHITECT,
            llm=get_non_code_llm(),
            memory=memory
        )
        devops = AgentFactory.create_agent(
            role=AgentRole.DEVOPS,
            llm=get_code_llm(),
            memory=memory,
            github_client=github_client,
            notification_service=notification_service
        )
        secops = AgentFactory.create_agent(
            role=AgentRole.SECOPS,
            llm=get_non_code_llm(),
            memory=memory
        )
        cloud_registry.register(project_id, {
            AgentRole.INFRA_ARCHITECT: architect,
            AgentRole.DEVOPS: devops,
            AgentRole.SECOPS: secops
        })
        logger.info(f"Re-registered cloud agents for resumed project {project_id}")
    
    app = create_cloud_workflow_graph()
    config = {"configurable": {"thread_id": project_id}}
    
    logger.info(f"Resuming workflow for project {project_id} (Action: {action})")
    
    try:
        result = await app.ainvoke(None, config=config)
    except Exception:
        cloud_registry.remove(project_id)
        _update_project_db(project_id, status="failed")
        raise
    
    # Update DB and clean up only if workflow fully completed
    graph_state = app.get_state(config)
    if not (graph_state and graph_state.next):
        cloud_registry.remove(project_id)
        final_status = result.get("status")
        if final_status == WorkflowStatus.COMPLETED:
            _update_project_db(project_id, status="completed", current_phase="completed", requires_approval=0)
        elif final_status == WorkflowStatus.FAILED:
            _update_project_db(project_id, status="failed", current_phase=str(result.get("current_phase", "failed")))
    
    return result
