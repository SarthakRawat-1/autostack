"""QA Agent - Code review and test generation."""

import json
from typing import Dict, Any, List, Optional

from agents.base import BaseAgent, TaskResult, BaseAgentError
from agents.config import AgentRole, QAConfig
from agents.prompts.qa import (
    QA_REVIEW_SYSTEM_PROMPT, 
    QA_REVIEW_USER_PROMPT_TEMPLATE,
)
from agents.schemas.qa import ReviewAndTestsOutput
from agents.templates.ci import get_workflow_content
from agents.templates.qa_pr import (
    TEST_RESULTS_TIMED_OUT_TEMPLATE,
    TEST_RESULTS_SUCCESS_TEMPLATE,
    TEST_RESULTS_FAILURE_HEADER_TEMPLATE,
    TEST_RESULTS_FAILURE_FOOTER_TEMPLATE,
    TEST_RESULTS_UNKNOWN_TEMPLATE,
    TEST_RESULTS_FOOTER,
    QA_REVIEW_HEADER,
    QA_REVIEW_QUALITY_LINE,
    QA_REVIEW_SECURITY_HEADER,
    QA_REVIEW_CODE_SMELLS_HEADER,
    QA_REVIEW_PERFORMANCE_HEADER,
    QA_REVIEW_SUGGESTIONS_HEADER,
    QA_REVIEW_FEEDBACK_HEADER,
    QA_REVIEW_FOOTER,
)
from models.models import Task, TaskStatus
from models.database import get_db_context
from langchain_core.language_models import BaseChatModel
from services.github_client import GitHubClient, FileChange
from services.memory import AgentMemory
from services.notification import NotificationService
from services.research import TavilyResearchService, get_research_service
from services.repomap.service import get_repomap_service, RepoMapService
from utils.logging import log_to_db, LogType
from utils.code_analysis import detect_language, get_markdown_code_block_lang, detect_language_and_framework, extract_project_versions, extract_project_versions

import logging
logger = logging.getLogger(__name__)




