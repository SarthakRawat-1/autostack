# File: workflows/graph.py
"""
LangGraph State Graph

Defines and compiles the LangGraph state graph for workflow orchestration.
Coordinates agent execution with conditional branching and state management.

Implements: Requirements 1.2, 2.4, 4.7
"""

import os
import logging
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from services.checkpointer import get_checkpointer
from services.agent_registry import software_registry

logger = logging.getLogger(__name__)

from workflows.state import (
    WorkflowState, WorkflowPhase, WorkflowStatus,
    create_initial_state, has_pending_tasks, all_tasks_completed,
    has_failed_tasks, is_retry_exhausted
)
from workflows.nodes import (
    initialize_project, plan_project, develop_features,
    test_code, generate_documentation, review_results,
    finalize_project
)
from agents.config import AgentFactory, AgentRole
from agents.llm import get_groq_llm
from services.github_client import GitHubClient
from services.memory import get_agent_memory
from models.models import ProjectStatus




def get_agents_for_project(project_id: str) -> Dict[str, Any]:
    """
    Get agents for a project from registry
    
    Args:
        project_id: Project identifier
        
    Returns:
        Dictionary of agents by role
    """
    return software_registry.get(project_id)


# Initialize LangSmith tracing if enabled
def _initialize_langsmith() -> None:
    """
    Initialize LangSmith tracing for LLM observability
    
    Enables LangSmith tracing if LANGCHAIN_TRACING_V2 is set to 'true'.
    Requires LANGCHAIN_API_KEY to be set in environment.
    """
    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    
    if tracing_enabled:
        api_key = os.getenv("LANGCHAIN_API_KEY")
        project = os.getenv("LANGCHAIN_PROJECT", "autostack")
        endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
        
        if not api_key:
            os.environ["LANGCHAIN_TRACING_V2"] = "false"
            return
        
        # Set LangSmith environment variables
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
    else:
        # Tracing disabled
        pass

# Initialize LangSmith on module import
_initialize_langsmith()


def should_continue_to_development(state: WorkflowState) -> str:
    """
    Conditional edge: Check if should continue to development

    Args:
        state: Current workflow state

    Returns:
        Next node name or END
    """
    logger.info(f"Checking if should continue to development...")
    logger.info(f"  Status: {state.get('status')}")
    logger.info(f"  Total tasks: {len(state.get('tasks', []))}")
    logger.info(f"  Pending tasks: {len(state.get('pending_tasks', []))}")
    logger.info(f"  Errors: {state.get('errors', [])}")
    logger.info(f"  User feedback: {len(state.get('user_feedback', []))}")

    if state.get("status") == WorkflowStatus.FAILED:
        logger.info("  -> Going to finalize (status is FAILED)")
        return "finalize"

    # Check if any tasks were created - if not, something went wrong in planning
    total_tasks = len(state.get("tasks", []))
    if total_tasks == 0:
        logger.warning("  -> No tasks created! Planning may have failed silently.")
        # Mark as failed since no work can be done
        state["status"] = WorkflowStatus.FAILED
        state["errors"] = state.get("errors", []) + [{"message": "No tasks were created during planning phase"}]
        return "finalize"

    # Check if we have user feedback that requires looping back
    user_feedback = state.get("user_feedback", [])
    if user_feedback and state.get("feedback_loop_target") == "plan":
        logger.info("  -> Looping back to plan due to user feedback")
        state["feedback_loop_target"] = None  # Reset the target
        return "plan"
    if user_feedback and state.get("feedback_loop_target") == "develop":
        logger.info("  -> Routing to develop due to user feedback")
        state["feedback_loop_target"] = None
        return "develop"

    if not has_pending_tasks(state):
        logger.info("  -> Going to finalize (no pending tasks)")
        return "finalize"

    logger.info("  -> Continuing to develop")
    return "develop"


def should_continue_to_testing(state: WorkflowState) -> str:
    """
    Conditional edge: Check if should continue to testing

    Args:
        state: Current workflow state

    Returns:
        Next node name or END
    """
    # Check if we have user feedback that requires looping back
    user_feedback = state.get("user_feedback", [])
    if user_feedback and state.get("feedback_loop_target") == "develop":
        logger.info("  -> Looping back to develop due to user feedback")
        state["feedback_loop_target"] = None  # Reset the target
        return "develop"
    if user_feedback and state.get("feedback_loop_target") == "test":
        logger.info("  -> Routing to test due to user feedback")
        state["feedback_loop_target"] = None
        return "test"

    if state.get("status") == WorkflowStatus.FAILED:
        return "review"

    # Check if there are actual pending QA tasks in the database
    project_id = state.get("project_id")
    if project_id:
        from models.database import get_db_context
        from models.models import Task, TaskStatus
        with get_db_context() as db:
            qa_count = db.query(Task).filter_by(
                project_id=project_id,
                agent_role="qa",
                status=TaskStatus.PENDING
            ).count()
            if qa_count > 0:
                return "test"

    return "document"


