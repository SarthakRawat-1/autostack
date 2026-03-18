# File: workflows/nodes.py
"""
Workflow Node Functions

Implements node functions for LangGraph workflow orchestration.
Each node represents a step in the autonomous development workflow.

Implements: Requirements 1.2, 2.4, 3.5, 4.7
"""

from typing import Dict, Any
from datetime import datetime
import logging

from workflows.state import (
    WorkflowState, WorkflowPhase, WorkflowStatus,
    update_phase, add_error, mark_task_completed, mark_task_failed
)
from models.models import Project, Task, TaskStatus, ProjectStatus
from models.database import get_db_context
from agents.base import TaskResult
from utils.logging import log_to_db

logger = logging.getLogger(__name__)


async def initialize_project(state: WorkflowState) -> WorkflowState:
    """
    Initialize project and setup repository
    
    Creates project record in database and initializes GitHub repository
    if not already created.
    
    Implements: Requirement 1.1 - Project initialization
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    log_to_db(state.get('project_id'), 'INFO', f"Initializing project: {state['project_id']}")
    
    try:
        # Update phase
        state = update_phase(state, WorkflowPhase.INITIALIZING, WorkflowStatus.RUNNING)
        
        # Update project status in database
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=state["project_id"]).first()
            
            if project:
                project.status = ProjectStatus.INITIALIZING
                project.current_phase = str(WorkflowPhase.INITIALIZING)
                project.updated_at = datetime.utcnow()
                db.commit()
                
                log_to_db(state.get('project_id'), 'INFO', f"Project {state['project_id']} initialized in database")
            else:
                error_msg = f"Project {state['project_id']} not found in database"
                log_to_db(state.get('project_id'), 'ERROR', error_msg)
                state = add_error(state, error_msg)
                state["status"] = WorkflowStatus.FAILED
                return state
        
        # Store initialization result
        state["results"]["initialization"] = {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "project_id": state["project_id"]
        }
        
        log_to_db(state.get('project_id'), 'INFO', f"Project {state['project_id']} initialization complete")
        
        return state
        
    except Exception as e:
        error_msg = f"Project initialization failed: {str(e)}"
        log_to_db(state.get('project_id'), 'ERROR', error_msg)
        state = add_error(state, error_msg)
        state["status"] = WorkflowStatus.FAILED
        return state


async def plan_project(state: WorkflowState) -> WorkflowState:
    """
    Plan project using Project Manager agent
    
    Invokes PM agent to analyze requirements and create task breakdown.
    
    Implements: Requirement 2.4 - Task assignment and workflow transition
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    log_to_db(state.get('project_id'), 'INFO', f"Planning project: {state['project_id']}")
    
    try:
        # Update phase
        state = update_phase(state, WorkflowPhase.PLANNING, WorkflowStatus.RUNNING)
        
        # Update project status in database
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=state["project_id"]).first()
            
            if project:
                project.status = ProjectStatus.PLANNING
                project.current_phase = str(WorkflowPhase.PLANNING)
                project.updated_at = datetime.utcnow()
                db.commit()
        
        # Get PM agent from registry
        from workflows.graph import get_agents_for_project
        agents = get_agents_for_project(state["project_id"])
        pm_agent = agents.get("project_manager")
        
        if not pm_agent:
            error_msg = "Project Manager agent not found in state"
            log_to_db(state.get('project_id'), 'ERROR', error_msg)
            state = add_error(state, error_msg)
            state["status"] = WorkflowStatus.FAILED
            return state
        
        # Find PM task in database (with retry)
        pm_task = None
        pm_task_id = None
        
        import asyncio
        for i in range(10):  # Retry up to 10 times
            with get_db_context() as db:
                pm_task = db.query(Task).filter_by(
                    project_id=state["project_id"],
                    agent_role="project_manager",
                    status=TaskStatus.PENDING
                ).first()
                
                if pm_task:
                    # Update task status
                    pm_task.status = TaskStatus.IN_PROGRESS
                    pm_task.updated_at = datetime.utcnow()
                    db.commit()
                    db.refresh(pm_task)
                    pm_task_id = pm_task.id
                    break
            
            # Wait before retry
            if not pm_task:
                await asyncio.sleep(2)
        
        if not pm_task_id:
            error_msg = "Project Manager task not found"
            log_to_db(state.get('project_id'), 'ERROR', error_msg)
            state = add_error(state, error_msg)
            state["status"] = WorkflowStatus.FAILED
            return state
            

        
        # Re-query task in new session for agent processing
        with get_db_context() as db:
            pm_task = db.query(Task).filter_by(id=pm_task_id).first()
            
            if not pm_task:
                error_msg = f"PM task {pm_task_id} not found"
                log_to_db(state.get('project_id'), 'ERROR', error_msg)
                state = add_error(state, error_msg)
                state["status"] = WorkflowStatus.FAILED
                return state
        
        # Invoke PM agent (task will be re-queried inside agent)
        # Pass authenticated github_client from developer agent for import mode
        developer_agent = agents.get("developer")
        github_client_for_pm = (
            developer_agent.github_client
            if developer_agent and hasattr(developer_agent, 'github_client')
            else None
        )
        
        context = {
            "project_description": state["project_description"],
            "project_name": state["project_name"],
            "repository": state.get("repository"),
            "repository_url": state.get("repository_url"),
            "user_feedback": state.get("user_feedback", []),
            "is_import_mode": state.get("is_import_mode", False),
            "source_branch": state.get("source_branch"),
            "github_client": github_client_for_pm
        }
        
        log_to_db(state.get('project_id'), 'INFO', f"Invoking PM agent for task {pm_task_id}")
        
        # Re-query task one more time for agent processing
        with get_db_context() as db:
            pm_task = db.query(Task).filter_by(id=pm_task_id).first()
            result: TaskResult = await pm_agent.process_task(pm_task, context)
        
        # Update task with result
        with get_db_context() as db:
            pm_task = db.query(Task).filter_by(id=pm_task_id).first()
            
            if result.success:
                pm_task.status = TaskStatus.COMPLETED
                pm_task.result = result.to_dict()
                pm_task.completed_at = datetime.utcnow()
                
                log_to_db(state.get('project_id'), 'INFO', f"PM task {pm_task.id} completed successfully")
                
                # Get all tasks created by PM
                all_tasks = db.query(Task).filter_by(
                    project_id=state["project_id"]
                ).all()
                
                # Categorize tasks by role
                task_ids = [t.id for t in all_tasks]
                pending_task_ids = [
                    t.id for t in all_tasks 
                    if t.status == TaskStatus.PENDING and t.agent_role != "project_manager"
                ]
                
                state["tasks"] = task_ids
                state["pending_tasks"] = pending_task_ids
                state["completed_tasks"] = [pm_task.id]
                
                logger.info(
                    f"Planning complete: {len(task_ids)} total tasks, "
                    f"{len(pending_task_ids)} pending"
                )
                
            else:
                pm_task.status = TaskStatus.FAILED
                pm_task.error_message = result.error
                pm_task.result = result.to_dict()
                
                error_msg = f"PM task failed: {result.error}"
                log_to_db(state.get('project_id'), 'ERROR', error_msg)
                state = add_error(state, error_msg)
                state["status"] = WorkflowStatus.FAILED
            
            pm_task.updated_at = datetime.utcnow()
            db.commit()
        
        # Store planning result
        state["results"]["planning"] = result.to_dict()
        
        return state
        
    except Exception as e:
        error_msg = f"Project planning failed: {str(e)}"
        log_to_db(state.get('project_id'), 'ERROR', error_msg)
        state = add_error(state, error_msg)
        state["status"] = WorkflowStatus.FAILED
        return state


