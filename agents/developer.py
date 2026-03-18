"""
This module implements the Developer Agent for AutoStack.
The Developer agent analyzes feature requirements, plans architecture,
generates code in batches, and manages GitHub operations including
branch creation, commits, and pull requests.
"""

import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base import BaseAgent, TaskResult, BaseAgentError
from agents.config import AgentRole, DeveloperConfig
from agents.schemas.developer import ArchitecturePlan, FeatureGeneration
from agents.prompts.developer import (
    ARCHITECTURE_SYSTEM_PROMPT,
    ARCHITECTURE_USER_PROMPT_TEMPLATE,
    FEATURE_GENERATION_SYSTEM_PROMPT,
    FEATURE_GENERATION_SYSTEM_ADDENDUM,
    FEATURE_GENERATION_USER_PROMPT_TEMPLATE,
    FEEDBACK_ANALYSIS_SYSTEM_PROMPT,
    FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE,
)
from models.models import Task, TaskStatus
from langchain_core.language_models import BaseChatModel
from services.github_client import GitHubClient, FileChange
from services.memory import AgentMemory
from services.notification import NotificationService
from services.research import TavilyResearchService, get_research_service
from agents.templates.developer_pr import FEATURE_PR_BODY_TEMPLATE
from utils.logging import log_to_db, LogType
from models.database import get_db_context
from models.models import Project

import logging
logger = logging.getLogger(__name__)




