# File: agents/project_manager.py
"""
The PM agent analyzes project requirements, creates task breakdowns,
and assigns tasks to appropriate agents.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from agents.base import BaseAgent, TaskResult, BaseAgentError
from agents.config import AgentRole, ProjectManagerConfig
from agents.schemas.pm import ProjectPlan, TaskBreakdown
from agents.prompts.pm import (
    PROJECT_ANALYSIS_SYSTEM_PROMPT,
    PROJECT_ANALYSIS_USER_PROMPT_TEMPLATE,
    TASK_BREAKDOWN_SYSTEM_PROMPT,
    TASK_BREAKDOWN_USER_PROMPT_TEMPLATE,
)
from models.models import Task, TaskStatus, Project, ProjectStatus
from models.database import get_db_context
from langchain_core.language_models import BaseChatModel
from services.memory import AgentMemory
from services.research import TavilyResearchService, get_research_service
from utils.logging import log_to_db, LogType
from utils.project_analysis import assess_complexity_level

import logging
logger = logging.getLogger(__name__)




class ProjectManagerAgent(BaseAgent):
    def __init__(
        self,
        llm: BaseChatModel,
        memory: AgentMemory,
        config: Optional[ProjectManagerConfig] = None,
        **kwargs
    ):
        super().__init__(llm, memory, config, **kwargs)

        # Use config values if provided
        if self.config:
            self.temperature = self.config.llm_temperature
            self.max_tokens = self.config.llm_max_tokens
            self.min_tasks = self.config.min_tasks
            self.max_tasks = self.config.max_tasks
            self.task_priority_levels = self.config.task_priority_levels
            self.include_dependencies = self.config.include_dependencies
        else:
            self.temperature = 0.7
            self.max_tokens = 4000
            self.min_tasks = 3
            self.max_tasks = 20
            self.task_priority_levels = 5
            self.include_dependencies = True

        # Default task limits for different complexities
        self.simple_task_limits = {'min_tasks': 1, 'max_tasks': 3}
        self.medium_task_limits = {'min_tasks': 3, 'max_tasks': 8}
        self.complex_task_limits = {'min_tasks': 5, 'max_tasks': 20}
        
        # Research service for up-to-date tech recommendations
        self.research_service: TavilyResearchService = get_research_service()
    
    def get_role(self) -> str:
        return AgentRole.PROJECT_MANAGER.value
    
    async def process_task(self, task: Task, context: Dict[str, Any]) -> TaskResult:
        # Extract task data immediately to avoid detached instance errors
        task_id = task.id
        task_description = task.description
        project_id = task.project_id
        
        log_to_db(project_id, "INFO", f"Processing PM task {task_id}: {task_description}", agent_role="project_manager")
        
        try:
            # Store task context in memory
            await self.store_memory(
                key=f"task_{task_id}",
                value=task_description,
                memory_type="task",
                project_id=project_id
            )
            
            # Get project details
            project_description = context.get("project_description", "")
            project_name = context.get("project_name", "Unknown Project")
            
            # Extract user feedback for refinement loop
            user_feedback_list = context.get("user_feedback", [])
            user_feedback_str = "\n".join(user_feedback_list) if user_feedback_list else "None"
            
            # Retrieve previous plan from memory if refining
            previous_plan_str = "None"
            if user_feedback_list:
                try:
                    prev_plan_mem = await self.retrieve_memory_by_key(
                        key=f"project_plan_{project_id}",
                        project_id=project_id,
                        collection_type="code_artifacts"
                    )
                    if prev_plan_mem and prev_plan_mem.get("content"):
                        previous_plan_str = prev_plan_mem["content"]
                        self._log("INFO", "Retrieved previous plan for refinement")
                except Exception:
                    pass
            
            # Fetch RepoMap for import mode (existing repository)
            current_codebase = "None"
            is_import_mode = context.get("is_import_mode", False)
            if is_import_mode:
                repository = context.get("repository")
                repository_url = context.get("repository_url")
                if repository or repository_url:
                    try:
                        from services.repomap.service import get_repomap_service

                        # Use authenticated GitHub client from context (passed by workflow node)
                        # Falls back to system-level token if not provided
                        github_client = context.get("github_client")
                        if not github_client:
                            from services.github_client import GitHubClient
                            github_client = GitHubClient()

                        repomap_service = get_repomap_service()

                        repo_name = repository or repository_url.rstrip("/").split("/")[-2] + "/" + repository_url.rstrip("/").split("/")[-1]
                        source_branch = context.get("source_branch") or "main"
                        repo_map = await repomap_service.get_repo_map_via_api(
                            github_client=github_client,
                            repository=repo_name,
                            branch=source_branch,
                            max_files=30
                        )
                        if repo_map:
                            current_codebase = repo_map
                            self._log("INFO", f"Fetched RepoMap for existing repository: {repo_name}")

                            # Store in memory for other agents (especially Developer agent to avoid duplicate RepoMap calls)
                            await self.store_memory(
                                key=f"repo_map_{project_id}",
                                value=repo_map,
                                memory_type="repo_map",
                                project_id=project_id,
                                collection_type="code_artifacts"
                            )

                            # Also store as codebase context for agents that need it
                            await self.store_memory(
                                key=f"codebase_context_{project_id}",
                                value=repo_map,
                                memory_type="codebase_context",
                                project_id=project_id,
                                collection_type="code_artifacts"
                            )
                    except Exception as e:
                        self._log("DEBUG", f"Could not fetch RepoMap for import: {e}")
            
            # Analyze requirements and create plan
            project_plan = await self.analyze_requirements(
                project_name, project_description, user_feedback_str, previous_plan_str, current_codebase
            )
            
            # Store plan in memory
            await self.store_memory(
                key=f"project_plan_{project_id}",
                value=json.dumps(project_plan),
                memory_type="plan",
                project_id=project_id
            )
            
            # Create task breakdown
            tasks = await self.create_task_breakdown(project_plan, project_id)
            
            # Assign tasks to agents
            assignments = await self.assign_tasks(tasks, project_id)
            
            log_to_db(project_id, "INFO", f"PM task {task_id} completed successfully - created {len(tasks)} tasks", agent_role="project_manager")
            return TaskResult(
                success=True,
                data={
                    "project_plan": project_plan,
                    "tasks_created": len(tasks),
                    "assignments": assignments
                },
                metadata={
                    "task_id": task_id,
                    "agent_role": self.role,
                    "project_id": project_id
                }
            )
            
        except Exception as e:
            log_to_db(project_id, "ERROR", f"PM task {task_id} failed: {str(e)}", agent_role="project_manager")
            return TaskResult(
                success=False,
                error=str(e),
                metadata={"task_id": task_id, "agent_role": self.role}
            )
    
    async def analyze_requirements(
        self, project_name: str, description: str,
        user_feedback: str = "None", previous_plan: str = "None",
        current_codebase: str = "None"
    ) -> Dict[str, Any]:
        if not description or not description.strip():
            raise ValueError("Project description cannot be empty")
        # Build system prompt using external template
        system_prompt = self.build_system_prompt(
            additional_instructions=PROJECT_ANALYSIS_SYSTEM_PROMPT
        )

        # Get research context for current tech recommendations (now pre-summarized)
        research_context = ""
        try:
            # Extract project type from description
            project_types = ["api", "web", "cli", "mobile"]
            detected_type = "software"
            for pt in project_types:
                if pt in description.lower():
                    detected_type = pt
                    break

            tech_info = await self.research_service.search_tech_stack(
                project_type=f"{detected_type} project",
                requirements=description[:100]  # Reduced from 200
            )
            if tech_info.get("recommendations"):
                # Now returns compact summary like "Recommended: FastAPI, PostgreSQL, Docker"
                research_context = f"\nTech context: {tech_info['recommendations']}"
        except Exception as e:
            self._log("DEBUG", f"Research context unavailable: {e}")

        # Check if we have user feedback to determine which prompt to use
        if user_feedback and user_feedback != "None" and previous_plan and previous_plan != "None":
            # Use feedback-specific prompt that ensures complete plan generation
            user_prompt = PROJECT_ANALYSIS_WITH_FEEDBACK_USER_PROMPT_TEMPLATE.format(
                project_name=project_name,
                project_description=description + research_context,
                previous_plan=previous_plan,
                current_codebase=current_codebase,
                user_feedback=user_feedback
            )
        else:
            # Use normal prompt for initial planning
            user_prompt = PROJECT_ANALYSIS_USER_PROMPT_TEMPLATE.format(
                project_name=project_name,
                project_description=description + research_context,
                user_feedback=user_feedback,
                previous_plan=previous_plan,
                current_codebase=current_codebase
            )

        # Invoke LLM with Pydantic schema for structured output
        try:
            plan = await self.invoke_llm_structured(
                prompt=user_prompt,
                schema=ProjectPlan,  # Use Pydantic model class
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # Pydantic handles validation automatically

            # Assess project complexity level
            complexity_level = self._assess_complexity_level(plan)
            plan['complexity_level'] = complexity_level

            self._log("INFO", f"Successfully analyzed requirements: {plan.get('complexity')} complexity ({complexity_level} level)")

            return plan

        except Exception as e:
            raise ValueError(f"Requirement analysis failed: {str(e)}") from e

    

    # NOTE: _get_project_plan_schema() and _validate_project_plan() removed
    # Now using ProjectPlan Pydantic model for structured output + validation


    def _assess_complexity_level(self, project_plan: Dict[str, Any]) -> str:
        features = project_plan.get("features", [])
        goals = project_plan.get("goals", [])
        challenges = project_plan.get("challenges", [])
        return assess_complexity_level(features, goals, challenges)

    def _adjust_task_limits_by_complexity(self, complexity_level: str) -> None:
        if complexity_level == 'simple':
            self.min_tasks = self.simple_task_limits['min_tasks']
            self.max_tasks = self.simple_task_limits['max_tasks']
        elif complexity_level == 'medium':
            self.min_tasks = self.medium_task_limits['min_tasks']
            self.max_tasks = self.medium_task_limits['max_tasks']
        elif complexity_level == 'complex':
            self.min_tasks = self.complex_task_limits['min_tasks']
            self.max_tasks = self.complex_task_limits['max_tasks']
    async def create_task_breakdown(
        self,
        project_plan: Dict[str, Any],
        project_id: str
    ) -> List[Task]:
        # Adjust task limits based on project complexity level
        complexity_level = project_plan.get('complexity_level', 'medium')
        self._adjust_task_limits_by_complexity(complexity_level)

        # Build system prompt using external template
        system_prompt = self.build_system_prompt(
            additional_instructions=TASK_BREAKDOWN_SYSTEM_PROMPT
        )

        # Prepare context for prompt template
        # Format project plan as readable text for the LLM
        goals_text = "\n".join([f"- {g}" for g in project_plan.get("goals", [])])
        features_text = "\n".join([
            f"- {f['name']} ({f['priority']} priority): {f['description']}"
            for f in project_plan.get("features", [])
        ])
        technical_approach = project_plan.get('technical_approach', 'Not specified')
        
        project_plan_text = f"""Goals:
{goals_text}