def should_retry_or_finalize(state: WorkflowState) -> str:
    """
    Conditional edge: Check if should retry failed tasks or finalize

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    # Check if we have user feedback that requires looping back to documentation
    user_feedback = state.get("user_feedback", [])
    if user_feedback and state.get("feedback_loop_target") == "document":
        logger.info("  -> Looping back to document due to user feedback")
        state["feedback_loop_target"] = None  # Reset the target
        return "document"

    # Check if all tasks completed successfully
    if all_tasks_completed(state) and not has_failed_tasks(state):
        return "finalize"

    # Check if there are failed tasks and retries available
    if has_failed_tasks(state) and not is_retry_exhausted(state):        # TODO: Implement retry logic in future iteration
        return "finalize"

    # Otherwise finalize
    return "finalize"


def create_workflow_graph(
    github_client: Optional[GitHubClient] = None,
    with_checkpointing: bool = True,
    execution_mode: str = "auto"
) -> StateGraph:
    """
    Create LangGraph workflow state graph
    
    Builds the complete workflow graph with all nodes and edges.
    
    Implements: Requirements 1.2, 2.4, 4.7
    
    Args:
        github_client: Optional GitHub client
        with_checkpointing: Whether to enable state checkpointing
        execution_mode: "auto" for full workflow, "manual" for step-by-step with interrupts
        
    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info(f"Creating LangGraph workflow state graph (mode: {execution_mode})")
    
    # Create state graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("initialize", initialize_project)
    workflow.add_node("plan", plan_project)
    workflow.add_node("develop", develop_features)
    workflow.add_node("test", test_code)
    workflow.add_node("document", generate_documentation)
    workflow.add_node("review", review_results)
    workflow.add_node("finalize", finalize_project)
    
    # Add edges
    workflow.set_entry_point("initialize")
    
    # Linear flow with conditional branches
    workflow.add_edge("initialize", "plan")
    workflow.add_conditional_edges(
        "plan",
        should_continue_to_development,
        {
            "develop": "develop",
            "plan": "plan",
            "finalize": "finalize"
        }
    )
    workflow.add_conditional_edges(
        "develop",
        should_continue_to_testing,
        {
            "test": "test",
            "develop": "develop",
            "document": "document",
            "review": "review"
        }
    )
    workflow.add_edge("test", "document")
    workflow.add_edge("document", "review")
    workflow.add_conditional_edges(
        "review",
        should_retry_or_finalize,
        {
            "document": "document",
            "finalize": "finalize"
        }
    )
    workflow.add_edge("finalize", END)
    
    # Determine interrupt points based on execution mode
    interrupt_before = []
    if execution_mode == "manual":
        # Pause before each major phase for user approval
        interrupt_before = ["develop", "test", "document", "finalize"]
    # Compile graph with optional checkpointing and interrupts
    if with_checkpointing:
        checkpointer = get_checkpointer()
        graph = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_before
        )
        logger.info(f"Workflow graph compiled with PostgresSaver checkpointing and {len(interrupt_before)} interrupt points")
    else:
        graph = workflow.compile(interrupt_before=interrupt_before)
        logger.info(f"Workflow graph compiled with {len(interrupt_before)} interrupt points")
    
    return graph