async def develop_features(state: WorkflowState) -> WorkflowState:
    """
    Develop features using Developer agent
    
    Processes all pending developer tasks sequentially.
    
    Implements: Requirement 3.5 - Task processing workflow
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    log_to_db(state.get('project_id'), 'INFO', f"Developing features for project: {state['project_id']}")
    
    try:
        # Update phase
        state = update_phase(state, WorkflowPhase.DEVELOPING, WorkflowStatus.RUNNING)
        
        # Update project status in database
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=state["project_id"]).first()
            
            if project:
                project.status = ProjectStatus.DEVELOPING
                project.current_phase = str(WorkflowPhase.DEVELOPING)
                project.updated_at = datetime.utcnow()
                db.commit()
        
        # Get Developer agent from registry
        from workflows.graph import get_agents_for_project
        agents = get_agents_for_project(state["project_id"])
        developer_agent = agents.get("developer")
        
        if not developer_agent:
            error_msg = "Developer agent not found in state"
            log_to_db(state.get('project_id'), 'ERROR', error_msg)
            state = add_error(state, error_msg)
            state["status"] = WorkflowStatus.FAILED
            return state
        
        # Get all pending developer tasks and extract IDs
        dev_task_ids = []
        with get_db_context() as db:
            dev_tasks = db.query(Task).filter_by(
                project_id=state["project_id"],
                agent_role="developer",
                status=TaskStatus.PENDING
            ).order_by(Task.priority).all()
            
            # Extract IDs before session closes
            dev_task_ids = [task.id for task in dev_tasks]
            
            log_to_db(state.get('project_id'), 'INFO', f"Found {len(dev_task_ids)} developer tasks to process")
            
            if not dev_task_ids:
                log_to_db(state.get('project_id'), 'INFO', "No developer tasks to process")
                return state
        
        # Process each developer task
        dev_results = []
        
        # Initialize context once with state values (will be updated as tasks complete)
        context = {
            "project_name": state["project_name"],
            "project_description": state["project_description"],
            "repository": state.get("repository"),
            "repository_url": state.get("repository_url"),
            "branch_name": state.get("branch_name"),
            "user_feedback": state.get("user_feedback", []),
            "is_import_mode": state.get("is_import_mode", False),
            "base_branch": state.get("source_branch") or "main"  # Use source_branch as base for new branches
        }
        
        for dev_task_id in dev_task_ids:
            try:
                log_to_db(state.get('project_id'), 'INFO', f"Processing developer task {dev_task_id}")
                
                # Update task status
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=dev_task_id).first()
                    task.status = TaskStatus.IN_PROGRESS
                    task.updated_at = datetime.utcnow()
                    db.commit()
                
                # Get task with all needed data in a session
                with get_db_context() as db:
                    dev_task = db.query(Task).filter_by(id=dev_task_id).first()
                    
                    result: TaskResult = await developer_agent.process_task(dev_task, context)
                
                # Update task with result
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=dev_task_id).first()
                    
                    if result.success:
                        task.status = TaskStatus.COMPLETED
                        task.result = result.to_dict()
                        task.completed_at = datetime.utcnow()
                        
                        state = mark_task_completed(state, dev_task_id)
                        
                        log_to_db(state.get('project_id'), 'INFO', f"Developer task {dev_task_id} completed successfully")
                        
                        # Update repository info if created (persist for subsequent tasks)
                        if result.data.get("repository"):
                            if not state.get("repository"):
                                state["repository"] = result.data.get("repository")
                                state["repository_url"] = result.data.get("repository_url")
                                log_to_db(state.get('project_id'), 'INFO', f"Repository info persisted in state: {state['repository']}")
                            
                            # Always update context with repository info for next tasks
                            context["repository"] = result.data.get("repository")
                            context["repository_url"] = result.data.get("repository_url")
                            log_to_db(state.get('project_id'), 'INFO', f"Repository info updated in context for next task")
                        
                    else:
                        task.status = TaskStatus.FAILED
                        task.error_message = result.error
                        task.result = result.to_dict()
                        
                        state = mark_task_failed(state, dev_task_id)
                        
                        error_msg = f"Developer task {dev_task_id} failed: {result.error}"
                        log_to_db(state.get('project_id'), 'ERROR', error_msg)
                        state = add_error(state, error_msg)
                    
                    task.updated_at = datetime.utcnow()
                    db.commit()
                
                dev_results.append(result.to_dict())
                
            except Exception as e:
                error_msg = f"Developer task {dev_task_id} failed: {str(e)}"
                log_to_db(state.get('project_id'), 'ERROR', error_msg)
                state = add_error(state, error_msg)
                state = mark_task_failed(state, dev_task_id)
                
                # Update task in database
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=dev_task_id).first()
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    task.updated_at = datetime.utcnow()
                    db.commit()
        
        # Store development results
        completed_count = len([r for r in dev_results if r.get("success")])
        failed_count = len([r for r in dev_results if not r.get("success")])
        
        state["results"]["development"] = {
            "tasks_processed": len(dev_task_ids),
            "tasks_completed": completed_count,
            "tasks_failed": failed_count,
            "results": dev_results
        }
        
        logger.info(
            f"Development phase complete: "
            f"{completed_count} completed, {failed_count} failed"
        )
        
        # Create PR after all developer tasks complete (if any succeeded)
        if completed_count > 0 and state.get("repository"):
            try:
                log_to_db(state.get('project_id'), 'INFO', "Creating pull request for all completed developer tasks")
                
                # Get branch name from first successful result
                branch_name = None
                for result in dev_results:
                    if result.get("success") and result.get("data", {}).get("branch_name"):
                        branch_name = result["data"]["branch_name"]
                        break
                
                if branch_name:
                    # Create PR using developer agent
                    from workflows.graph import get_agents_for_project
                    agents = get_agents_for_project(state["project_id"])
                    developer_agent = agents.get("developer")
                    
                    if developer_agent:
                        pr = await developer_agent.create_feature_pr(
                            task_id="all-dev-tasks",
                            task_description=f"Implement {state['project_name']} features",
                            project_id=state["project_id"],
                            branch_name=branch_name,
                            context=context
                        )
                        
                        log_to_db(state.get('project_id'), 'INFO', f"Pull request created: #{pr.number} - {pr.url}")
                        
                        # Store PR info in state
                        state["pr_number"] = pr.number
                        state["pr_url"] = pr.url
                        state["branch_name"] = branch_name
                        
                        # Send notification
                        if developer_agent.notification_service:
                            try:
                                await developer_agent.notification_service.send_pull_request_created(
                                    project_name=state["project_name"],
                                    pr_number=pr.number,
                                    pr_url=pr.url,
                                    pr_title=pr.title,
                                    branch=branch_name
                                )
                                log_to_db(state.get('project_id'), 'INFO', "Notification sent for PR creation")
                            except Exception as e:
                                log_to_db(state.get('project_id'), 'WARNING', f"Failed to send notification: {e}")
                    else:
                        log_to_db(state.get('project_id'), 'WARNING', "Developer agent not found, skipping PR creation")
                else:
                    log_to_db(state.get('project_id'), 'WARNING', "No branch name found, skipping PR creation")
                    
            except Exception as e:
                log_to_db(state.get('project_id'), 'ERROR', f"Failed to create PR: {e}")
                # Don't fail the whole workflow if PR creation fails
        
        return state
        
    except Exception as e:
        error_msg = f"Feature development failed: {str(e)}"
        log_to_db(state.get('project_id'), 'ERROR', error_msg)
        state = add_error(state, error_msg)
        state["status"] = WorkflowStatus.FAILED
        return state


async def test_code(state: WorkflowState) -> WorkflowState:
    """
    Test code using QA agent
    
    Processes all pending QA tasks sequentially.
    
    Implements: Requirement 4.7 - QA workflow integration
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    log_to_db(state.get('project_id'), 'INFO', f"Testing code for project: {state['project_id']}")
    
    try:
        # Update phase
        state = update_phase(state, WorkflowPhase.TESTING, WorkflowStatus.RUNNING)
        
        # Update project status in database
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=state["project_id"]).first()
            
            if project:
                project.status = ProjectStatus.TESTING
                project.current_phase = str(WorkflowPhase.TESTING)
                project.updated_at = datetime.utcnow()
                db.commit()
        
        # Get QA agent from registry
        from workflows.graph import get_agents_for_project
        agents = get_agents_for_project(state["project_id"])
        qa_agent = agents.get("qa")
        
        if not qa_agent:
            log_to_db(state.get('project_id'), 'WARNING', "QA agent not found in state, skipping testing phase")
            return state
        
        # Get all pending QA tasks and extract IDs
        qa_task_ids = []
        with get_db_context() as db:
            qa_tasks = db.query(Task).filter_by(
                project_id=state["project_id"],
                agent_role="qa",
                status=TaskStatus.PENDING
            ).order_by(Task.priority).all()
            
            # Extract IDs before session closes
            qa_task_ids = [task.id for task in qa_tasks]
            
            log_to_db(state.get('project_id'), 'INFO', f"Found {len(qa_task_ids)} QA tasks to process")
            
            if not qa_task_ids:
                log_to_db(state.get('project_id'), 'INFO', "No QA tasks to process")
                return state
        
        # Process each QA task
        qa_results = []
        
        for qa_task_id in qa_task_ids:
            try:
                log_to_db(state.get('project_id'), 'INFO', f"Processing QA task {qa_task_id}")
                
                # Update task status
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=qa_task_id).first()
                    task.status = TaskStatus.IN_PROGRESS
                    task.updated_at = datetime.utcnow()
                    db.commit()
                
                # Get task with all needed data in a session
                with get_db_context() as db:
                    qa_task = db.query(Task).filter_by(id=qa_task_id).first()
                    
                    # Invoke QA agent while task is still attached to session
                    context = {
                        "project_name": state["project_name"],
                        "project_description": state["project_description"],
                        "repository": state.get("repository"),
                        "repository_url": state.get("repository_url"),
                        "pr_number": state.get("pr_number"),
                        "pr_url": state.get("pr_url"),
                        "branch_name": state.get("branch_name"),
                        "user_feedback": state.get("user_feedback", [])
                    }
                    
                    result: TaskResult = await qa_agent.process_task(qa_task, context)
                
                # Update task with result
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=qa_task_id).first()
                    
                    if result.success:
                        task.status = TaskStatus.COMPLETED
                        task.result = result.to_dict()
                        task.completed_at = datetime.utcnow()
                        
                        state = mark_task_completed(state, qa_task_id)
                        
                        log_to_db(state.get('project_id'), 'INFO', f"QA task {qa_task_id} completed successfully")
                        
                    else:
                        task.status = TaskStatus.FAILED
                        task.error_message = result.error
                        task.result = result.to_dict()
                        
                        state = mark_task_failed(state, qa_task_id)
                        
                        error_msg = f"QA task {qa_task_id} failed: {result.error}"
                        log_to_db(state.get('project_id'), 'ERROR', error_msg)
                        state = add_error(state, error_msg)
                    
                    task.updated_at = datetime.utcnow()
                    db.commit()
                
                qa_results.append(result.to_dict())
                
            except Exception as e:
                error_msg = f"QA task {qa_task_id} failed: {str(e)}"
                log_to_db(state.get('project_id'), 'ERROR', error_msg)
                state = add_error(state, error_msg)
                state = mark_task_failed(state, qa_task_id)
                
                # Update task in database
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=qa_task_id).first()
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    task.updated_at = datetime.utcnow()
                    db.commit()
        
        # Store testing results with CI status for fix detection
        # Extract CI status from results to check for failures
        ci_failed = False
        for r in qa_results:
            if r.get("success") and isinstance(r.get("data"), dict):
                ci_status = r["data"].get("github_actions_status", {})
                if ci_status and ci_status.get("conclusion") == "failure":
                    ci_failed = True
                    break
        
        state["results"]["testing"] = {
            "tasks_processed": len(qa_task_ids),
            "tasks_completed": len([r for r in qa_results if r.get("success")]),
            "tasks_failed": len([r for r in qa_results if not r.get("success")]),
            "results": qa_results,
            "ci_failed": ci_failed  # Flag for fix_ci conditional edge
        }
        
        logger.info(
            f"Testing phase complete: "
            f"{state['results']['testing']['tasks_completed']} completed, "
            f"{state['results']['testing']['tasks_failed']} failed"
        )
        
        return state
        
    except Exception as e:
        error_msg = f"Code testing failed: {str(e)}"
        log_to_db(state.get('project_id'), 'ERROR', error_msg)
        state = add_error(state, error_msg)
        state["status"] = WorkflowStatus.FAILED
        return state


