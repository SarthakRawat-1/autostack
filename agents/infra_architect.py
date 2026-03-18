# File: agents/infra_architect.py
"""
Infrastructure Architect Agent

This agent acts as the 'Product Manager' for cloud infrastructure.
It analyzes user requirements, inspecting existing repositories if provided,
and produces a detailed 'Resource Plan' (Blueprint) for the DevOps agent to implement.
"""

import logging
from typing import Dict, Any, Optional

from agents.base import BaseAgent
from agents.config import AgentConfig, AgentRole
from agents.prompts.infra_architect import INFRA_ARCHITECT_SYSTEM_PROMPT, INFRA_PLANNING_USER_PROMPT
from agents.schemas.infra_architect import ResourcePlan
from utils.logging import log_to_db

logger = logging.getLogger(__name__)


class InfraArchitectAgent(BaseAgent):
    """
    Infrastructure Architect Agent
    
    Responsibilities:
    1. Analyze natural language requests.
    2. Inspect repositories (via RepoMapService) to detect workload types.
    3. classify intent (Deployment vs Pure Provisioning).
    4. Generate a structured Resource Plan (Pydantic-validated).
    """
    
    def __init__(
        self,
        llm,
        memory,
        config: AgentConfig,
        **kwargs
    ):
        super().__init__(llm, memory, config, **kwargs)

    async def analyze_and_plan(
        self,
        user_request: str,
        repo_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: Analyzes requirements and produces a Resource Plan.
        """
        
        # Step 1: Gather Context
        repo_summary = ""
        context_str = f"User Request: {user_request}\n"
        
        if repo_url:
            context_str += f"Repository URL: {repo_url}\n"
            try:
                # Use RepoMapService properly via API
                from services.repomap.service import get_repomap_service
                from services.github_client import GitHubClient

                github_client = GitHubClient()
                repomap_service = get_repomap_service()

                # Parse owner/repo from URL
                repo_name = repo_url
                if "github.com" in repo_url:
                    parts = repo_url.rstrip("/").split("/")
                    repo_name = f"{parts[-2]}/{parts[-1]}"

                self._log("INFO", f"Analyzing repository: {repo_name}")
                repo_map = await repomap_service.get_repo_map_via_api(
                    github_client=github_client,
                    repo_name=repo_name,
                    branch="main",
                    max_files=50
                )

                if repo_map:
                    repo_summary = f"\nRepository Analysis (Repo Map):\n{repo_map}\n"
                    context_str += repo_summary
            except Exception as e:
                self._log("WARNING", f"Failed to map repository {repo_url}: {e}")
                context_str += f"\n(Repository analysis failed: {e})\n"

        # Step 2: Intent Classification & Planning Prompt
        system_prompt = INFRA_ARCHITECT_SYSTEM_PROMPT
        user_message = INFRA_PLANNING_USER_PROMPT.format(context_str=context_str)

        # Step 3: Call LLM with Pydantic structured output
        plan = await self.invoke_llm_structured(
            prompt=user_message,
            schema=ResourcePlan,
            system_prompt=system_prompt,
        )

        self._log("INFO", f"Generated Resource Plan: {plan.get('summary')}")
        return plan


# Register agent with factory
from agents.config import AgentFactory
AgentFactory.register_agent(AgentRole.INFRA_ARCHITECT, InfraArchitectAgent)