async def execute_workflow(
    project_id: str,
    project_name: str,
    project_description: str,
    repository: Optional[str] = None,
    repository_url: Optional[str] = None,
    source_branch: Optional[str] = None,
    github_client: Optional[GitHubClient] = None,
    notification_service: Optional[Any] = None,
    max_retries: int = 2,
    execution_mode: str = "auto",
    credentials: Optional[Dict[str, str]] = None,
    is_import_mode: bool = False
) -> Dict[str, Any]:
    """
    Execute complete workflow for a project
    
    Convenience function to create and execute workflow graph.
    
    Args:
        project_id: Project identifier
        project_name: Project name
        project_description: Project description
        repository: Optional repository name
        repository_url: Optional repository URL
        github_client: Optional GitHub client
        notification_service: Optional notification service
        max_retries: Maximum retry attempts
        execution_mode: "auto" for full workflow, "manual" for step-by-step
        credentials: Optional dict with github_token, slack_webhook, discord_webhook
        
    Returns:
        Final workflow state
        
    Raises:
        Exception: If workflow execution fails
    """
    logger.info(f"Executing workflow for project: {project_id} (mode: {execution_mode})")
    
    try:
        # Initialize LLMs with LangChain
        logger.info("Initializing LangChain LLMs...")
        
        if not github_client:
            # Use user's GitHub token if provided
            github_token = credentials.get("github_token") if credentials else None
            github_client = GitHubClient(token=github_token)
            logger.info(f"Initialized GitHub client ({'user token' if github_token else 'system token'})")
        
        if not notification_service:
            from services.notification import NotificationService
            # Use user's webhook URLs if provided
            slack_webhook = credentials.get("slack_webhook") if credentials else None
            discord_webhook = credentials.get("discord_webhook") if credentials else None
            notification_service = NotificationService(
                slack_webhook_url=slack_webhook,
                discord_webhook_url=discord_webhook
            )
            logger.info(f"Initialized notification service ({'user webhooks' if credentials else 'system webhooks'})")
        
        # Get agent memory (may fail if ChromaDB is not configured)
        logger.info("Connecting to agent memory (ChromaDB)...")
        try:
            memory = get_agent_memory()
            logger.info("Agent memory connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to agent memory: {e}")
            raise Exception(f"Agent memory connection failed: {e}") from e
        
        # Create agents with appropriate LLMs
        # Use different models for different agent types
        from agents.llm import get_code_llm, get_non_code_llm

        logger.info("Creating agents...")
        pm_agent = AgentFactory.create_agent(
            role=AgentRole.PROJECT_MANAGER,
            llm=get_non_code_llm(),  # PM uses optimized model for non-code tasks
            memory=memory
        )
        logger.info("Project Manager agent created")

        developer_agent = AgentFactory.create_agent(
            role=AgentRole.DEVELOPER,
            llm=get_code_llm(),  # Developer uses optimized model for code generation
            memory=memory,
            github_client=github_client,
            notification_service=notification_service
        )

        qa_agent = AgentFactory.create_agent(
            role=AgentRole.QA,
            llm=get_code_llm(),  # QA uses optimized model for code analysis
            memory=memory,
            github_client=github_client,
            notification_service=notification_service
        )

        doc_agent = AgentFactory.create_agent(
            role=AgentRole.DOCUMENTATION,
            llm=get_non_code_llm(),  # Documentation uses optimized model for writing tasks
            memory=memory,
            github_client=github_client,
            notification_service=notification_service
        )
        # Create initial state (without agents - they can't be serialized)
        initial_state = create_initial_state(
            project_id=project_id,
            project_name=project_name,
            project_description=project_description,
            repository=repository,
            repository_url=repository_url,
            source_branch=source_branch,
            max_retries=max_retries,
            is_import_mode=is_import_mode
        )
        
        # Store agents in a scoped registry accessible by nodes (not in state)
        # This avoids serialization issues with checkpointing
        software_registry.register(project_id, {
            "project_manager": pm_agent,
            "developer": developer_agent,
            "qa": qa_agent,
            "documentation": doc_agent
        })        
        # Create and compile workflow graph with execution mode
        graph = create_workflow_graph(
            github_client=github_client,
            with_checkpointing=True,
            execution_mode=execution_mode
        )
        
        # Execute workflow        
        # Configure checkpointer with thread_id
        config = {
            "configurable": {
                "thread_id": project_id  # Use project_id as thread_id for checkpointing
            }
        }
        
        # Execute workflow (may be interrupted in manual mode)
        final_state = await graph.ainvoke(initial_state, config=config)
        
        # Check if workflow was interrupted
        graph_state = graph.get_state(config)
        if graph_state.next:
            # Workflow is interrupted, waiting for approval
            next_node = graph_state.next[0] if graph_state.next else None            
            # Update project in database to mark as requiring approval
            from models.database import get_db_context
            from models.models import Project
            with get_db_context() as db:
                project = db.query(Project).filter_by(id=project_id).first()
                if project:
                    project.requires_approval = 1
                    project.current_interrupt = next_node
                    db.commit()
            
            return {
                **final_state,
                "status": "interrupted",
                "requires_approval": True,
                "current_interrupt": next_node
            }
        
        logger.info(
            f"Workflow execution complete. Status: {final_state.get('status')}, "
            f"Phase: {final_state.get('current_phase')}"
        )
        
        # Clean up agents if workflow fully completed (not interrupted)
        graph_state = graph.get_state(config)
        if not (graph_state and graph_state.next):
            software_registry.remove(project_id)
        
        return final_state
        
    except Exception as e:
        software_registry.remove(project_id)
        error_msg = f"Workflow execution failed: {str(e)}"
        raise Exception(error_msg) from e