async def generate_documentation(state: WorkflowState) -> WorkflowState:
    """
    Generate documentation using Documentation agent
    
    Processes all pending documentation tasks sequentially.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    log_to_db(state.get('project_id'), 'INFO', f"Generating documentation for project: {state['project_id']}")
    
    try:
        # Update phase
        state = update_phase(state, WorkflowPhase.DOCUMENTING, WorkflowStatus.RUNNING)
        
        # Update project status in database
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=state["project_id"]).first()
            
            if project:
                project.status = ProjectStatus.DOCUMENTING
                project.current_phase = str(WorkflowPhase.DOCUMENTING)
                project.updated_at = datetime.utcnow()
                db.commit()
        
        # Get Documentation agent from registry
        from workflows.graph import get_agents_for_project
        agents = get_agents_for_project(state["project_id"])
        doc_agent = agents.get("documentation")
        
        if not doc_agent:
            log_to_db(state.get('project_id'), 'WARNING', "Documentation agent not found in state, skipping documentation phase")
            return state
        
        # Get all pending documentation tasks and extract IDs
        doc_task_ids = []
        with get_db_context() as db:
            doc_tasks = db.query(Task).filter_by(
                project_id=state["project_id"],
                agent_role="documentation",
                status=TaskStatus.PENDING
            ).order_by(Task.priority).all()
            
            # Extract IDs before session closes
            doc_task_ids = [task.id for task in doc_tasks]
            
            log_to_db(state.get('project_id'), 'INFO', f"Found {len(doc_task_ids)} documentation tasks to process")
            
            if not doc_task_ids:
                log_to_db(state.get('project_id'), 'INFO', "No documentation tasks to process")
                return state
        
        # Process each documentation task
        doc_results = []
        
        for doc_task_id in doc_task_ids:
            try:
                log_to_db(state.get('project_id'), 'INFO', f"Processing documentation task {doc_task_id}")
                
                # Update task status
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=doc_task_id).first()
                    task.status = TaskStatus.IN_PROGRESS
                    task.updated_at = datetime.utcnow()
                    db.commit()
                
                # Get task with all needed data in a session
                with get_db_context() as db:
                    doc_task = db.query(Task).filter_by(id=doc_task_id).first()
                    
                    # Invoke Documentation agent while task is still attached to session
                    context = {
                        "project_name": state["project_name"],
                        "project_description": state["project_description"],
                        "repository": state.get("repository"),
                        "repository_url": state.get("repository_url"),
                        "pr_number": state.get("pr_number"),
                        "pr_url": state.get("pr_url"),
                        "branch_name": state.get("branch_name"),
                        "user_feedback": state.get("user_feedback", [])
                    }
                    
                    result: TaskResult = await doc_agent.process_task(doc_task, context)
                
                # Update task with result
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=doc_task_id).first()
                    
                    if result.success:
                        task.status = TaskStatus.COMPLETED
                        task.result = result.to_dict()
                        task.completed_at = datetime.utcnow()
                        
                        state = mark_task_completed(state, doc_task_id)
                        
                        log_to_db(state.get('project_id'), 'INFO', f"Documentation task {doc_task_id} completed successfully")
                        
                    else:
                        task.status = TaskStatus.FAILED
                        task.error_message = result.error
                        task.result = result.to_dict()
                        
                        state = mark_task_failed(state, doc_task_id)
                        
                        error_msg = f"Documentation task {doc_task_id} failed: {result.error}"
                        log_to_db(state.get('project_id'), 'ERROR', error_msg)
                        state = add_error(state, error_msg)
                    
                    task.updated_at = datetime.utcnow()
                    db.commit()
                
                doc_results.append(result.to_dict())
                
            except Exception as e:
                error_msg = f"Documentation task {doc_task_id} failed: {str(e)}"
                log_to_db(state.get('project_id'), 'ERROR', error_msg)
                state = add_error(state, error_msg)
                state = mark_task_failed(state, doc_task_id)
                
                # Update task in database
                with get_db_context() as db:
                    task = db.query(Task).filter_by(id=doc_task_id).first()
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    task.updated_at = datetime.utcnow()
                    db.commit()
        
        # Store documentation results
        state["results"]["documentation"] = {
            "tasks_processed": len(doc_task_ids),
            "tasks_completed": len([r for r in doc_results if r.get("success")]),
            "tasks_failed": len([r for r in doc_results if not r.get("success")]),
            "results": doc_results
        }
        
        logger.info(
            f"Documentation phase complete: "
            f"{state['results']['documentation']['tasks_completed']} completed, "
            f"{state['results']['documentation']['tasks_failed']} failed"
        )
        
        return state
        
    except Exception as e:
        error_msg = f"Documentation generation failed: {str(e)}"
        log_to_db(state.get('project_id'), 'ERROR', error_msg)
        state = add_error(state, error_msg)
        state["status"] = WorkflowStatus.FAILED
        return state


async def review_results(state: WorkflowState) -> WorkflowState:
    """
    Review workflow results and determine next steps
    
    Analyzes completed tasks and decides whether to continue,
    retry failed tasks, or finalize the project.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    log_to_db(state.get('project_id'), 'INFO', f"Reviewing results for project: {state['project_id']}")
    
    try:
        # Update phase
        state = update_phase(state, WorkflowPhase.REVIEWING, WorkflowStatus.RUNNING)
        
        # Count task statuses
        total_tasks = len(state.get("tasks", []))
        completed_tasks = len(state.get("completed_tasks", []))
        failed_tasks = len(state.get("failed_tasks", []))
        pending_tasks = len(state.get("pending_tasks", []))
        
        logger.info(
            f"Task summary: {completed_tasks}/{total_tasks} completed, "
            f"{failed_tasks} failed, {pending_tasks} pending"
        )
        
        # Store review results
        state["results"]["review"] = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "pending_tasks": pending_tasks,
            "success_rate": completed_tasks / total_tasks if total_tasks > 0 else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return state
        
    except Exception as e:
        error_msg = f"Results review failed: {str(e)}"
        log_to_db(state.get('project_id'), 'ERROR', error_msg)
        state = add_error(state, error_msg)
        state["status"] = WorkflowStatus.FAILED
        return state


