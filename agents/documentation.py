"""
The Documentation agent retrieves code from developer PRs, analyzes the codebase,
generates comprehensive documentation (README, API docs, etc.), and commits
documentation back to the same PR.
"""

import json
from typing import Dict, Any, List, Optional

from agents.base import BaseAgent, TaskResult, BaseAgentError
from agents.config import AgentRole, DocumentationConfig
from agents.schemas.documentation import DocumentationOutput
from agents.prompts.documentation import (
    DOCUMENTATION_SYSTEM_PROMPT,
    DOCUMENTATION_USER_PROMPT_TEMPLATE,
)
from models.models import Task, TaskStatus
from models.database import get_db_context
from langchain_core.language_models import BaseChatModel
from services.github_client import GitHubClient, FileChange
from services.memory import AgentMemory
from services.notification import NotificationService
from utils.logging import log_to_db
from utils.code_analysis import detect_language, get_markdown_code_block_lang
from agents.templates.documentation_pr import (
    DOC_COMMENT_HEADER,
    DOC_COMMENT_SUMMARY_LINE,
    DOC_COMMENT_FILES_HEADER,
    DOC_COMMENT_README_PREVIEW_HEADER,
    DOC_COMMENT_FOOTER,
)
from utils.logging import log_to_db, LogType

import logging
logger = logging.getLogger(__name__)