def _reset_downstream_tasks(project_id: str, target: str) -> None:
    """
    Reset tasks for re-processing based on feedback target.
    
    For 'plan': Resets PM task to PENDING, deletes all non-PM tasks (PM will recreate).
    For others: Resets tasks of the target role and all downstream roles to PENDING.
    """
    from models.database import get_db_context
    from models.models import Task, TaskStatus
    from datetime import datetime
    
    roles_to_reset = {
        "plan": ["developer", "qa", "documentation"],
        "develop": ["developer", "qa", "documentation"],
        "test": ["qa", "documentation"],
        "document": ["documentation"],
    }
    
    roles = roles_to_reset.get(target, [])
    if not roles:
        return
    
    with get_db_context() as db:
        if target == "plan":
            # Delete non-PM tasks (PM will recreate them with new plan)
            db.query(Task).filter(
                Task.project_id == project_id,
                Task.agent_role != "project_manager"
            ).delete()
            # Reset PM task to PENDING for re-processing
            pm_tasks = db.query(Task).filter_by(
                project_id=project_id,
                agent_role="project_manager"
            ).all()
            for task in pm_tasks:
                task.status = TaskStatus.PENDING
                task.result = None
                task.error_message = None
                task.completed_at = None
                task.updated_at = datetime.utcnow()
        else:
            # Reset tasks for target + downstream roles to PENDING
            tasks = db.query(Task).filter(
                Task.project_id == project_id,
                Task.agent_role.in_(roles)
            ).all()
            for task in tasks:
                task.status = TaskStatus.PENDING
                task.result = None
                task.error_message = None
                task.completed_at = None
                task.updated_at = datetime.utcnow()
        
        db.commit()
    
    logger.info(f"Reset downstream tasks for feedback target '{target}': roles={roles}")