async def finalize_project(state: WorkflowState) -> WorkflowState:
    """
    Finalize project and mark as complete
    
    Updates project status, sends notifications, and performs cleanup.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    log_to_db(state.get('project_id'), 'INFO', f"Finalizing project: {state['project_id']}")
    
    try:
        # Update phase
        state = update_phase(state, WorkflowPhase.FINALIZING, WorkflowStatus.RUNNING)
        
        # Gather statistics
        total_tasks = len(state.get("tasks", []))
        completed_tasks = len(state.get("completed_tasks", []))
        failed_tasks = len(state.get("failed_tasks", []))
        errors = state.get("errors", [])
        
        logger.info(f"Finalizing project {state['project_id']}")
        logger.info(f"  Total tasks: {total_tasks}")
        logger.info(f"  Completed tasks: {completed_tasks}")
        logger.info(f"  Failed tasks: {failed_tasks}")
        logger.info(f"  Errors: {len(errors)}")
        
        # Determine final status
        if failed_tasks > 0:
            final_status = ProjectStatus.FAILED
            workflow_status = WorkflowStatus.FAILED
            log_to_db(state.get('project_id'), 'WARNING', f"Project completed with {failed_tasks} failed tasks")
        elif total_tasks == 0 or (completed_tasks == 0 and len(errors) > 0):
            # No tasks created or no work done with errors = failed
            final_status = ProjectStatus.FAILED
            workflow_status = WorkflowStatus.FAILED
            log_to_db(state.get('project_id'), 'ERROR', f"Project failed - no work completed (tasks: {total_tasks}, errors: {len(errors)})")
        elif completed_tasks == 0 and total_tasks > 0:
            # Tasks exist but none completed = failed
            final_status = ProjectStatus.FAILED
            workflow_status = WorkflowStatus.FAILED
            log_to_db(state.get('project_id'), 'ERROR', f"Project failed - {total_tasks} tasks created but none completed")
        else:
            final_status = ProjectStatus.COMPLETED
            workflow_status = WorkflowStatus.COMPLETED
            log_to_db(state.get('project_id'), 'INFO', f"Project completed successfully with {completed_tasks}/{total_tasks} tasks")
        
        # Update project in database
        with get_db_context() as db:
            project = db.query(Project).filter_by(id=state["project_id"]).first()
            
            if project:
                project.status = final_status
                project.current_phase = str(WorkflowPhase.COMPLETED)
                project.completed_at = datetime.utcnow()
                project.updated_at = datetime.utcnow()
                db.commit()
                
                log_to_db(state.get('project_id'), 'INFO', f"Project {state['project_id']} marked as {final_status}")
        
        # Update workflow state
        state = update_phase(state, WorkflowPhase.COMPLETED, workflow_status)
        state["completed_at"] = datetime.utcnow().isoformat()
        
        # Store finalization result
        state["results"]["finalization"] = {
            "final_status": str(final_status),
            "completed_at": state["completed_at"],
            "total_tasks": len(state.get("tasks", [])),
            "completed_tasks": len(state.get("completed_tasks", [])),
            "failed_tasks": failed_tasks
        }
        
        log_to_db(state.get('project_id'), 'INFO', f"Project {state['project_id']} finalization complete")
        
        return state
        
    except Exception as e:
        error_msg = f"Project finalization failed: {str(e)}"
        log_to_db(state.get('project_id'), 'ERROR', error_msg)
        state = add_error(state, error_msg)
        state["status"] = WorkflowStatus.FAILED
        return state