class DeveloperAgent(BaseAgent):
    def __init__(
        self,
        llm: BaseChatModel,
        memory: AgentMemory,
        github_client: GitHubClient,
        notification_service: Optional[NotificationService] = None,
        config: Optional[DeveloperConfig] = None,
        **kwargs
    ):
        super().__init__(llm, memory, config, **kwargs)

        # Client dependencies
        self.github_client = github_client
        self.notification_service = notification_service

        # Use config values if provided
        if self.config:
            self.temperature = self.config.llm_temperature
            self.max_tokens = self.config.llm_max_tokens
            self.batch_size = self.config.batch_size
            self.branch_prefix = self.config.branch_prefix
            self.max_file_size = self.config.max_file_size
            self.code_style = self.config.code_style
        else:
            self.temperature = 0.7
            self.max_tokens = 4000
            self.batch_size = 4  # Generate 2-5 files per batch
            self.branch_prefix = "feature/"
            self.max_file_size = 100000  # 100KB max file size
            self.code_style = "pep8"

        # Instance state for tracking current operation
        self.architecture_plan: Optional[Dict[str, Any]] = None
        self.feature_batches: List[Dict[str, Any]] = []
        self.current_branch: Optional[str] = None
        self.research_context: Optional[str] = None  # Cached research (done once at architecture phase)
        self._current_project_id: Optional[str] = None  # Track current project for memory operations

        # Research service for up-to-date context
        self.research_service: TavilyResearchService = get_research_service()

    def get_role(self) -> str:
        return AgentRole.DEVELOPER.value

    async def process_task(self, task: Task, context: Dict[str, Any]) -> TaskResult:
        # Extract task data immediately to avoid detached instance errors
        task_id = task.id
        task_description = task.description
        task_requirements = task.requirements
        project_id = task.project_id
        
        log_to_db(project_id, "INFO", f"Processing developer task {task_id}: {task_description}", agent_role="developer")
        
        try:
            # Store task context in memory
            await self.store_memory(
                key=f"task_{task_id}",
                value=task_description,
                memory_type="task",
                project_id=project_id,
                collection_type="agent_memory"
            )

            # Check if repository exists, create if needed
            # For import mode: repository_url is provided but repository might not be set
            is_import_mode = context.get("is_import_mode", False)
            
            if is_import_mode and context.get("repository_url"):
                # Import mode: Extract repo name from URL, don't create new repo
                repo_url = context["repository_url"].rstrip("/")
                parts = repo_url.split("/")
                repo_name = f"{parts[-2]}/{parts[-1]}".replace(".git", "")
                context["repository"] = repo_name
                self._log("INFO", f"Import mode: Using existing repository {repo_name}")
            elif "repository" not in context or not context.get("repository"):
                # New project mode: Create repository
                repository = await self._create_project_repository(task_id, task_description, project_id, context)
                context["repository"] = repository.full_name
                context["repository_url"] = repository.url
            
            # Phase 1: Architecture Planning (only if no plan exists for this project)
            project_has_architecture = await self._project_has_architecture_plan(project_id)
            if not project_has_architecture:
                await self.analyze_and_plan_architecture(task_id, task_description, project_id, context)
            else:
                self.architecture_plan = await self.get_architecture_plan(project_id)

            # Phase 2: Feature-level batched code generation
            feature_batch = await self.generate_feature_batch(task_id, task_description, task_requirements, project_id, context)
            
            # Create GitHub branch for feature
            feature_branch_name = await self.create_feature_branch(task_id, task_description, context)
            
            # Commit feature batch to branch
            commit = await self.commit_feature_batch(feature_batch, feature_branch_name, task_id, task_description, context)
            
            # Don't create PR yet - will be created after all developer tasks complete
            # Store branch info for later PR creation
            pr = None
            pr_url = None
            pr_number = None
            
            # Store feature batch in memory - convert FileChange objects to serializable format
            serializable_batch = []
            for file_change in feature_batch:
                serializable_batch.append({
                    "path": file_change.path,
                    "content": file_change.content,
                    "mode": file_change.mode
                })

            await self.store_memory(
                key=f"feature_batch_{task_id}",
                value=json.dumps(serializable_batch),
                memory_type="feature_batch",
                project_id=project_id,
                collection_type="code_artifacts"
            )

            # Update task batches tracking
            self.feature_batches.append({
                "task_id": task_id,
                "feature_name": task_description,
                "branch_name": feature_branch_name,
                "pr_url": pr_url,
                "commit_sha": commit.sha,
                "files": [file_change.path for file_change in feature_batch]
            })
            # Skip notification for now - will notify when PR is created after all tasks
            
            log_to_db(project_id, "INFO", f"Developer task {task_id} completed successfully", agent_role="developer")
            return TaskResult(
                success=True,
                data={
                    "feature_batch": serializable_batch,
                    "branch_name": feature_branch_name,
                    "pr_url": pr_url,
                    "pr_number": pr_number,
                    "commit_sha": commit.sha,
                    "files_generated": [file_change.path for file_change in feature_batch],
                    "repository": context.get("repository"),
                    "repository_url": context.get("repository_url")
                },
                metadata={
                    "task_id": task_id,
                    "agent_role": self.role,
                    "project_id": project_id,
                    "feature_branch": feature_branch_name,
                    "pr_url": pr_url
                }
            )

        except Exception as e:
            log_to_db(project_id, "ERROR", f"Developer task {task_id} failed: {str(e)}", agent_role="developer")
            return TaskResult(
                success=False,
                error=str(e),
                metadata={"task_id": task_id, "agent_role": self.role}
            )

    async def _create_project_repository(self, task_id: str, task_description: str, project_id: str, context: Dict[str, Any]):
        try:
            # Generate repository name from project
            project_name = context.get("project_name", project_id)
            # Sanitize name for GitHub (lowercase, hyphens, no spaces)
            repo_name = project_name.lower().replace(" ", "-").replace("_", "-")
            # Limit length
            repo_name = repo_name[:100]            
            # Check if token is available
            if not self.github_client.auth_token:
                raise BaseAgentError("GitHub token is missing. Please configure settings.github_token.")

            # Create repository
            repository = await self.github_client.create_repository(
                name=repo_name,
                description=context.get("project_description", task_description),
                private=True,
                auto_init=True  # Initialize with README so main branch exists
            )
            
            # Persist repository URL to database
            try:
                with get_db_context() as db:
                    project = db.query(Project).filter(Project.id == project_id).first()
                    if project:
                        project.repository_url = repository.url
                        db.commit()
                        self._log("INFO", f"Updated project {project_id} with repository URL: {repository.url}", LogType.GITHUB_REPO_CREATE)
            except Exception as db_error:
                self._log("WARNING", f"Failed to save repository URL to DB: {str(db_error)}")
                # Don't fail the task, just log the error
            
            return repository
            
        except Exception as e:
            # We don't want to fail the whole task if repo creation fails, 
            # but we should probably report it. 
            # For now, re-raise to ensure we know it failed.
            raise BaseAgentError(f"Repository creation failed: {str(e)}") from e
    
    async def _project_has_architecture_plan(self, project_id: str) -> bool:
        try:
            memories = await self.retrieve_memory(
                query=f"architecture plan for project {project_id}",
                limit=1,
                memory_type="architecture_plan",
                project_id=project_id,
                collection_type="code_artifacts"
            )
            return len(memories) > 0
        except Exception:
            return False

    async def analyze_and_plan_architecture(self, task_id: str, task_description: str, project_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Use external prompt templates
        system_prompt = self.build_system_prompt(
            additional_instructions=ARCHITECTURE_SYSTEM_PROMPT
        )

        # Build requirements from task + context
        requirements = task_description
        if "requirements" in context:
            requirements += f"\n\nAdditional requirements: {context['requirements']}"
        if "project_description" in context:
            requirements += f"\n\nProject description: {context['project_description']}"
        
        # Do research ONCE here (before architecture planning)
        research_context = ""
        try:
            # Detect language from requirements (simple keyword detection)
            requirements_lower = requirements.lower()
            if any(kw in requirements_lower for kw in ["javascript", "node", "react", "vue", "angular", "express", "npm"]):
                detected_language = "javascript"
            elif any(kw in requirements_lower for kw in ["typescript", "tsx"]):
                detected_language = "typescript"
            elif any(kw in requirements_lower for kw in ["go", "golang"]):
                detected_language = "go"
            elif any(kw in requirements_lower for kw in ["rust", "cargo"]):
                detected_language = "rust"
            elif any(kw in requirements_lower for kw in ["java", "spring", "maven", "gradle"]):
                detected_language = "java"
            elif any(kw in requirements_lower for kw in ["ruby", "rails"]):
                detected_language = "ruby"
            elif any(kw in requirements_lower for kw in ["c#", "csharp", ".net", "dotnet"]):
                detected_language = "csharp"
            else:
                detected_language = "python"  # Default fallback

            self._log("INFO", f"Detected language from requirements: {detected_language}")

            # Search for current tech stack recommendations
            project_name = context.get("project_name", "software project")
            research = await self.research_service.get_context_for_code_generation(
                language=detected_language,
                framework="",
                project_type=project_name,
                features=[task_description[:100]]
            )

            # Research service now returns PRE-SUMMARIZED content (no truncation needed!)
            package_info = research.get('package_info', 'latest stable')
            best_practices = research.get('best_practices', 'standard conventions')
            testing_setup = research.get('testing_setup', 'pytest')
            project_structure = research.get('project_structure', 'standard layout')

            # ALSO Research specific testing framework configuration requirements
            # This will help anticipate configuration issues that cause CI failures
            test_config_info = await self.research_service.search_best_practices(
                topic=f"configuration setup for {testing_setup} in {detected_language}",
                language=detected_language
            )
            test_config_summary = test_config_info if test_config_info else "standard configuration"

            # Compact single-line format for each piece of info
            research_context = f"""Tech: {detected_language} | Packages: {package_info}
Structure: {project_structure} | Patterns: {best_practices}
Testing: {testing_setup} | Config: {test_config_summary}"""

            self.research_context = research_context  # Cache for feature generation
            self._log("INFO", f"Research context: {len(research_context)} chars (summarized)")

            # Store research context in memory for future retrieval (in case of agent restart)
            if research_context:
                await self.store_memory(
                    key=f"research_context_{project_id}",
                    value=research_context,
                    memory_type="research_context",
                    project_id=project_id,
                    collection_type="code_artifacts"
                )

        except Exception as e:
            self._log("WARNING", f"Research unavailable, continuing without: {e}")
            self.research_context = ""
        
        # Include research in requirements for architecture planning
        if research_context:
            requirements += f"\n\n{research_context}"

        user_prompt = ARCHITECTURE_USER_PROMPT_TEMPLATE.format(requirements=requirements)

        # Invoke LLM with Pydantic model for structured output
        try:
            plan = await self.invoke_llm_structured(
                prompt=user_prompt,
                schema=ArchitecturePlan,  # Use Pydantic model
                system_prompt=system_prompt,
            )

            # Convert Pydantic model to dict if needed
            if hasattr(plan, 'model_dump'):
                plan = plan.model_dump()
            elif hasattr(plan, 'dict'):
                plan = plan.dict()

            self.architecture_plan = plan
            # Store in memory for future reference
            await self.store_memory(
                key=f"architecture_plan_{project_id}",
                value=json.dumps(plan),
                memory_type="architecture_plan",
                project_id=project_id,
                collection_type="code_artifacts"
            )

            return plan

        except Exception as e:
            raise BaseAgentError(f"Architecture planning failed: {str(e)}") from e

    # NOTE: _get_architecture_plan_schema() and _validate_architecture_plan() removed
    # Now using ArchitecturePlan Pydantic model for structured output + validation


    async def get_architecture_plan(self, project_id: str) -> Dict[str, Any]:
        """Retrieve architecture plan using exact-key lookup for reliability."""
        try:
            # Use exact-key retrieval instead of semantic search
            memory = await self.retrieve_memory_by_key(
                key=f"architecture_plan_{project_id}",
                project_id=project_id,
                collection_type="code_artifacts"
            )

            if memory:
                content = memory["content"]
                plan = json.loads(content)
                self.architecture_plan = plan
                self._log("DEBUG", f"Retrieved architecture plan via exact-key lookup")
                return plan
            
            raise BaseAgentError(f"No architecture plan found for project {project_id}")
        except json.JSONDecodeError as e:
            raise BaseAgentError(f"Failed to parse architecture plan JSON: {str(e)}") from e
        except Exception as e:
            raise BaseAgentError(f"Failed to retrieve architecture plan: {str(e)}") from e

    async def generate_feature_batch(self, task_id: str, task_description: str, task_requirements: str, project_id: str, context: Dict[str, Any]) -> List[FileChange]:
        # Set current project ID for memory operations
        self._current_project_id = project_id

        # Build system prompt WITHOUT architecture (it's in user prompt as compact summary)
        system_prompt = self.build_system_prompt(
            additional_instructions=FEATURE_GENERATION_SYSTEM_ADDENDUM
        )

        # Get context for code generation (uses compact summaries)
        generation_context = await self.get_generation_context(project_id, task_description)

        # Extract user feedback for refinement loop
        user_feedback_list = context.get("user_feedback", [])
        user_feedback_str = "\n".join(user_feedback_list) if user_feedback_list else "None"

        # Fetch RepoMap when in import mode (existing repo) or refinement mode (feedback present)
        current_codebase = "Not available - initial generation"
        is_import_mode = context.get("is_import_mode", False)

        # Determine if we're in refinement mode (feedback provided)
        is_refinement_mode = bool(user_feedback_list)

        # First, try to get RepoMap from memory (could be stored by PM agent during import mode)
        repo_map_from_memory = None
        if is_import_mode:
            try:
                repo_map_memory = await self.retrieve_memory_by_key(
                    key=f"repo_map_{project_id}",
                    project_id=project_id,
                    collection_type="code_artifacts"
                )
                if repo_map_memory and repo_map_memory.get("content"):
                    repo_map_from_memory = repo_map_memory["content"]
                    current_codebase = repo_map_from_memory
                    self._log("INFO", f"Retrieved RepoMap from memory (stored by PM agent) - {len(repo_map_from_memory)} chars")
            except Exception as e:
                self._log("DEBUG", f"Could not retrieve RepoMap from memory: {e}")

        # If no RepoMap found in memory, fetch it via RepoMapService
        if not repo_map_from_memory:
            if is_import_mode or is_refinement_mode:
                repository = context.get("repository")
                branch_name = context.get("branch_name") or self.current_branch or "main"

                if repository:
                    try:
                        from services.repomap.service import get_repomap_service
                        repomap_service = get_repomap_service(max_tokens=6000, verbose=False)
                        repo_map = await repomap_service.get_repo_map_via_api(
                            github_client=self.github_client,
                            repository=repository,
                            branch=branch_name,
                            max_files=50
                        )
                        if repo_map:
                            current_codebase = repo_map
                            mode = "import" if is_import_mode else "refinement"
                            self._log("INFO", f"Fetched RepoMap for {mode} ({len(repo_map)} chars)")
                    except Exception as e:
                        self._log("WARNING", f"Failed to fetch RepoMap: {e}")

        # Build user prompt for feature implementation
        user_prompt = FEATURE_GENERATION_USER_PROMPT_TEMPLATE.format(
            task_description=task_description,
            architecture_context=generation_context.get("architecture_context", ""),
            previous_context=generation_context.get("previous_context", ""),
            research_context=generation_context.get("research_context", ""),
            current_codebase=current_codebase,
            user_feedback=user_feedback_str,
            batch_size=self.batch_size
        )

        # Generate code batch based on architecture plan
        try:
            # Request structured response with both code and interface contracts
            response = await self.invoke_llm_structured(
                prompt=user_prompt,
                schema=FeatureGeneration,  # Use Pydantic model
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # Convert Pydantic model to dict if needed
            if hasattr(response, 'model_dump'):
                response = response.model_dump()
            elif hasattr(response, 'dict'):
                response = response.dict()

            # Validate response
            if response is None:
                raise BaseAgentError("LLM returned None for feature generation")

            # Extract files from response
            files_data = response.get("files") or []
            interface_contracts = response.get("interface_contracts") or []

            if not files_data:
                raise BaseAgentError("LLM response missing 'files' array")

            # If in refinement mode, selectively update files based on feedback
            if is_refinement_mode:
                file_changes = await self.selective_file_update(
                    files_data=files_data,
                    repository=context.get("repository"),
                    branch_name=context.get("branch_name") or self.current_branch or "main",
                    task_description=task_description,
                    user_feedback=user_feedback_str
                )
            else:
                # Normal mode - create all files as generated
                file_changes = []
                for file_data in files_data:
                    # Handle both dict and Pydantic model
                    if hasattr(file_data, 'model_dump'):
                        file_data = file_data.model_dump()
                    elif hasattr(file_data, 'dict'):
                        file_data = file_data.dict()

                    file_path = file_data.get("path")
                    content = file_data.get("content", "")

                    if len(content) > self.max_file_size:
                        raise BaseAgentError(f"Generated file {file_path} exceeds size limit of {self.max_file_size} bytes")

                    # Warn if code appears to be on a single line (formatting issue)
                    if len(content) > 100 and '\n' not in content:
                        self._log("WARNING", f"File {file_path} appears to be on a single line ({len(content)} chars, no newlines). This may be a formatting issue.")

                    file_change = FileChange(path=file_path, content=content)
                    file_changes.append(file_change)

            # Store interface contracts in memory for future feature generations
            # IMPORTANT: Only store contracts that reference files we actually generated
            contract_keys = []
            if interface_contracts:
                # Build set of valid file paths we actually created
                valid_file_paths = {f.path for f in file_changes}

                # Filter contracts to only those with valid file_path
                valid_contracts = []
                for contract in interface_contracts:
                    # Handle both dict and Pydantic model
                    if hasattr(contract, 'model_dump'):
                        contract = contract.model_dump()
                    elif hasattr(contract, 'dict'):
                        contract = contract.dict()

                    file_path = contract.get('file_path', '')
                    contract_name = contract.get('name', 'unknown')

                    if file_path in valid_file_paths:
                        valid_contracts.append(contract)
                    else:
                        self._log("WARNING", f"Skipping contract '{contract_name}' - file_path '{file_path}' not in generated files: {list(valid_file_paths)}")

                self._log("INFO", f"Validated contracts: {len(valid_contracts)}/{len(interface_contracts)} have valid file paths")

                # Store only valid contracts
                for contract in valid_contracts:
                    contract_key = f"interface_contract_{contract.get('name', 'unknown')}"
                    await self.store_memory(
                        key=contract_key,
                        value=json.dumps(contract),
                        memory_type="interface_contract",
                        project_id=project_id,
                        collection_type="code_artifacts"
                    )
                    contract_keys.append(contract_key)

                # Store manifest of all contract keys for validation by QA/Doc agents
                await self.store_memory(
                    key=f"contract_manifest_{project_id}",
                    value=json.dumps({
                        "contract_keys": contract_keys,
                        "count": len(contract_keys),
                        "task_id": task_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }),
                    memory_type="contract_manifest",
                    project_id=project_id,
                    collection_type="code_artifacts"
                )

                self._log("INFO", f"Stored {len(valid_contracts)} validated interface contracts + manifest")

            # Store feature batch metadata in memory
            # Note: Full code content is stored later in process_task after PR creation
            feature_batch_data = {
                "feature_description": task_description,
                "files_generated": [f.path for f in file_changes],
                "interface_contracts_count": len(interface_contracts),
                "timestamp": datetime.utcnow().isoformat()
            }

            await self.store_memory(
                key=f"feature_batch_metadata_{task_id}",
                value=json.dumps(feature_batch_data),
                memory_type="feature_batch_metadata",
                project_id=project_id,
                collection_type="code_artifacts"
            )

            # Validate batch consistency
            await self._validate_batch_consistency(file_changes, project_id)

            self._log("INFO", f"Generated {len(file_changes)} files with {len(interface_contracts)} interface contracts for feature: {task_description}")
            return file_changes

        except Exception as e:
            raise BaseAgentError(f"Feature generation failed: {str(e)}") from e

    async def selective_file_update(
        self,
        files_data: list,
        repository: str,
        branch_name: str,
        task_description: str,
        user_feedback: str
    ) -> List[FileChange]:
        """
        Selectively update files based on user feedback.
        Only update files that need changes based on feedback, leave others untouched.
        """
        self._log("INFO", f"Performing selective file update based on feedback: {user_feedback[:100]}...")

        file_changes = []

        # Get list of all files currently in the repository branch
        try:
            all_repo_files = await self.github_client.list_repository_files(
                repo=repository,
                ref=branch_name
            )
            self._log("INFO", f"Found {len(all_repo_files)} files in repository branch")
        except Exception as e:
            self._log("WARNING", f"Could not list repository files: {e}")
            all_repo_files = []

        # Determine which files need to be updated based on feedback
        files_to_update = await self.determine_files_to_update_with_memory(
            files_data=files_data,
            user_feedback=user_feedback,
            repository=repository,
            branch_name=branch_name,
            all_repo_files=all_repo_files
        )

        # Only process files that need updates based on feedback
        for file_data in files_data:
            # Handle both dict and Pydantic model
            if hasattr(file_data, 'model_dump'):
                file_data = file_data.model_dump()
            elif hasattr(file_data, 'dict'):
                file_data = file_data.dict()

            file_path = file_data.get("path")
            generated_content = file_data.get("content", "")

            if file_path in files_to_update:
                # This file needs to be updated based on feedback
                # Use the generated content (which incorporates feedback)
                self._log("INFO", f"Updating file based on feedback: {file_path}")

                if len(generated_content) > self.max_file_size:
                    raise BaseAgentError(f"File {file_path} exceeds size limit of {self.max_file_size} bytes")

                # Warn if code appears to be on a single line (formatting issue)
                if len(generated_content) > 100 and '\n' not in generated_content:
                    self._log("WARNING", f"File {file_path} appears to be on a single line ({len(generated_content)} chars, no newlines). This may be a formatting issue.")

                file_change = FileChange(path=file_path, content=generated_content)
                file_changes.append(file_change)

                # Update memory with the new file version
                await self.store_memory(
                    key=f"file_content_{file_path}_{self._current_project_id}",
                    value=generated_content,
                    memory_type="file_content",
                    project_id=self._current_project_id,
                    collection_type="code_artifacts"
                )

                # Send notification about file update during feedback refinement
                if self.notification_service:
                    try:
                        from services.notification import NotificationLevel
                        await self.notification_service.send_notification(
                            message=f"Code file updated based on feedback\n\n"
                                    f"**File:** {file_path}\n"
                                    f"**Size:** {len(generated_content)} characters\n"
                                    f"**Project:** {self._current_project_id}\n\n"
                                    f"File has been updated to address user feedback.",
                            level=NotificationLevel.INFO,
                            title="Code File Updated (Feedback)",
                            fields={
                                "File": file_path,
                                "Size": f"{len(generated_content)} chars",
                                "Project": str(self._current_project_id),
                                "Update Type": "Feedback Refinement"
                            }
                        )
                    except Exception as e:
                        self._log("WARNING", f"Failed to send file update notification: {e}")
            else:
                # This file doesn't need updating based on feedback, skip it
                self._log("INFO", f"Skipping file (no changes needed): {file_path}")

        return file_changes

    async def determine_files_to_update_with_memory(
        self,
        files_data: list,
        user_feedback: str,
        repository: str,
        branch_name: str,
        all_repo_files: list
    ) -> set:
        """
        Determine which files need to be updated based on user feedback using memory for context.
        """
        # Create a list of file paths from the generated files
        generated_files = [file_data.get("path") if isinstance(file_data, dict) else file_data.path
                          for file_data in files_data]

        # Get relevant file metadata from memory to provide context for feedback analysis
        file_context = ""
        try:
            # Search memory for file-related information to provide context
            file_related_memories = await self.retrieve_memory(
                query=user_feedback,
                limit=10,
                memory_type="file_content",
                project_id=self._current_project_id,
                collection_type="code_artifacts"
            )

            if file_related_memories:
                file_context = "\nRelevant file context from memory:\n"
                for memory in file_related_memories[:5]:  # Limit to top 5
                    file_path = memory.get("metadata", {}).get("key", "").split("_")[2] if memory.get("metadata", {}).get("key") else "unknown"
                    file_context += f"- File: {file_path}\n"
        except Exception as e:
            self._log("DEBUG", f"Could not retrieve file context from memory: {e}")

        # Build user prompt using external template with memory context
        user_prompt = FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            user_feedback=user_feedback,
            generated_files=generated_files
        ) + file_context

        system_prompt = self.build_system_prompt(
            additional_instructions=FEEDBACK_ANALYSIS_SYSTEM_PROMPT
        )

        try:
            result = await self.invoke_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1  # Low temperature for consistent analysis
            )

            # Try to parse as JSON
            import re
            json_match = re.search(r'\[(.*?)\]', result)
            if json_match:
                try:
                    files_to_update = json.loads(json_match.group(0))
                    if isinstance(files_to_update, list):
                        # Filter to only include files that actually exist in the current batch
                        valid_files = [f for f in files_to_update if f in generated_files]
                        return set(valid_files)
                except:
                    pass

            # If JSON parsing fails, try to extract file paths from plain text
            # Look for file paths mentioned in the response
            possible_files = []
            for file_path in generated_files:
                if file_path in result:
                    possible_files.append(file_path)

            return set(possible_files)

        except Exception as e:
            self._log("WARNING", f"Feedback analysis failed: {e}, updating all generated files")
            # If analysis fails, return all generated files to be safe
            return set(generated_files)




    async def get_generation_context(self, project_id: str, feature_description: str) -> Dict[str, str]:
        context = {
            "architecture_context": "",
            "previous_context": "",
            "research_context": ""
        }
        
        # Get research context using exact-key retrieval for reliability
        if self.research_context:
            context["research_context"] = self.research_context
        else:
            try:
                # Use exact-key retrieval instead of semantic search
                memory = await self.retrieve_memory_by_key(
                    key=f"research_context_{project_id}",
                    project_id=project_id,
                    collection_type="code_artifacts"
                )
                if memory and memory.get("content"):
                    self.research_context = memory.get("content")
                    context["research_context"] = self.research_context
                    self._log("DEBUG", f"Retrieved research context via exact-key lookup")
            except Exception:
                pass
        
        # Get architecture plan - COMPACT SUMMARY instead of full JSON
        try:
            plan = self.architecture_plan
            if not plan:
                plan = await self.get_architecture_plan(project_id)
            context["architecture_context"] = self._create_compact_architecture_summary(plan)
        except Exception:
            pass
        
        # Get interface contracts - use manifest for reliable retrieval
        try:
            # First try to get contract keys from manifest
            contract_keys = []
            try:
                manifest = await self.retrieve_memory_by_key(
                    key=f"contract_manifest_{project_id}",
                    project_id=project_id,
                    collection_type="code_artifacts"
                )
                if manifest and manifest.get("content"):
                    manifest_data = json.loads(manifest["content"])
                    contract_keys = manifest_data.get("contract_keys", [])
            except Exception:
                pass
            
            interface_contracts = []
            if contract_keys:
                # Use exact-key retrieval for each contract
                for contract_key in contract_keys:
                    try:
                        contract_memory = await self.retrieve_memory_by_key(
                            key=contract_key,
                            project_id=project_id,
                            collection_type="code_artifacts"
                        )
                        if contract_memory:
                            interface_contracts.append(contract_memory)
                    except Exception:
                        continue
            else:
                # Fallback to semantic search (no limit - retrieve all contracts)
                interface_contracts = await self.retrieve_memory(
                    query=f"interface contracts for {feature_description} in project {project_id}",
                    limit=100,  # High limit to get all contracts
                    memory_type="interface_contract",
                    project_id=project_id,
                    collection_type="code_artifacts"
                )
            
            interface_lines = []
            for memory in interface_contracts:
                content = memory.get("content", "")
                if content:
                    try:
                        c = json.loads(content)
                        # Include file_path for cross-task consistency
                        file_path = c.get('file_path', 'unknown')
                        
                        contract_str = f"### {c.get('name', 'Unknown')} (in {file_path})\n"
                        contract_str += f"  File: {file_path}\n"
                        contract_str += f"  Signature: {c.get('signature', 'N/A')}\n"
                        
                        inputs = c.get('inputs', [])
                        if inputs:
                            contract_str += f"  Inputs: {', '.join(inputs[:5])}\n"
                        
                        outputs = c.get('outputs', [])
                        if outputs:
                            contract_str += f"  Outputs: {', '.join(outputs[:3])}\n"
                        
                        purpose = c.get('purpose', '')
                        if purpose:
                            contract_str += f"  Purpose: {purpose[:150]}\n"
                        
                        deps = c.get('dependencies', [])
                        if deps:
                            contract_str += f"  Depends on: {', '.join(deps[:5])}\n"
                        
                        interface_lines.append(contract_str)
                    except json.JSONDecodeError:
                        pass
            
            if interface_lines:
                context["previous_context"] = f"Existing interfaces ({len(interface_lines)} found):\n\n" + "\n".join(interface_lines)
            else:
                context["previous_context"] = "No existing interfaces yet - this is the first feature."
        except Exception:
            context["previous_context"] = "No existing interfaces yet - this is the first feature."
        
        return context
    
    def _create_compact_architecture_summary(self, plan: Dict[str, Any]) -> str:
        """Create a detailed architecture summary for code generation context"""
        if not plan:
            return "No architecture defined"
        
        lines = []
        
        # Directory structure - full layout
        dirs = plan.get("directory_structure", [])
        if dirs:
            lines.append("## Directory Structure")
            for d in dirs[:15]:  # Allow more directories
                lines.append(f"  {d}")
        
        # Tech stack - complete info
        tech = plan.get("tech_stack", {})
        if tech:
            lines.append("\n## Tech Stack")
            frameworks = tech.get("frameworks", [])
            if frameworks:
                lines.append(f"  Frameworks: {', '.join(frameworks)}")
            libs = tech.get("libraries", [])
            if libs:
                lines.append(f"  Libraries: {', '.join(libs)}")
            dbs = tech.get("databases", [])
            if dbs:
                lines.append(f"  Databases: {', '.join(dbs)}")
            tools = tech.get("tools", [])
            if tools:
                lines.append(f"  Tools: {', '.join(tools)}")
        
        # Modules - detailed info including files and responsibilities
        modules = plan.get("modules", {})
        if modules:
            lines.append("\n## Modules")
            for name, info in list(modules.items())[:10]:
                if isinstance(info, dict):
                    desc = info.get("description", "")[:100]
                    files = info.get("files", [])
                    responsibilities = info.get("responsibilities", [])
                    
                    lines.append(f"  ### {name}")
                    if desc:
                        lines.append(f"    Description: {desc}")
                    if files:
                        lines.append(f"    Files: {', '.join(files[:5])}")
                    if responsibilities:
                        for r in responsibilities[:3]:
                            lines.append(f"    - {r[:80]}")
        
        # Data flow - entry points
        data_flow = plan.get("data_flow", {})
        if data_flow and isinstance(data_flow, dict):
            entry_points = data_flow.get("entry_points", [])
            if entry_points:
                lines.append("\n## Entry Points")
                for ep in entry_points[:5]:
                    lines.append(f"  - {ep}")
        
        # Coding standards - full details
        standards = plan.get("coding_standards", {})
        if standards and isinstance(standards, dict):
            lines.append("\n## Coding Standards")
            naming = standards.get("naming_conventions", "")
            if naming:
                lines.append(f"  Naming: {naming[:200]}")
            error = standards.get("error_handling", "")
            if error:
                lines.append(f"  Errors: {error[:150]}")
            org = standards.get("file_organization", "")
            if org:
                lines.append(f"  Organization: {org[:150]}")
        
        return "\n".join(lines) if lines else "Standard architecture"

    async def _validate_batch_consistency(self, file_changes: List[FileChange], project_id: str) -> None:
        """Validate generated files for basic consistency."""
        for file_change in file_changes:
            if not file_change.path or not file_change.path.strip():
                raise BaseAgentError("Generated file has empty path")
            if file_change.content is None:
                raise BaseAgentError(f"Generated file {file_change.path} has None content")
            if len(file_change.content) > self.max_file_size:
                raise BaseAgentError(
                    f"Generated file {file_change.path} exceeds size limit "
                    f"({len(file_change.content)} > {self.max_file_size} bytes)"
                )
        
        self._log("DEBUG", f"Batch consistency validation passed for {len(file_changes)} files")

    async def create_feature_branch(self, task_id: str, task_description: str, context: Dict[str, Any]) -> str:
        try:
            # Determine repository name from context
            repo_full_name = context.get("repository", context.get("repo", "owner/repo"))
            
            # Create branch name from PROJECT name (not task description)
            # This ensures all tasks use the same branch
            project_name = context.get("project_name", "autostack-project")
            safe_project_name = project_name.replace(" ", "-").replace("_", "-").lower()[:50]
            branch_name = f"{self.branch_prefix}{safe_project_name}"
            
            # Create branch from main/default branch
            from_branch = context.get("base_branch", "main")
            
            # Try to create branch - if it already exists, just use it
            try:
                branch = await self.github_client.create_branch(
                    repo=repo_full_name,
                    branch_name=branch_name,
                    from_branch=from_branch
                )
                
                self.current_branch = branch_name
                return branch_name
                
            except Exception as e:
                # Check if error is because branch already exists
                if "already exists" in str(e).lower() or "reference already exists" in str(e).lower():
                    self.current_branch = branch_name
                    return branch_name
                else:
                    # Some other error, re-raise
                    raise
            
        except Exception as e:
            raise BaseAgentError(f"Branch creation failed: {str(e)}") from e

    async def commit_feature_batch(self, feature_batch: List[FileChange], branch_name: str, task_id: str, task_description: str, context: Dict[str, Any]) -> Any:
        try:
            # Determine repository name from context
            repo_full_name = context.get("repository", context.get("repo", "owner/repo"))
            
            # Create commit message
            commit_message = f"[AutoStack] {task_description}"
            
            # Add files list to commit message
            file_list = ", ".join([fc.path for fc in feature_batch])
            commit_message += f"\n\nFiles: {file_list}"
            
            self._log("INFO", f"Committing {len(feature_batch)} files to branch {branch_name}", LogType.GITHUB_COMMIT)
            
            # Commit files to branch
            commit = await self.github_client.commit_files(
                repo=repo_full_name,
                branch=branch_name,
                files=feature_batch,
                message=commit_message
            )
            return commit
            
        except Exception as e:
            raise BaseAgentError(f"Commit failed: {str(e)}") from e

    async def create_feature_pr(self, task_id: str, task_description: str, project_id: str, branch_name: str, context: Dict[str, Any]) -> Any:
        try:
            # Determine repository name from context
            repo_full_name = context.get("repository", context.get("repo", "owner/repo"))
            
            # Create PR title
            pr_title = f"[AutoStack] {task_description[:60]}"  # GitHub PR title limit
            
            # Create PR body with details
            pr_body = FEATURE_PR_BODY_TEMPLATE.format(
                task_description=task_description,
                project_id=project_id,
                task_id=task_id
            )
            
            # Determine base branch
            base_branch = context.get("base_branch", "main")            
            # Create pull request
            pr = await self.github_client.create_pull_request(
                repo=repo_full_name,
                head=branch_name,
                base=base_branch,
                title=pr_title,
                body=pr_body
            )
            # Notify about PR creation if notification service is available
            if self.notification_service:
                try:
                    await self.notification_service.send_pull_request_created(
                        project_name=context.get("project_name", project_id),
                        pr_number=pr.number,
                        pr_url=pr.url,
                        pr_title=pr_title,
                        branch=branch_name
                    )
                except Exception as notification_error:
                    # Don't fail the main operation if notification fails
                    pass

            return pr
            
        except Exception as e:
            raise BaseAgentError(f"PR creation failed: {str(e)}") from e


# Register agent with factory
from agents.config import AgentFactory
AgentFactory.register_agent(AgentRole.DEVELOPER, DeveloperAgent)