Features:
{features_text}

Technical Approach: {technical_approach}
Complexity: {project_plan.get('complexity', 'medium')}"""
        
        # Build user prompt using external template
        user_prompt = TASK_BREAKDOWN_USER_PROMPT_TEMPLATE.format(
            project_plan=project_plan_text,
            requirements=project_plan.get('technical_approach', 'Build the described features'),
            min_tasks=self.min_tasks,
            max_tasks=self.max_tasks
        )
        
        # Invoke LLM with Pydantic schema for structured output
        try:
            breakdown = await self.invoke_llm_structured(
                prompt=user_prompt,
                schema=TaskBreakdown,  # Use Pydantic model
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Validate the response
            if breakdown is None:
                raise ValueError("LLM returned None for task breakdown")
            
            # Handle different response types
            if hasattr(breakdown, 'model_dump'):
                breakdown = breakdown.model_dump()
            elif hasattr(breakdown, 'dict'):
                breakdown = breakdown.dict()
            
            tasks_list = breakdown.get("tasks") if isinstance(breakdown, dict) else None
            if tasks_list is None or not isinstance(tasks_list, list):
                self._log("ERROR", f"Invalid breakdown response: {type(breakdown)} - {breakdown}")
                raise ValueError(f"LLM response missing 'tasks' array. Got: {type(breakdown)}")
            
            if len(tasks_list) == 0:
                raise ValueError("LLM returned empty tasks array")
            
            self._log("INFO", f"LLM generated {len(tasks_list)} tasks")
            
            # Create Task objects and store in database
            tasks = []
            task_id_map = {}  # Map indices to task IDs
            
            with get_db_context() as db:
                for idx, task_data in enumerate(tasks_list):
                    # Create task object
                    task = Task(
                        project_id=project_id,
                        agent_role=task_data["agent_role"],
                        status=TaskStatus.PENDING,
                        priority=task_data["priority"],
                        description=task_data["description"],
                        requirements=task_data.get("requirements", ""),
                        dependencies=[]  # Will be updated after all tasks created
                    )
                    
                    db.add(task)
                    db.flush()  # Get task ID
                    
                    tasks.append(task)
                    task_id_map[idx] = task.id
                    
                    self._log(
                        "DEBUG",
                        f"Created task {task.id}: {task.description[:50]}... (role={task.agent_role}, priority={task.priority})",
                        LogType.TASK_START
                    )
                
                # Update dependencies with actual task IDs
                for idx, task_data in enumerate(tasks_list):
                    if self.include_dependencies:
                        dep_indices = task_data.get("dependencies") or []
                        if dep_indices:
                            dep_ids = [task_id_map[dep_idx] for dep_idx in dep_indices if dep_idx in task_id_map]
                            tasks[idx].dependencies = dep_ids
                
                # Commit all tasks
                db.commit()
                
                # Refresh to get all fields and extract IDs before session closes
                task_ids = []
                for task in tasks:
                    db.refresh(task)
                    task_ids.append(task.id)
            
            self._log(
                "INFO",
                f"Created {len(tasks)} tasks for project {project_id}",
                LogType.TASK_COMPLETE
            )
            
            # Store task breakdown in memory
            await self.store_memory(
                key=f"task_breakdown_{project_id}",
                value=json.dumps({
                    "task_count": len(tasks),
                    "task_ids": task_ids,  # Use extracted IDs
                    "breakdown": breakdown
                }),
                memory_type="task_breakdown",
                project_id=project_id
            )
            
            return tasks
            
        except Exception as e:
            raise ValueError(f"Task breakdown creation failed: {str(e)}") from e
    
    async def assign_tasks(
        self,
        tasks: List[Task],
        project_id: str
    ) -> Dict[str, List[str]]:
        self._log("INFO", f"Assigning {len(tasks)} tasks for project {project_id}")
        
        # Group tasks by agent role
        assignments: Dict[str, List[str]] = {
            "developer": [],
            "qa": [],
            "documentation": []
        }
        
        try:
            # Re-query tasks from database to avoid detached instance issues
            with get_db_context() as db:
                # Get all tasks for this project
                all_tasks = db.query(Task).filter_by(project_id=project_id).all()
                
                # Sort tasks by priority (lower number = higher priority)
                sorted_tasks = sorted(all_tasks, key=lambda t: t.priority)
                
                for task in sorted_tasks:
                    # Task is already assigned to an agent role from creation
                    # Here we just track the assignments
                    agent_role = task.agent_role
                    
                    if agent_role in assignments:
                        assignments[agent_role].append(task.id)
                        
                        self._log(
                            "DEBUG",
                            f"Assigned task {task.id} to {agent_role} (priority={task.priority})"
                        )
                    else:
                        pass
                
                # Update project status to PLANNING -> DEVELOPING
                project = db.query(Project).filter_by(id=project_id).first()
                if project:
                    project.status = ProjectStatus.DEVELOPING
                    project.current_phase = "development"
                    project.updated_at = datetime.utcnow()
                else:
                    pass
                
                db.commit()
            
            # Store assignments in memory
            await self.store_memory(
                key=f"task_assignments_{project_id}",
                value=json.dumps(assignments),
                memory_type="assignments",
                project_id=project_id
            )
            
            # Log assignment summary
            summary = ", ".join([
                f"{role}: {len(task_ids)} tasks"
                for role, task_ids in assignments.items()
                if task_ids
            ])
            return assignments
            
        except Exception as e:
            raise ValueError(f"Task assignment failed: {str(e)}") from e

# Register agent with factory
from agents.config import AgentFactory
AgentFactory.register_agent(AgentRole.PROJECT_MANAGER, ProjectManagerAgent)