async def resume_workflow(
    project_id: str,
    approved: bool = True,
    decision: str = "approve",
    feedback: Optional[str] = None,
    credentials: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Resume an interrupted workflow after user approval
    
    Args:
        project_id: Project identifier
        approved: Whether user approved continuation (deprecated, use decision)
        decision: User decision - 'approve', 'request_changes', or 'cancel'
        feedback: Optional feedback text when requesting changes
        credentials: Optional credentials dict
        
    Returns:
        Updated workflow state
        
    Raises:
        Exception: If workflow resumption fails
    """
    from models.database import get_db_context
    from models.models import Project

    logger.info(f"Resuming workflow for project: {project_id} (decision: {decision})")

    try:
        # Get project from database
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=project_id).first()
            
            if not project:
                raise Exception(f"Project {project_id} not found")
            
            if not project.requires_approval:
                raise Exception(f"Project {project_id} is not waiting for approval")
            
            execution_mode = project.execution_mode
            
            # Save the original interrupt point BEFORE clearing it
            original_interrupt = project.current_interrupt
            
            # Handle cancel decision
            if decision == "cancel" or not approved:
                project.status = ProjectStatus.CANCELLED
                project.requires_approval = 0
                project.current_interrupt = None
                db.commit()
                return {
                    "status": "cancelled",
                    "project_id": project_id
                }
            
            # Clear approval flag (will be set again if interrupted)
            project.requires_approval = 0
            project.current_interrupt = None
            db.commit()
        
        # Get credentials for project
        if not credentials:
            from services.credentials import get_credential_manager
            credential_manager = get_credential_manager()
            with get_db_context() as db:
                project = db.query(Project).filter_by(id=project_id).first()
                credentials = credential_manager.get_credentials_for_project(project)
        
        # Initialize clients with credentials
        # groq_client removed as it is legacy and unused
        github_client = GitHubClient(token=credentials.get("github_token"))
        
        from services.notification import NotificationService
        notification_service = NotificationService(
            slack_webhook_url=credentials.get("slack_webhook"),
            discord_webhook_url=credentials.get("discord_webhook")
        )
        
        # Re-register agents (registry is in-memory and empty after restart)
        if not software_registry.get(project_id):
            from agents.llm import get_code_llm, get_non_code_llm
            memory = get_agent_memory()
            
            pm_agent = AgentFactory.create_agent(
                role=AgentRole.PROJECT_MANAGER,
                llm=get_non_code_llm(),
                memory=memory
            )
            developer_agent = AgentFactory.create_agent(
                role=AgentRole.DEVELOPER,
                llm=get_code_llm(),
                memory=memory,
                github_client=github_client,
                notification_service=notification_service
            )
            qa_agent = AgentFactory.create_agent(
                role=AgentRole.QA,
                llm=get_code_llm(),
                memory=memory,
                github_client=github_client,
                notification_service=notification_service
            )
            doc_agent = AgentFactory.create_agent(
                role=AgentRole.DOCUMENTATION,
                llm=get_non_code_llm(),
                memory=memory,
                github_client=github_client,
                notification_service=notification_service
            )
            software_registry.register(project_id, {
                "project_manager": pm_agent,
                "developer": developer_agent,
                "qa": qa_agent,
                "documentation": doc_agent
            })
            logger.info(f"Re-registered agents for resumed project {project_id}")
        
        # Recreate workflow graph with same execution mode
        graph = create_workflow_graph(
            github_client=github_client,
            with_checkpointing=True,
            execution_mode=execution_mode
        )
        
        # Configure with same thread_id to resume from checkpoint
        config = {
            "configurable": {
                "thread_id": project_id
            }
        }
        
        # Inject feedback into state before resuming (if provided)
        # original_interrupt was saved before clearing above
        # 
        # Feedback routing uses LangGraph's as_node parameter to rewind the
        # graph to a previous node's output, causing the conditional edge from
        # that node to re-evaluate with the new feedback_loop_target. This
        # correctly routes backward through the graph.
        #
        # as_node mapping:
        #   interrupt "develop" → target "plan"    → as_node="plan"    (should_continue_to_development → "plan")
        #   interrupt "test"    → target "develop"  → as_node="plan"    (should_continue_to_development → "develop")
        #   interrupt "document"→ target "test"     → as_node="develop" (should_continue_to_testing → "test")
        #   interrupt "finalize"→ target "document" → as_node="review"  (should_retry_or_finalize → "document")

        if feedback:
            current_state = graph.get_state(config)
            if current_state and current_state.values:
                existing_feedback = current_state.values.get("user_feedback", [])
                existing_feedback.append(feedback)

                # Map interrupt point → (feedback_loop_target, as_node)
                feedback_routing = {
                    "develop":  ("plan",     "plan"),     # Go back to PM for plan revision
                    "test":     ("develop",  "plan"),     # Go back to developer for code fixes
                    "document": ("test",     "develop"),  # Go back to QA for test updates
                    "finalize": ("document", "review"),   # Go back to documentation
                }

                routing = feedback_routing.get(original_interrupt)
                if routing:
                    target, as_node = routing
                    
                    # Reset downstream tasks in DB so nodes find PENDING tasks
                    _reset_downstream_tasks(project_id, target)
                    
                    graph.update_state(config, {
                        "user_feedback": existing_feedback,
                        "feedback_loop_target": target
                    }, as_node=as_node)
                    logger.info(
                        f"Injected feedback: target={target}, as_node={as_node}, "
                        f"interrupt={original_interrupt}: {feedback[:50]}..."
                    )
                else:
                    # Unknown interrupt point - just add feedback without routing
                    graph.update_state(config, {"user_feedback": existing_feedback})
                    logger.info(f"Injected feedback into state: {feedback[:50]}...")
        
        # Resume workflow (LangGraph will continue from checkpoint)
        final_state = await graph.ainvoke(None, config=config)
        
        # Check if interrupted again
        graph_state = graph.get_state(config)
        if graph_state.next:
            next_node = graph_state.next[0] if graph_state.next else None            
            with get_db_context() as db:
                project = db.query(Project).filter_by(id=project_id).first()
                if project:
                    project.requires_approval = 1
                    project.current_interrupt = next_node
                    db.commit()
            
            return {
                **final_state,
                "status": "interrupted",
                "requires_approval": True,
                "current_interrupt": next_node
            }
        
        # Workflow fully completed – clean up agents
        software_registry.remove(project_id)
        return final_state
        
    except Exception as e:
        software_registry.remove(project_id)
        error_msg = f"Workflow resumption failed: {str(e)}"
        raise Exception(error_msg) from e


async def cancel_workflow(project_id: str) -> Dict[str, Any]:
    """
    Cancel an interrupted or running workflow
    
    Args:
        project_id: Project identifier
        
    Returns:
        Cancellation status
    """
    from models.database import get_db_context
    from models.models import Project, ProjectStatus    
    try:
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=project_id).first()
            
            if not project:
                raise Exception(f"Project {project_id} not found")
            
            project.status = ProjectStatus.CANCELLED
            project.requires_approval = 0
            project.current_interrupt = None
            db.commit()
        
        software_registry.remove(project_id)
        
        return {
            "status": "cancelled",
            "project_id": project_id,
            "message": "Workflow cancelled successfully"
        }
        
    except Exception as e:
        error_msg = f"Workflow cancellation failed: {str(e)}"
        raise Exception(error_msg) from e