class DocumentationAgent(BaseAgent):
    def __init__(
        self,
        llm: BaseChatModel,
        memory: AgentMemory,
        github_client: Optional[GitHubClient] = None,
        notification_service: Optional[NotificationService] = None,
        config: Optional[DocumentationConfig] = None,
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
            self.generate_readme = self.config.generate_readme
            self.generate_api_docs = self.config.generate_api_docs
            self.doc_format = self.config.doc_format
            self.include_examples = self.config.include_examples
        else:
            self.temperature = 0.7
            self.max_tokens = 4000
            self.generate_readme = True
            self.generate_api_docs = True
            self.doc_format = "markdown"
            self.include_examples = True

        # File size limit (shared with Developer agent)
        self.max_file_size = 100000  # 100KB

        # Instance state for tracking current operation
        self._current_project_id: Optional[str] = None  # Track current project for memory operations
    
    def get_role(self) -> str:
        return AgentRole.DOCUMENTATION.value
    
    async def process_task(self, task: Task, context: Dict[str, Any]) -> TaskResult:
        # Extract task data immediately to avoid detached instance errors
        task_id = task.id
        task_description = task.description
        task_requirements = task.requirements
        task_dependencies = task.dependencies
        project_id = task.project_id

        # Set current project ID for memory operations
        self._current_project_id = project_id

        log_to_db(project_id, "INFO", f"Processing documentation task {task_id}: {task_description}", agent_role="documentation")
        
        # Extract user feedback for refinement loop
        user_feedback_list = context.get("user_feedback", [])
        user_feedback_str = "\n".join(user_feedback_list) if user_feedback_list else "None"
        
        try:            
            # Step 1: Validate and get developer tasks from dependencies
            if not task_dependencies:
                raise BaseAgentError(
                    "Documentation task must have at least one developer task dependency"
                )
            
            # Step 2: Aggregate data from ALL dependencies (not just first)
            all_files_to_document = []
            branch_name = None
            dev_result = None  # Will use first valid result for fallback data
            branch_names_seen = set()
            
            for developer_task_id in task_dependencies:
                with get_db_context() as db:
                    developer_task = db.query(Task).filter_by(id=developer_task_id).first()
                    
                    if not developer_task:
                        self._log("WARNING", f"Developer task {developer_task_id} not found, skipping")
                        continue
                    
                    if developer_task.status != TaskStatus.COMPLETED:
                        self._log("WARNING", f"Developer task {developer_task_id} not completed (status: {developer_task.status}), skipping")
                        continue
                    
                    if not developer_task.result:
                        self._log("WARNING", f"Developer task {developer_task_id} has no result, skipping")
                        continue
                    
                    # Extract result while task is still attached to session
                    task_result = developer_task.result
                    
                    if "data" in task_result:
                        files = task_result["data"].get("files_generated", [])
                        all_files_to_document.extend(files)
                        
                        task_branch = task_result["data"].get("branch_name")
                        if task_branch:
                            branch_names_seen.add(task_branch)
                            if not branch_name:
                                branch_name = task_branch
                        
                        if not dev_result:
                            dev_result = task_result
            
            # Validate all dependencies are on the same branch
            if len(branch_names_seen) > 1:
                self._log("WARNING", f"Multiple branches found across dependencies: {branch_names_seen}. Using first: {branch_name}")
            
            if not dev_result:
                raise BaseAgentError("No valid developer task results found in dependencies")
            
            self._log("INFO", f"Aggregated {len(all_files_to_document)} files from {len(task_dependencies)} dependencies")
            
            # Step 3: Extract PR information from context/developer result
            repository = context.get("repository")
            if not repository:
                raise BaseAgentError("Repository not specified in context")
            
            # Get PR info from context (set by workflow after PR creation)
            pr_number = context.get("pr_number")
            pr_url = context.get("pr_url")
            branch_name = context.get("branch_name") or branch_name
            files_to_document = all_files_to_document
            
            if not branch_name:
                raise BaseAgentError("Branch name not found in context or developer results")
            
            self._log("INFO", f"Files to document: {len(files_to_document)} files on branch {branch_name}")
            
            # Step 4: Retrieve repo map from memory (generated by QA agent)
            # This avoids cloning the repo again - QA already did it
            code_files = {}
            
            try:
                # Try to get the repo map stored by QA agent
                repo_map_memory = await self.retrieve_memory_by_key(
                    key=f"repo_map_{project_id}",
                    project_id=project_id,
                    collection_type="code_artifacts"
                )
                
                if repo_map_memory and repo_map_memory.get("content"):
                    # Use the repo map from QA for documentation context
                    code_files["_code_structure.md"] = repo_map_memory["content"]
                    self._log("INFO", f"Using repo map from QA agent ({len(repo_map_memory['content'])} chars)")
                else:
                    # Fallback: fetch minimal files if no repo map found
                    self._log("WARNING", "No repo map found from QA, fetching minimal code files")
                    all_files = await self.github_client.list_repository_files(
                        repo=repository,
                        ref=branch_name
                    )
                    # Only fetch config files for context
                    config_files = [f for f in all_files if f in ['package.json', 'pyproject.toml', 'requirements.txt', 'README.md', 'go.mod', 'Cargo.toml']]
                    for file_path in config_files[:3]:  # Max 3 files
                        try:
                            content = await self.github_client.get_file_content(repo=repository, path=file_path, ref=branch_name)
                            code_files[file_path] = content
                        except:
                            continue
                    
                    if not code_files:
                        code_files["_project_info.txt"] = f"Project: {context.get('project_name', 'Unknown')}\nDescription: {context.get('project_description', task_description)}"
                        
            except Exception as e:
                self._log("WARNING", f"Failed to retrieve repo map: {e}")
                code_files["_project_info.txt"] = f"Project: {context.get('project_name', 'Unknown')}\nDescription: {context.get('project_description', task_description)}"
            
            # Step 5: Detect language and project type from code
            # Step 5: Detect language from code
            language = detect_language(code_files)
            project_type = "project"  # Generic type, LLM will determine specifics
            
            # Step 6: Get project context
            project_name = context.get("project_name", "Project")
            project_description = context.get("project_description", task_description)
            
            # Step 7: Generate documentation
            documentation = await self.generate_documentation(
                code_files=code_files,
                project_name=project_name,
                project_description=project_description,
                task_description=task_description,
                requirements=task_requirements or "",
                language=language,
                project_type=project_type,
                user_feedback=user_feedback_str
            )
            
            self._log(
                "INFO",
                f"Documentation generated: {len(documentation['files'])} files"
            )
            
            # Step 8: Post documentation summary as PR comment
            try:
                await self.post_documentation_comment(
                    repository=repository,
                    pr_number=pr_number,
                    documentation_data=documentation
                )
            except Exception as e:
                # Continue even if comment posting fails
                pass
            
            # Step 9: Commit documentation to PR branch (same PR)
            commit_sha = None

            if documentation["files"]:
                # Check if we're in refinement mode (feedback provided)
                user_feedback_list = context.get("user_feedback", [])
                is_refinement_mode = bool(user_feedback_list)

                if is_refinement_mode:
                    # In refinement mode, selectively update documentation files based on feedback
                    doc_files = await self.selective_doc_update(
                        doc_data=documentation["files"],
                        repository=repository,
                        branch_name=branch_name,
                        task_description=task_description,
                        user_feedback="\n".join(user_feedback_list)
                    )
                else:
                    # Normal mode - create all documentation files as generated
                    doc_files = [
                        FileChange(
                            path=doc["file_path"],
                            content=doc["content"]
                        )
                        for doc in documentation["files"]
                    ]

                commit = await self.github_client.commit_files(
                    repo=repository,
                    branch=branch_name,  # Same branch = same PR
                    files=doc_files,
                    message=f"[AutoStack Docs] Add documentation for {task_description}"
                )
                commit_sha = commit.sha
            else:
                commit_sha = None
            
            # Step 10: Return result
            # Send notification about documentation completion
            if hasattr(self, 'notification_service') and self.notification_service:
                try:
                    doc_files = [doc["file_path"] for doc in documentation["files"]]
                    
                    from services.notification import NotificationLevel
                    await self.notification_service.send_notification(
                        message=f"Documentation generated for PR #{pr_number}\n\n"
                                f"**Files Created:** {', '.join(doc_files)}\n"
                                f"**Language:** {language}\n\n"
                                f"{documentation.get('summary', '')}\n\n"
                                f"[View PR]({pr_url})",
                        level=NotificationLevel.SUCCESS,
                        title="Documentation Complete",
                        fields={
                            "Project": context.get("project_name", project_id),
                            "PR": f"#{pr_number}",
                            "Files": f"{len(doc_files)} docs",
                            "Language": language
                        }
                    )
                except Exception as e:
                    pass
            
            log_to_db(project_id, "INFO", f"Documentation task {task_id} completed successfully", agent_role="documentation")
            return TaskResult(
                success=True,
                data={
                    "pr_number": pr_number,
                    "pr_url": pr_url,
                    "branch_name": branch_name,
                    "commit_sha": commit_sha,
                    "documentation_files_generated": [
                        doc["file_path"] for doc in documentation["files"]
                    ],
                    "documentation_summary": documentation.get("summary", ""),
                    "developer_task_id": developer_task_id,
                    "files_documented": list(code_files.keys()),
                    "language": language,
                    "project_type": project_type
                },
                metadata={
                    "task_id": task_id,
                    "agent_role": self.role,
                    "project_id": project_id,
                    "developer_task_id": developer_task_id,
                    "pr_number": pr_number,
                    "pr_url": pr_url
                }
            )

        except Exception as e:
            log_to_db(project_id, "ERROR", f"Documentation task {task_id} failed: {str(e)}", agent_role="documentation")
            return TaskResult(
                success=False,
                error=str(e),
                metadata={
                    "task_id": task_id,
                    "agent_role": self.role,
                    "project_id": project_id
                }
            )

    async def selective_doc_update(
        self,
        doc_data: list,
        repository: str,
        branch_name: str,
        task_description: str,
        user_feedback: str
    ) -> List[FileChange]:
        """
        Selectively update documentation files based on user feedback.
        Only update documentation files that need changes based on feedback, leave others untouched.
        """
        self._log("INFO", f"Performing selective documentation update based on feedback: {user_feedback[:100]}...")

        file_changes = []

        # Determine which documentation files need to be updated based on feedback
        docs_to_update = await self.determine_docs_to_update(
            doc_data=doc_data,
            user_feedback=user_feedback,
            repository=repository,
            branch_name=branch_name
        )

        # Process each documentation file - only include files that need updates
        for doc_item in doc_data:
            # Handle both dict and Pydantic model
            if hasattr(doc_item, 'model_dump'):
                doc_item = doc_item.model_dump()
            elif hasattr(doc_item, 'dict'):
                doc_item = doc_item.dict()

            file_path = doc_item.get("file_path")
            generated_content = doc_item.get("content", "")

            if file_path in docs_to_update:
                # This documentation file needs to be updated based on feedback
                # Use the generated content (which incorporates feedback)
                self._log("INFO", f"Updating documentation file based on feedback: {file_path}")

                if len(generated_content) > self.max_file_size:
                    raise BaseAgentError(f"Documentation file {file_path} exceeds size limit of {self.max_file_size} bytes")

                file_change = FileChange(path=file_path, content=generated_content)
                file_changes.append(file_change)

                # Update memory with the new documentation file version
                await self.store_memory(
                    key=f"doc_file_content_{file_path}_{self._current_project_id}",
                    value=generated_content,
                    memory_type="doc_file_content",
                    project_id=self._current_project_id,
                    collection_type="code_artifacts"
                )

                # Send notification about documentation file update during feedback refinement
                if self.notification_service:
                    try:
                        from services.notification import NotificationLevel
                        await self.notification_service.send_notification(
                            message=f"Documentation file updated based on feedback\n\n"
                                    f"**File:** {file_path}\n"
                                    f"**Size:** {len(generated_content)} characters\n"
                                    f"**Project:** {self._current_project_id}\n\n"
                                    f"Documentation file has been updated to address user feedback.",
                            level=NotificationLevel.INFO,
                            title="Documentation Updated (Feedback)",
                            fields={
                                "File": file_path,
                                "Size": f"{len(generated_content)} chars",
                                "Project": str(self._current_project_id),
                                "Update Type": "Feedback Refinement"
                            }
                        )
                    except Exception as e:
                        self._log("WARNING", f"Failed to send documentation update notification: {e}")
            else:
                # This documentation file doesn't need updating based on feedback, skip it
                # The file already exists in the repository from previous runs
                self._log("INFO", f"Skipping documentation file (no changes needed): {file_path}")

        return file_changes

    async def determine_docs_to_update(
        self,
        doc_data: list,
        user_feedback: str,
        repository: str,
        branch_name: str
    ) -> set:
        """
        Determine which documentation files need to be updated based on user feedback.
        """
        # Create a list of documentation file paths from the generated docs
        doc_files = [doc_item.get("file_path") if isinstance(doc_item, dict) else doc_item.file_path
                     for doc_item in doc_data]

        # Get relevant documentation metadata from memory to provide context for feedback analysis
        doc_context = ""
        try:
            # Search memory for documentation-related information to provide context
            doc_related_memories = await self.retrieve_memory(
                query=user_feedback,
                limit=10,
                memory_type="doc_file_content",
                project_id=self._current_project_id,
                collection_type="code_artifacts"
            )

            if doc_related_memories:
                doc_context = "\nRelevant documentation context from memory:\n"
                for memory in doc_related_memories[:5]:  # Limit to top 5
                    file_path = memory.get("metadata", {}).get("key", "").split("_")[3] if memory.get("metadata", {}).get("key") else "unknown"
                    doc_context += f"- Doc File: {file_path}\n"
        except Exception as e:
            self._log("DEBUG", f"Could not retrieve documentation context from memory: {e}")

        # Build user prompt using external template with memory context
        from agents.prompts.documentation import DOC_FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE
        user_prompt = DOC_FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            user_feedback=user_feedback,
            doc_files=doc_files
        ) + doc_context

        system_prompt = self.build_system_prompt(
            additional_instructions="Analyze user feedback to determine which documentation files need updating."
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
                    docs_to_update = json.loads(json_match.group(0))
                    if isinstance(docs_to_update, list):
                        # Filter to only include documentation files that actually exist in the current batch
                        valid_docs = [f for f in docs_to_update if f in doc_files]
                        return set(valid_docs)
                except:
                    pass

            # If JSON parsing fails, try to extract file paths from plain text
            # Look for file paths mentioned in the response
            possible_docs = []
            for file_path in doc_files:
                if file_path in result:
                    possible_docs.append(file_path)

            return set(possible_docs)

        except Exception as e:
            self._log("WARNING", f"Documentation feedback analysis failed: {e}, updating all documentation files")
            # If analysis fails, return all documentation files to be safe
            return set(doc_files)
    
    async def generate_documentation(
        self,
        code_files: Dict[str, str],
        project_name: str,
        project_description: str,
        task_description: str,
        requirements: str,
        language: str = "Python",
        project_type: str = "library",
        user_feedback: str = "None"
    ) -> Dict[str, Any]:
        # Determine code block language for markdown
        code_block_lang = get_markdown_code_block_lang(language)
        
        # Format code files for prompt with explicit file paths
        code_text = "\n\n".join([
            f"File Path: {path}\n```{code_block_lang}\n{content}\n```"
            for path, content in code_files.items()
        ])
        
        # Extract file paths for reference
        file_paths_list = "\n".join([f"  - {path}" for path in code_files.keys()])
        
        # Build system prompt using external template
        system_prompt = self.build_system_prompt(
            additional_instructions=DOCUMENTATION_SYSTEM_PROMPT.format(
                language=language
            )
        )
        
        # Build user prompt using external template
        user_prompt = DOCUMENTATION_USER_PROMPT_TEMPLATE.format(
            project_name=project_name,
            project_description=project_description,
            language=language,
            task_description=task_description,
            user_feedback=user_feedback,
            file_paths=file_paths_list,
            code_text=code_text
        )
        
        # Invoke LLM with Pydantic schema for structured output
        try:
            result = await self.invoke_llm_structured(
                prompt=user_prompt,
                schema=DocumentationOutput,  # Use Pydantic model class
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Convert Pydantic model to dict if needed
            if result is None:
                raise BaseAgentError("LLM returned None for documentation")
            
            if hasattr(result, 'model_dump'):
                result = result.model_dump()
            elif hasattr(result, 'dict'):
                result = result.dict()
            
            # Validate result
            files_list = result.get("files") if isinstance(result, dict) else None
            if files_list is None or not isinstance(files_list, list):
                raise BaseAgentError(
                    f"LLM response missing required 'files' field: {type(result)}"
                )
            
            return result
            
        except Exception as e:
            raise BaseAgentError(f"Documentation generation failed: {str(e)}") from e
    
    async def post_documentation_comment(
        self,
        repository: str,
        pr_number: int,
        documentation_data: Dict[str, Any]
    ) -> None:
        # Build comprehensive documentation comment
        comment_parts = [
            DOC_COMMENT_HEADER,
            DOC_COMMENT_SUMMARY_LINE.format(summary=documentation_data.get('summary', 'Documentation generated'))
        ]
        
        # Add list of generated files
        if documentation_data.get("files"):
            comment_parts.append(DOC_COMMENT_FILES_HEADER)
            for doc_file in documentation_data["files"]:
                file_path = doc_file["file_path"]
                description = doc_file.get("description", "Documentation file")
                comment_parts.append(f"- **{file_path}**: {description}")
        
        # Add preview of README if it exists
        readme_file = next(
            (f for f in documentation_data.get("files", []) 
             if "README" in f["file_path"].upper()),
            None
        )
        
        if readme_file:
            # Get first 500 characters of README as preview
            readme_preview = readme_file["content"][:500]
            if len(readme_file["content"]) > 500:
                readme_preview += "..."
            
            comment_parts.append(DOC_COMMENT_README_PREVIEW_HEADER)
            comment_parts.append("```markdown")
            comment_parts.append(readme_preview)
            comment_parts.append("```")
        
        # Add footer
        comment_parts.append(DOC_COMMENT_FOOTER)
        
        comment = "\n".join(comment_parts)
        
        # Post comment to PR
        try:
            await self.github_client.add_pr_comment(
                repo=repository,
                pr_number=pr_number,
                comment=comment
            )            
        except Exception as e:
            raise BaseAgentError(f"Failed to post documentation comment: {str(e)}") from e

# Register agent with factory
from agents.config import AgentFactory
AgentFactory.register_agent(AgentRole.DOCUMENTATION, DocumentationAgent)