class QAAgent(BaseAgent):
    
    def __init__(
        self,
        llm: BaseChatModel,
        memory: AgentMemory,
        github_client: Optional[GitHubClient] = None,
        notification_service: Optional[NotificationService] = None,
        config: Optional[QAConfig] = None,
        **kwargs
    ):
        super().__init__(llm, memory, config, **kwargs)
        
        # Client dependencies
        self.github_client = github_client
        
        # Use config values if provided
        if self.config:
            self.temperature = self.config.llm_temperature
            self.max_tokens = self.config.llm_max_tokens
            self.test_framework = self.config.test_framework
            self.generate_tests = self.config.generate_tests
            self.execute_tests = self.config.execute_tests
        else:
            self.temperature = 0.7
            self.max_tokens = 4000
            self.test_framework = "auto"  # Auto-detect from code
            self.generate_tests = True
            self.execute_tests = False  # Tests run via GitHub Actions
        
        # File size limit (shared with Developer agent)
        self.max_file_size = 100000  # 100KB
        
        # Research service for up-to-date testing best practices
        self.research_service: TavilyResearchService = get_research_service()
    
    def get_role(self) -> str:
        return AgentRole.QA.value
    
    async def process_task(self, task: Task, context: Dict[str, Any]) -> TaskResult:
        """
        Process QA task: Review code and generate tests
        
        Workflow:
        1. Get developer task from dependencies
        2. Extract PR information from developer task result
        3. Retrieve code from GitHub PR
        4. Single LLM call for code review + test generation
        5. Post review feedback as PR comment
        6. Commit tests to same PR branch
        7. Return result with test and review information
        
        Args:
            task: QA task to process from PM agent
            context: Project context including repository info
            
        Returns:
            TaskResult with review and test information
            
        Raises:
            BaseAgentError: If QA processing fails
        """
        # Extract task data immediately to avoid detached instance errors
        task_id = task.id
        task_description = task.description
        task_requirements = task.requirements
        task_dependencies = task.dependencies
        project_id = task.project_id
        
        # Set project context for memory operations in refinement mode
        self._current_project_id = project_id
        
        log_to_db(project_id, "INFO", f"Processing QA task {task_id}: {task_description}", agent_role="qa")
        
        # Extract user feedback for refinement loop
        user_feedback_list = context.get("user_feedback", [])
        user_feedback_str = "\n".join(user_feedback_list) if user_feedback_list else "None"
        
        # Fetch previous test logs if in refinement mode
        previous_test_logs = "None"
        if user_feedback_list:
            repository = context.get("repository")
            branch_name = context.get("branch_name")
            if repository and branch_name:
                try:
                    logs = await self.github_client.get_workflow_run_logs(repository, branch_name)
                    if logs and logs != "No failure logs found":
                        previous_test_logs = logs
                        self._log("INFO", f"Fetched test failure logs for refinement")
                except Exception as e:
                    self._log("DEBUG", f"Could not fetch test logs: {e}")
        
        try:            
            # Step 1: Validate and get developer tasks from dependencies
            if not task_dependencies:
                raise BaseAgentError(
                    "QA task must have at least one developer task dependency"
                )
            
            # Step 2: Aggregate data from ALL dependencies (not just first)
            all_files_to_test = []
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
                        all_files_to_test.extend(files)
                        
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
            
            self._log("INFO", f"Aggregated {len(all_files_to_test)} files from {len(task_dependencies)} dependencies")
            
            # Step 3: Extract PR information from context/developer result
            repository = context.get("repository")
            if not repository:
                raise BaseAgentError("Repository not specified in context")
            
            # Get PR info from context (set by workflow after PR creation)
            pr_number = context.get("pr_number")
            pr_url = context.get("pr_url")
            branch_name = context.get("branch_name") or branch_name
            files_to_test = all_files_to_test
            
            if not branch_name:
                raise BaseAgentError("Branch name not found in context or developer results")
            
            self._log("INFO", f"Files to test: {len(files_to_test)} files on branch {branch_name}")
            
            # Step 4: Use RepoMapService to analyze ACTUAL code from the GitHub branch
            # Uses GitHub API (authenticated) instead of git clone for private repos
            code_context = ""
            code_files = {}
            all_files = []
            
            try:
                # Get repo map via authenticated GitHub API (works with private repos)
                repomap_service = get_repomap_service(max_tokens=6000, verbose=False)
                repo_map = await repomap_service.get_repo_map_via_api(
                    github_client=self.github_client,
                    repository=repository,
                    branch=branch_name,
                    priority_files=files_to_test,  # Prioritize files we need to test
                    max_files=100
                )
                
                if repo_map:
                    code_context = repo_map
                    self._log("INFO", f"Generated repo map with {len(repo_map)} chars from branch {branch_name}")
                    
                    # Store repo map in memory for Documentation agent to reuse
                    # This avoids cloning the repo twice
                    await self.store_memory(
                        key=f"repo_map_{project_id}",
                        value=repo_map,
                        memory_type="repo_map",
                        project_id=project_id,
                        collection_type="code_artifacts"
                    )
                    self._log("DEBUG", f"Stored repo map in memory for documentation agent")
                else:
                    self._log("WARNING", "RepoMapService returned empty map")
                
                # List files for config detection
                all_files = await self.github_client.list_repository_files(
                    repo=repository,
                    ref=branch_name
                )
                
                # Add source file paths to context
                if files_to_test:
                    paths_list = "\n".join([f"  - {fp}" for fp in files_to_test])
                    code_files["_source_files.txt"] = f"Source files generated (use these paths for imports):\n{paths_list}"
                    self._log("INFO", f"Added {len(files_to_test)} source file paths for test import generation")
                
                # Fetch config files for language/framework detection
                config_files = [f for f in all_files if f in [
                    'package.json', 'pyproject.toml', 'requirements.txt', 'setup.py', 
                    'go.mod', 'Cargo.toml', 'pom.xml', 'build.gradle', 'Gemfile', 'composer.json'
                ]]
                
                for file_path in config_files[:1]:  # Max 1 config file
                    try:
                        content = await self.github_client.get_file_content(repo=repository, path=file_path, ref=branch_name)
                        code_files[file_path] = content
                    except:
                        continue
                
                # If no repo map, fetch minimal code as fallback
                if not code_context:
                    self._log("WARNING", "No repo map available, fetching minimal code files")
                    code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.cs', '.cpp', '.c', '.h'}
                    code_file_paths = [
                        f for f in all_files 
                        if any(f.endswith(ext) for ext in code_extensions)
                        and not any(excl in f for excl in ['.git', 'node_modules'])
                    ]
                    for file_path in code_file_paths[:3]:
                        try:
                            content = await self.github_client.get_file_content(repo=repository, path=file_path, ref=branch_name)
                            code_files[file_path] = content
                        except:
                            continue
                
                if not code_files and not code_context:
                    code_files["_placeholder.txt"] = f"Project: {context.get('project_name', 'Unknown')}\nTask: {task_description}"
                        
            except Exception as e:
                self._log("WARNING", f"RepoMapService failed: {e}, falling back to file list")
                # Fallback: just list files
                try:
                    all_files = await self.github_client.list_repository_files(
                        repo=repository,
                        ref=branch_name
                    )
                    if files_to_test:
                        paths_list = "\n".join([f"  - {fp}" for fp in files_to_test])
                        code_files["_source_files.txt"] = f"Source files to test:\n{paths_list}"
                except Exception as fallback_error:
                    self._log("ERROR", f"Fallback also failed: {fallback_error}")
                    code_files["_placeholder.txt"] = f"Project: {context.get('project_name', 'Unknown')}\nTask: {task_description}"
            
            # Step 5: Detect language and test framework
            # First try to get from architecture plan (set by Developer agent)
            language = None
            test_framework = None
            architecture_context = ""
            arch_plan = None
            
            try:
                arch_memory = await self.retrieve_memory_by_key(
                    key=f"architecture_plan_{project_id}",
                    project_id=project_id,
                    collection_type="code_artifacts"
                )
                if arch_memory and arch_memory.get("content"):
                    import json as json_module
                    arch_plan = json_module.loads(arch_memory["content"])
                    
                    # Extract language from tech_stack frameworks
                    tech_stack = arch_plan.get("tech_stack", {})
                    frameworks = tech_stack.get("frameworks", [])
                    
                    # Map common frameworks to language
                    framework_to_lang = {
                        "fastapi": "Python", "flask": "Python", "django": "Python",
                        "express": "JavaScript", "react": "JavaScript", "next.js": "JavaScript",
                        "nestjs": "TypeScript", "angular": "TypeScript",
                        "spring": "Java", "gin": "Go", "fiber": "Go",
                        "rails": "Ruby", "laravel": "PHP", "asp.net": "C#"
                    }
                    
                    for fw in frameworks:
                        fw_lower = fw.lower()
                        for key, lang in framework_to_lang.items():
                            if key in fw_lower:
                                language = lang
                                break
                        if language:
                            break
                    
                    # Extract test framework from testing_strategy
                    testing = arch_plan.get("testing_strategy", {})
                    testing_tools = testing.get("testing_tools", [])
                    
                    # Map testing tools to framework names
                    tool_mapping = {
                        "pytest": "pytest", "unittest": "unittest",
                        "jest": "jest", "mocha": "mocha", "vitest": "vitest",
                        "junit": "JUnit", "go test": "go test",
                        "rspec": "RSpec", "phpunit": "PHPUnit", "nunit": "NUnit"
                    }
                    
                    for tool in testing_tools:
                        tool_lower = tool.lower()
                        for key, fw in tool_mapping.items():
                            if key in tool_lower:
                                test_framework = fw
                                break
                        if test_framework:
                            break
                    
                    # Build architecture context string
                    if testing:
                        test_types = testing.get("unit_test_types", [])
                        tools = testing.get("testing_tools", [])
                        architecture_context = f"Testing Strategy:\n  Types: {', '.join(test_types) if test_types else 'standard'}\n  Tools: {', '.join(tools) if tools else 'standard'}"
                    
                    standards = arch_plan.get("coding_standards", {})
                    if standards:
                        naming = standards.get("naming_conventions", "")
                        if naming:
                            architecture_context += f"\n  Naming: {naming[:100]}"
                    
                    if language:
                        self._log("INFO", f"Detected language from architecture: {language}")
                    if test_framework:
                        self._log("INFO", f"Detected test framework from architecture: {test_framework}")
                        
            except Exception as e:
                self._log("DEBUG", f"Could not load architecture plan: {e}")
            
            # Fallback: detect from file extensions if architecture didn't provide
            if not language or not test_framework:
                detected_lang, detected_fw = self._detect_language_and_framework(code_files)
                if not language:
                    language = detected_lang
                if not test_framework:
                    test_framework = detected_fw
                self._log("INFO", f"Using fallback detection: {language}/{test_framework}")
            
            # Step 6: Single LLM call for code review + test generation
            # Pass the repo map as code context for accurate test generation
            interface_details_text = code_context if code_context else "No code structure available - generate tests based on file paths."
            
            review_and_tests = await self.review_and_generate_tests(
                code_files=code_files,
                task_description=task_description,
                requirements=task_requirements or "",
                language=language,
                test_framework=test_framework,
                architecture_context=architecture_context,
                interface_details=interface_details_text,
                user_feedback=user_feedback_str,
                previous_test_logs=previous_test_logs
            )
            
            # Check for formatting issues in generated tests
            for test in review_and_tests.get("tests", []):
                content = test.get("content", "")
                file_path = test.get("file_path", "unknown")
                if len(content) > 100 and '\n' not in content:
                    self._log("WARNING", f"Test file {file_path} appears to be on a single line ({len(content)} chars). May be a formatting issue.")
            
            self._log(
                "INFO",
                f"Generated {len(review_and_tests['tests'])} test files"
            )
            
            # Step 7: Post review feedback as PR comment
            if pr_number:
                try:
                    await self.post_review_comment(
                        repository=repository,
                        pr_number=pr_number,
                        review_data=review_and_tests["review"]
                    )
                except Exception as e:
                    # Continue even if comment posting fails
                    pass
            else:
                pass
            # Step 8: Commit tests to PR branch (GitHub Actions will run them)
            commit_sha = None
            github_actions_status = None
            
            if self.generate_tests and review_and_tests["tests"]:
                # Check if we're in refinement mode (feedback provided)
                user_feedback_list = context.get("user_feedback", [])
                is_refinement_mode = bool(user_feedback_list)

                if is_refinement_mode:
                    # In refinement mode, selectively update test files based on feedback
                    test_files = await self.selective_test_update(
                        test_data=review_and_tests["tests"],
                        repository=repository,
                        branch_name=branch_name,
                        task_description=task_description,
                        user_feedback="\n".join(user_feedback_list)
                    )
                else:
                    # Normal mode - create all test files as generated
                    test_files = [
                        FileChange(
                            path=test["file_path"],
                            content=test["content"]
                        )
                        for test in review_and_tests["tests"]
                    ]

                # Step 8a: Check if GitHub Actions workflow exists, create if not
                workflow_exists = await self._check_workflow_exists(repository, branch_name)

                if not workflow_exists:
                    # Determine files list for context (use all_files to detect config files like package.json)
                    file_list = all_files if 'all_files' in locals() else []
                    workflow_file = await self._generate_workflow_file(language, test_framework, code_files)
                    test_files.append(workflow_file)
                else:
                    pass
                # Step 8b: Commit tests (and workflow if needed) to PR branch
                commit = await self.github_client.commit_files(
                    repo=repository,
                    branch=branch_name,  # Same branch = same PR
                    files=test_files,
                    message=f"[AutoStack QA] Add tests for {task_description}"
                )
                commit_sha = commit.sha
                
                # Step 8c: Wait for and check GitHub Actions status (if enabled)
                if self.execute_tests:
                    try:
                        github_actions_status = await self.github_client.wait_for_checks(
                            repo=repository,
                            ref=commit_sha,
                            timeout=300  # 5 minutes
                        )
                        
                        if github_actions_status.get("conclusion") == "success":
                            pass
                        elif github_actions_status.get("conclusion") == "failure":
                            pass
                        else:
                            self._log(
                                "WARNING",
                                f"⚠️  GitHub Actions: {github_actions_status.get('conclusion', 'unknown')}"
                            )
                        
                        # Step 8d: Post test results as PR comment
                        try:
                            await self._post_test_results_comment(
                                repository=repository,
                                pr_number=pr_number,
                                github_actions_status=github_actions_status,
                                language=language,
                                test_framework=test_framework
                            )
                        except Exception as e:
                            pass
                    except Exception as e:
                        github_actions_status = {"error": str(e)}
                else:
                    pass
            else:
                commit_sha = None
                github_actions_status = None
            
            # Step 9: Return result
            # Send notification about QA completion
            if hasattr(self, 'notification_service') and self.notification_service:
                try:
                    tests_status = "passed" if github_actions_status and github_actions_status.get("conclusion") == "success" else "pending"
                    review_quality = review_and_tests["review"].get("overall_quality", "unknown")

                    from services.notification import NotificationLevel
                    await self.notification_service.send_notification(
                        message=f"QA review completed for PR #{pr_number}\n\n"
                                f"**Code Quality:** {review_quality}\n"
                                f"**Tests Generated:** {len(review_and_tests['tests'])} files\n"
                                f"**Tests Status:** {tests_status}\n\n"
                                f"[View PR]({pr_url})",
                        level=NotificationLevel.SUCCESS,
                        title="QA Review Complete",
                        fields={
                            "Project": context.get("project_name", project_id),
                            "PR": f"#{pr_number}",
                            "Quality": review_quality,
                            "Tests": f"{len(review_and_tests['tests'])} files"
                        }
                    )
                except Exception as e:
                    pass

            return TaskResult(
                success=True,
                data={
                    "review": review_and_tests.get("review"),
                    "tests": review_and_tests.get("tests"),
                    "github_actions_status": github_actions_status,
                    "pr_url": pr_url,
                    "commit_sha": commit_sha
                },
                metadata={
                    "task_id": task_id,
                    "agent_role": self.role,
                    "project_id": project_id,
                    "pr_number": pr_number
                }
            )

        except Exception as e:
            log_to_db(project_id, "ERROR", f"QA task {task_id} failed: {str(e)}", agent_role="qa")
            return TaskResult(
                success=False,
                error=str(e),
                metadata={"task_id": task_id, "agent_role": self.role}
            )

    async def selective_test_update(
        self,
        test_data: list,
        repository: str,
        branch_name: str,
        task_description: str,
        user_feedback: str
    ) -> List[FileChange]:
        """
        Selectively update test files based on user feedback.
        Only update test files that need changes based on feedback, leave others untouched.
        """
        self._log("INFO", f"Performing selective test update based on feedback: {user_feedback[:100]}...")

        file_changes = []

        # Determine which test files need to be updated based on feedback
        tests_to_update = await self.determine_tests_to_update(
            test_data=test_data,
            user_feedback=user_feedback,
            repository=repository,
            branch_name=branch_name
        )

        # Process each test file
        for test_item in test_data:
            # Handle both dict and Pydantic model
            if hasattr(test_item, 'model_dump'):
                test_item = test_item.model_dump()
            elif hasattr(test_item, 'dict'):
                test_item = test_item.dict()

            file_path = test_item.get("file_path")
            generated_content = test_item.get("content", "")

            if file_path in tests_to_update:
                # This test file needs to be updated based on feedback
                # Use the generated content (which incorporates feedback)
                self._log("INFO", f"Updating test file based on feedback: {file_path}")

                if len(generated_content) > self.max_file_size:
                    raise BaseAgentError(f"Test file {file_path} exceeds size limit of {self.max_file_size} bytes")

                # Warn if code appears to be on a single line (formatting issue)
                if len(generated_content) > 100 and '\n' not in generated_content:
                    self._log("WARNING", f"Test file {file_path} appears to be on a single line ({len(generated_content)} chars, no newlines). This may be a formatting issue.")

                file_change = FileChange(path=file_path, content=generated_content)
                file_changes.append(file_change)

                # Update memory with the new test file version
                await self.store_memory(
                    key=f"test_file_content_{file_path}_{self._current_project_id}",
                    value=generated_content,
                    memory_type="test_file_content",
                    project_id=self._current_project_id,
                    collection_type="code_artifacts"
                )

                # Send notification about test file update during feedback refinement
                if self.notification_service:
                    try:
                        from services.notification import NotificationLevel
                        await self.notification_service.send_notification(
                            message=f"Test file updated based on feedback\n\n"
                                    f"**File:** {file_path}\n"
                                    f"**Size:** {len(generated_content)} characters\n"
                                    f"**Project:** {self._current_project_id}\n\n"
                                    f"Test file has been updated to address user feedback.",
                            level=NotificationLevel.INFO,
                            title="Test File Updated (Feedback)",
                            fields={
                                "File": file_path,
                                "Size": f"{len(generated_content)} chars",
                                "Project": str(self._current_project_id),
                                "Update Type": "Feedback Refinement"
                            }
                        )
                    except Exception as e:
                        self._log("WARNING", f"Failed to send test file update notification: {e}")
            else:
                # This test file doesn't need updating based on feedback, skip it
                self._log("INFO", f"Skipping test file (no changes needed): {file_path}")

        return file_changes

    async def determine_tests_to_update(
        self,
        test_data: list,
        user_feedback: str,
        repository: str,
        branch_name: str
    ) -> set:
        """
        Determine which test files need to be updated based on user feedback.
        """
        # Create a list of test file paths from the generated tests
        test_files = [test_item.get("file_path") if isinstance(test_item, dict) else test_item.file_path
                     for test_item in test_data]

        # Get relevant test metadata from memory to provide context for feedback analysis
        test_context = ""
        try:
            # Search memory for test-related information to provide context
            test_related_memories = await self.retrieve_memory(
                query=user_feedback,
                limit=10,
                memory_type="test_file_content",
                project_id=self._current_project_id,
                collection_type="code_artifacts"
            )

            if test_related_memories:
                test_context = "\nRelevant test context from memory:\n"
                for memory in test_related_memories[:5]:  # Limit to top 5
                    file_path = memory.get("metadata", {}).get("key", "").split("_")[3] if memory.get("metadata", {}).get("key") else "unknown"
                    test_context += f"- Test File: {file_path}\n"
        except Exception as e:
            self._log("DEBUG", f"Could not retrieve test context from memory: {e}")

        # Build user prompt using external template with memory context
        from agents.prompts.qa import QA_FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE
        user_prompt = QA_FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            user_feedback=user_feedback,
            test_files=test_files
        ) + test_context

        system_prompt = self.build_system_prompt(
            additional_instructions="Analyze user feedback to determine which test files need updating."
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
                    tests_to_update = json.loads(json_match.group(0))
                    if isinstance(tests_to_update, list):
                        # Filter to only include test files that actually exist in the current batch
                        valid_tests = [f for f in tests_to_update if f in test_files]
                        return set(valid_tests)
                except:
                    pass

            # If JSON parsing fails, try to extract file paths from plain text
            # Look for file paths mentioned in the response
            possible_tests = []
            for file_path in test_files:
                if file_path in result:
                    possible_tests.append(file_path)

            return set(possible_tests)

        except Exception as e:
            self._log("WARNING", f"Test feedback analysis failed: {e}, updating all test files")
            # If analysis fails, return all test files to be safe
            return set(test_files)

    async def get_generation_context(self, project_id: str, feature_description: str) -> Dict[str, str]:
        context = {
            "architecture_context": "",
            "previous_context": "",
            "research_context": "",
            "interface_details": ""
        }

        # Get architecture plan from memory
        try:
            plan_memory = await self.retrieve_memory_by_key(
                key=f"architecture_plan_{project_id}",
                project_id=project_id,
                collection_type="code_artifacts"
            )
            if plan_memory and plan_memory.get("content"):
                plan = json.loads(plan_memory["content"])
                # Create compact architecture summary
                features = plan.get("features", [])
                goals = plan.get("goals", [])
                approach = plan.get("technical_approach", "Not specified")

                context["architecture_context"] = f"Features: {len(features)} items, Goals: {len(goals)} items, Approach: {approach[:100]}..."
        except Exception as e:
            self._log("DEBUG", f"Could not retrieve architecture plan: {e}")

        # Get previous context from memory
        try:
            # Look for previous test results or reviews for continuity
            prev_memories = await self.retrieve_memory(
                query=feature_description,
                limit=5,
                memory_type="test_results",
                project_id=project_id,
                collection_type="code_artifacts"
            )
            if prev_memories:
                context["previous_context"] = f"Previous test results found ({len(prev_memories)} items)"
        except Exception:
            pass

        # Get research context
        try:
            research_memory = await self.retrieve_memory_by_key(
                key=f"research_context_{project_id}",
                project_id=project_id,
                collection_type="code_artifacts"
            )
            if research_memory and research_memory.get("content"):
                context["research_context"] = research_memory["content"]
        except Exception:
            pass

        # Get interface details from memory
        try:
            interface_memory = await self.retrieve_memory_by_key(
                key=f"interface_contracts_{project_id}",
                project_id=project_id,
                collection_type="code_artifacts"
            )
            if interface_memory and interface_memory.get("content"):
                contracts = json.loads(interface_memory["content"])
                if isinstance(contracts, list):
                    # Create interface summary
                    interfaces_summary = "\n".join([
                        f"- {c.get('name', 'unknown')}: {c.get('signature', '')}"
                        for c in contracts[:10]  # Limit to first 10
                    ])
                    context["interface_details"] = interfaces_summary
        except Exception:
            pass

        return context
    
    def _detect_language_and_framework(
        self,
        code_files: Dict[str, str]
    ) -> tuple[str, str]:
        language, test_framework = detect_language_and_framework(code_files)
        return language, test_framework
    
    async def review_and_generate_tests(
        self,
        code_files: Dict[str, str],
        task_description: str,
        requirements: str,
        language: str = "Python",
        test_framework: str = "pytest",
        architecture_context: str = "",
        interface_details: str = "",
        user_feedback: str = "None",
        previous_test_logs: str = "None"
    ) -> Dict[str, Any]:
        # Use utility function for code block language
        code_block_lang = get_markdown_code_block_lang(language)
        
        # Format code files for prompt
        code_text = "\n\n".join([
            f"File Path: {path}\n```{code_block_lang}\n{content}\n```"
            for path, content in code_files.items()
        ])
        
        # Extract file paths for import guidance
        file_paths_list = "\n".join([f"  - {path}" for path in code_files.keys()])
        
        # Build system prompt using external template
        system_prompt = self.build_system_prompt(
            additional_instructions=QA_REVIEW_SYSTEM_PROMPT.format(
                language=language,
                test_framework=test_framework
            )
        )
        
        # Build user prompt using external template with full context
        user_prompt = QA_REVIEW_USER_PROMPT_TEMPLATE.format(
            language=language,
            test_framework=test_framework,
            task_description=task_description,
            requirements=requirements if requirements else "No specific requirements provided",
            architecture_context=architecture_context if architecture_context else "No architecture context available",
            interface_details=interface_details if interface_details else "No interface contracts available - generate tests based on code inspection",
            file_paths_list=file_paths_list,
            code_text=code_text,
            user_feedback=user_feedback,
            previous_test_logs=previous_test_logs
        )
        
        # Note: Research context already gathered by Developer agent during architecture planning
        # No additional research needed here - reduces token usage significantly
        
        # Single LLM call for both review and tests using Pydantic schema
        try:
            result = await self.invoke_llm_structured(
                prompt=user_prompt,
                schema=ReviewAndTestsOutput,  # Use Pydantic model
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Validate result
            if result is None:
                raise BaseAgentError("LLM returned None for code review")
            
            # Convert Pydantic model to dict if needed
            if hasattr(result, 'model_dump'):
                result = result.model_dump()
            elif hasattr(result, 'dict'):
                result = result.dict()
            
            # Validate required fields
            if not isinstance(result, dict):
                raise BaseAgentError(f"Expected dict, got {type(result)}")
            
            review = result.get("review")
            tests = result.get("tests")
            
            if review is None or tests is None:
                raise BaseAgentError(
                    f"LLM response missing required fields. Has review: {review is not None}, has tests: {tests is not None}"
                )
            
            # Convert nested Pydantic models if needed
            if hasattr(review, 'model_dump'):
                result["review"] = review.model_dump()
            
            # Convert test items if they are Pydantic models
            if isinstance(tests, list):
                result["tests"] = [
                    t.model_dump() if hasattr(t, 'model_dump') else t 
                    for t in tests
                ]
            
            return result
            
        except Exception as e:
            raise BaseAgentError(f"Code review and test generation failed: {str(e)}") from e
    

    async def _check_workflow_exists(
        self,
        repository: str,
        branch: str
    ) -> bool:
        """
        Check if GitHub Actions workflow file exists in repository
        
        Args:
            repository: Repository name (owner/repo format)
            branch: Branch name to check
            
        Returns:
            True if workflow exists, False otherwise
        """
        try:
            await self.github_client.get_file_content(
                repo=repository,
                path=".github/workflows/ci.yml",
                ref=branch
            )
            return True
        except Exception:
            return False
    
    async def _generate_workflow_file(
        self,
        language: str,
        test_framework: str,
        code_files: Dict[str, str] = {}
    ) -> FileChange:
        """
        Generate CI workflow using robust static templates.
        
        We rely on static templates because:
        1. They are guaranteed to be valid YAML (unlike LLM output)
        2. They are faster and save tokens
        3. Our templates already handle multiple package managers
        4. We inject specific versions (Node 20, Python 3.11) extracted from config files
        """
        self._log("INFO", f"Generating CI workflow using static template for {language}/{test_framework}")
        
        # Extract versions from config files
        versions = extract_project_versions(code_files)
        if versions:
            self._log("INFO", f"Extracted project versions: {versions}")
        
        # Get template content with injected versions
        workflow_content = get_workflow_content(language, test_framework, versions)
        
        return FileChange(
            path=".github/workflows/ci.yml",
            content=workflow_content
        )

    async def _post_test_results_comment(
        self,
        repository: str,
        pr_number: int,
        github_actions_status: Dict[str, Any],
        language: str,
        test_framework: str
    ) -> None:
        """
        Post test execution results as PR comment
        
        Args:
            repository: Repository name (owner/repo format)
            pr_number: Pull request number
            github_actions_status: GitHub Actions check run status
            language: Programming language
            test_framework: Test framework used
        """
        conclusion = github_actions_status.get("conclusion", "unknown")
        
        if conclusion == "timed_out":
            comment = TEST_RESULTS_TIMED_OUT_TEMPLATE.format(
                reason=github_actions_status.get('error', 'Timeout after 5 minutes')
            )
        elif conclusion == "success":
            comment = TEST_RESULTS_SUCCESS_TEMPLATE.format(
                language=language,
                test_framework=test_framework,
                workflow_name=github_actions_status.get('workflow_name', 'CI'),
                details_url=github_actions_status.get('html_url', '')
            )
        elif conclusion == "failure":
            details = github_actions_status.get('details', [])
            failed_checks = [d for d in details if d.get('conclusion') == 'failure']
            
            comment = TEST_RESULTS_FAILURE_HEADER_TEMPLATE.format(
                language=language,
                test_framework=test_framework,
                workflow_name=github_actions_status.get('workflow_name', 'CI')
            )
            for check in failed_checks:
                comment += f"\n- [{check.get('name')}]({check.get('html_url')})"
            
            comment += TEST_RESULTS_FAILURE_FOOTER_TEMPLATE.format(
                details_url=github_actions_status.get('html_url', '')
            )
        else:
            comment = TEST_RESULTS_UNKNOWN_TEMPLATE.format(
                conclusion=conclusion,
                language=language,
                test_framework=test_framework,
                details_url=github_actions_status.get('html_url', '')
            )
        
        comment += TEST_RESULTS_FOOTER
        
        try:
            await self.github_client.add_pr_comment(
                repo=repository,
                pr_number=pr_number,
                comment=comment
            )
        except Exception as e:
            pass
    async def post_review_comment(
        self,
        repository: str,
        pr_number: int,
        review_data: Dict[str, Any]
    ) -> None:
        """
        Post code review feedback as PR comment
        
        Formats the review data into a comprehensive markdown comment
        and posts it to the pull request.
        
        Args:
            repository: Repository name (owner/repo format)
            pr_number: Pull request number
            review_data: Review data from LLM
            
        Raises:
            BaseAgentError: If posting comment fails
        """
        # Build comprehensive review comment
        comment_parts = [
            QA_REVIEW_HEADER,
            QA_REVIEW_QUALITY_LINE.format(quality=review_data['overall_quality'].upper())
        ]
        
        # Add security issues if any
        if review_data.get("security_issues"):
            comment_parts.append(QA_REVIEW_SECURITY_HEADER)
            for issue in review_data["security_issues"]:
                comment_parts.append(f"- ⚠️ {issue}")
        
        # Add code smells if any
        if review_data.get("code_smells"):
            comment_parts.append(QA_REVIEW_CODE_SMELLS_HEADER)
            for smell in review_data["code_smells"]:
                comment_parts.append(f"- {smell}")
        
        # Add performance issues if any
        if review_data.get("performance_issues"):
            comment_parts.append(QA_REVIEW_PERFORMANCE_HEADER)
            for issue in review_data["performance_issues"]:
                comment_parts.append(f"- {issue}")
        
        # Add suggestions if any
        if review_data.get("suggestions"):
            comment_parts.append(QA_REVIEW_SUGGESTIONS_HEADER)
            for suggestion in review_data["suggestions"]:
                comment_parts.append(f"- {suggestion}")
        
        # Add detailed feedback
        comment_parts.append(QA_REVIEW_FEEDBACK_HEADER)
        comment_parts.append(review_data["feedback_comment"])
        
        # Add footer
        comment_parts.append(QA_REVIEW_FOOTER)
        
        comment = "\n".join(comment_parts)
        
        # Post comment to PR
        try:
            # Note: GitHub client needs add_pr_comment method
            # This will be implemented in github_client.py
            await self.github_client.add_pr_comment(
                repo=repository,
                pr_number=pr_number,
                comment=comment
            )            
        except Exception as e:
            raise BaseAgentError(f"Failed to post review comment: {str(e)}") from e
 
# Register agent with factory
from agents.config import AgentFactory
AgentFactory.register_agent(AgentRole.QA, QAAgent)

