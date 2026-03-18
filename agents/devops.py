# File: agents/devops.py
"""
DevOps Agent

This agent acts as the 'Infrastructure Engineer'.
It takes the resource plan from the Infra Architect and writes the actual Terraform code.
It uses Tavily to find correct resource syntax and generates GitHub Actions workflows.
"""

import logging
import json
import os
import subprocess
import tempfile
from typing import Dict, Any, List, Optional

from agents.base import BaseAgent
from agents.config import AgentConfig, AgentRole
from agents.prompts.devops import DEVOPS_SYSTEM_PROMPT, DEVOPS_GENERATION_USER_PROMPT
from agents.schemas.devops import TerraformCodebase
from services.research import get_research_service
from services.github_client import GitHubClient
from services.notification import NotificationService
from utils.logging import log_to_db

logger = logging.getLogger(__name__)


class DevOpsAgent(BaseAgent):
    """
    DevOps Agent
    
    Responsibilities:
    1. Translate Resource Plan (JSON) into Terraform Code (Azure).
    2. Use Tavily to fetch syntax for unknown resources.
    3. Generate GitHub Actions CI/CD workflows.
    4. Run 'terraform fmt' and 'terraform validate' (if available).
    5. Prepare files for commit to GitHub.
    """
    
    def __init__(
        self,
        llm,
        memory,
        github_client,
        notification_service: Optional[NotificationService] = None,
        config: Optional[AgentConfig] = None,
        **kwargs
    ):
        super().__init__(llm, memory, config, **kwargs)
        self.research_service = get_research_service()
        self.github_client = github_client
        self.notification_service = notification_service
        
    async def _research_resources(self, resources: List[Dict[str, Any]]) -> str:
        """
        Research/Verify Terraform syntax for requested resources.
        
        Args:
            resources: List of resource dictionaries from the plan
            
        Returns:
            String containing research notes and syntax examples
        """
        if not resources:
            return ""
            
        self._log("INFO", f"Researching {len(resources)} resources via Tavily...")
        research_notes = []
        
        # Group resources by type to minimize queries
        # e.g. if we have 3 "Azure Container Apps" items, just research once
        resource_types = set()
        for r in resources:
            r_type = r.get("type", "").lower()
            if r_type:
                resource_types.add(r_type)
        
        for r_type in list(resource_types)[:5]:  # Limit to 5 unique types to save tokens/time
            try:
                # Query for specific Terraform syntax and best practices
                query = f"terraform azurerm {r_type} resource syntax example best practices 2024"
                
                # Use Tavily to get concise technical details
                result = await self.research_service.search(
                    query=query,
                    max_results=2,
                    include_answer=True 
                )
                
                content = result.get("answer") or ""
                if not content and result.get("results"):
                    content = result["results"][0].get("content", "")[:500]
                    
                if content:
                    research_notes.append(f"## Resource: {r_type}\n{content}")
                    
            except Exception as e:
                self._log("WARNING", f"Failed to research resource {r_type}: {e}")
                
        return "\n\n".join(research_notes)
        
    async def _fetch_existing_code(
        self,
        github_client: GitHubClient,
        repo: str,
        branch: str = "main"
    ) -> str:
        """Fetch all existing Terraform files from the repo to support updates."""
        try:
            # Discover all files in the repo and filter for *.tf
            all_files = await github_client.list_repository_files(repo, ref=branch)
            tf_files = [f for f in all_files if f.endswith(".tf")]

            if not tf_files:
                return "None (greenfield)"

            self._log("INFO", f"Found {len(tf_files)} existing .tf files in {repo}")
            existing_content = ""
            for fname in tf_files:
                try:
                    content = await github_client.get_file_content(repo, fname, ref=branch)
                    existing_content += f"\n--- {fname} ---\n{content}\n"
                except Exception:
                    pass  # File unreadable, skip

            return existing_content if existing_content else "None (greenfield)"
        except Exception as e:
            self._log("WARNING", f"Failed to fetch existing code: {e}")
            return "Error fetching existing code"

    async def generate_code(
        self,
        resource_plan: Dict[str, Any],
        github_client: Optional[GitHubClient] = None,
        target_repo: Optional[str] = None,
        commit: bool = True
    ) -> Dict[str, str]:
        """
        Main entry point: Generates Terraform files from the plan.
        """
        
        # Step 1: Research Resources
        resources = resource_plan.get("resources", [])
        research_context = await self._research_resources(resources)

        # Step 1.5: Fetch Existing Code (if updating)
        existing_files_str = "None (greenfield)"
        if github_client and target_repo:
            self._log("INFO", f"Fetching existing Terraform code from {target_repo}...")
            existing_files_str = await self._fetch_existing_code(github_client, target_repo)
        
        # Step 2: Generate Terraform Code
        tf_files = await self._generate_terraform_files(
            resource_plan, 
            research_context,
            existing_files_str
        )
        
        # Step 3: Generate GitHub Actions
        workflow_file = self._generate_github_action()
        tf_files[".github/workflows/terraform.yml"] = workflow_file
        
        # Step 4: Validate & Format (Local Simulation)
        tf_files = self._format_and_validate(tf_files)
        
        # Step 5: Commit to GitHub (if client provided and commit requested)
        if commit and github_client and target_repo:
            await self._commit_to_github(github_client, target_repo, tf_files)
            
        return tf_files

    async def _generate_terraform_files(
        self,
        plan: Dict[str, Any],
        research_context: str,
        existing_files: str = "None"
    ) -> Dict[str, str]:
        """Call LLM to write the actual .tf files using Pydantic schema."""

        system_prompt = DEVOPS_SYSTEM_PROMPT
        user_msg = DEVOPS_GENERATION_USER_PROMPT.format(
            resource_plan=json.dumps(plan, indent=2),
            research_context=research_context,
            existing_files=existing_files
        )

        try:
            # Invoke LLM with Pydantic structured output
            output = await self.invoke_llm_structured(
                prompt=user_msg,
                schema=TerraformCodebase,
                system_prompt=system_prompt,
            )

            files = {
                "main.tf": output["main_tf"],
                "variables.tf": output["variables_tf"],
                "provider.tf": output["provider_tf"]
            }
            if output.get("outputs_tf"):
                files["outputs.tf"] = output["outputs_tf"]

            if output.get("extra_files"):
                files.update(output["extra_files"])

            # Ensure the provider configuration is properly set up for Azure
            # Add default provider configuration if not present
            if "provider.tf" not in files or "azurerm" not in files["provider.tf"]:
                default_provider = '''provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.0"
}
'''
                files["provider.tf"] = default_provider

            # Ensure variables.tf includes required variables
            if "variables.tf" not in files or "subscription_id" not in files["variables.tf"]:
                default_vars = '''variable "subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "location" {
  description = "Azure Region"
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Azure Resource Group Name"
  type        = string
  default     = "rg-autostack"
}
'''
                # Append to existing variables if they exist
                if "variables.tf" in files:
                    files["variables.tf"] = default_vars + "\n" + files["variables.tf"]
                else:
                    files["variables.tf"] = default_vars

            return files

        except Exception as e:
            self._log("ERROR", f"Terraform generation failed: {e}")
            # Fallback if Pydantic fails? Or re-raise.
            # Ideally retry or fallback to text.
            # For now, simpler to raise.
            raise

    def _generate_github_action(self) -> str:
        """Returns standard Terraform CI/CD workflow."""
        return """
name: 'Terraform'

on:
  push:
    branches: [ "main" ]
  pull_request:

permissions:
  contents: read

jobs:
  terraform:
    name: 'Terraform'
    runs-on: ubuntu-latest
    environment: production

    defaults:
      run:
        shell: bash

    steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Setup Terraform
      uses: hashicorp/setup-terraform@v1
      with:
        cli_config_credentials_token: ${{ secrets.TF_API_TOKEN }}

    - name: Terraform Init
      run: terraform init

    - name: Terraform Format
      run: terraform fmt -check

    - name: Terraform Plan
      run: terraform plan -input=false
        """

    def _format_and_validate(self, files: Dict[str, str]) -> Dict[str, str]:
        """
        Optimistically runs terraform fmt if terraform is installed.
        Returns the formatted file content.
        """
        # Check if terraform is installed
        try:
            subprocess.run(["terraform", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            self._log("WARNING", "Terraform binary not found. Skipping local formatting.")
            return files

        with tempfile.TemporaryDirectory() as tmpdirname:
            # Write files
            for fname, content in files.items():
                # Skip subdirectories for now (like .github)
                if "/" in fname:
                    continue
                with open(os.path.join(tmpdirname, fname), 'w', encoding='utf-8') as f:
                    f.write(content)

            # Run fmt
            try:
                subprocess.run(["terraform", "fmt"], cwd=tmpdirname, check=True, capture_output=True)

                # Read back
                for fname in files.keys():
                    if "/" in fname: continue
                    with open(os.path.join(tmpdirname, fname), 'r', encoding='utf-8') as f:
                        files[fname] = f.read()

            except Exception as e:
                self._log("WARNING", f"Terraform fmt failed: {e}")

        return files

    async def apply_code(
        self,
        files: Dict[str, str],
        azure_credentials: Dict[str, str],
        azure_subscription_id: str
    ) -> Dict[str, Any]:
        """
        Executes terraform apply.

        Args:
            files: Terraform files content.
            azure_credentials: Dict with tenant_id, client_id, client_secret.
            azure_subscription_id: Azure Subscription ID to deploy to.

        Returns:
            Dict with execution results.
        """
        required_keys = ["tenant_id", "client_id", "client_secret"]
        missing = [k for k in required_keys if not azure_credentials.get(k)]
        if missing:
            raise ValueError(f"Missing Azure credential fields: {missing}")

        with tempfile.TemporaryDirectory() as tmpdirname:
            # Write files
            for fname, content in files.items():
                full_path = os.path.join(tmpdirname, fname)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)

            # Setup Environment - Azure Service Principal auth
            env = os.environ.copy()
            env["ARM_SUBSCRIPTION_ID"] = azure_subscription_id
            env["ARM_TENANT_ID"] = azure_credentials["tenant_id"]
            env["ARM_CLIENT_ID"] = azure_credentials["client_id"]
            env["ARM_CLIENT_SECRET"] = azure_credentials["client_secret"]
            env["TF_VAR_subscription_id"] = azure_subscription_id

            self._log("INFO", f"Running Terraform Apply for subscription {azure_subscription_id}...")

            try:
                # Initialize Terraform with proper provider configuration
                init_result = subprocess.run(
                    ["terraform", "init", "-upgrade"],
                    cwd=tmpdirname,
                    check=False,  # Don't throw on error, we'll check return code
                    capture_output=True,
                    text=True,
                    env=env
                )

                if init_result.returncode != 0:
                    self._log("ERROR", f"Terraform init failed: {init_result.stderr}")

                    if self.notification_service:
                        try:
                            from services.notification import NotificationLevel
                            await self.notification_service.send_notification(
                                message=f"Terraform initialization failed for subscription {azure_subscription_id}.\n\n"
                                        f"**Subscription:** {azure_subscription_id}\n"
                                        f"**Error:** {init_result.stderr[:200]}",
                                level=NotificationLevel.ERROR,
                                title="Terraform Initialization Failed",
                                fields={
                                    "Subscription ID": azure_subscription_id,
                                    "Phase": "Init",
                                    "Error": init_result.stderr[:100]
                                }
                            )
                        except Exception as e:
                            self._log("WARNING", f"Failed to send init failure notification: {e}")

                    return {
                        "success": False,
                        "stdout": init_result.stdout,
                        "stderr": init_result.stderr,
                        "phase": "init"
                    }

                # Plan first to see what will be created
                plan_result = subprocess.run(
                    ["terraform", "plan", f"-var=subscription_id={azure_subscription_id}"],
                    cwd=tmpdirname,
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env
                )

                if plan_result.returncode != 0:
                    self._log("ERROR", f"Terraform plan failed: {plan_result.stderr}")

                    if self.notification_service:
                        try:
                            from services.notification import NotificationLevel
                            await self.notification_service.send_notification(
                                message=f"Terraform plan failed for subscription {azure_subscription_id}.\n\n"
                                        f"**Subscription:** {azure_subscription_id}\n"
                                        f"**Error:** {plan_result.stderr[:200]}",
                                level=NotificationLevel.ERROR,
                                title="Terraform Plan Failed",
                                fields={
                                    "Subscription ID": azure_subscription_id,
                                    "Phase": "Plan",
                                    "Error": plan_result.stderr[:100]
                                }
                            )
                        except Exception as e:
                            self._log("WARNING", f"Failed to send plan failure notification: {e}")

                    return {
                        "success": False,
                        "stdout": plan_result.stdout,
                        "stderr": plan_result.stderr,
                        "phase": "plan"
                    }

                # Apply with auto-approve
                apply_cmd = [
                    "terraform", "apply",
                    "-auto-approve",
                    f"-var=subscription_id={azure_subscription_id}"
                ]

                apply_result = subprocess.run(
                    apply_cmd,
                    cwd=tmpdirname,
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env
                )

                if apply_result.returncode == 0:
                    self._log("INFO", "Terraform Apply Successful")

                    if self.notification_service:
                        try:
                            from services.notification import NotificationLevel
                            await self.notification_service.send_notification(
                                message=f"Infrastructure provisioning completed successfully for subscription {azure_subscription_id}!\n\n"
                                        f"**Subscription:** {azure_subscription_id}\n"
                                        f"**Resources:** Infrastructure deployed successfully\n\n"
                                        f"Your Azure resources are now active.",
                                level=NotificationLevel.SUCCESS,
                                title="Infrastructure Provisioned Successfully",
                                fields={
                                    "Subscription ID": azure_subscription_id,
                                    "Phase": "Apply",
                                    "Status": "Success"
                                }
                            )
                        except Exception as e:
                            self._log("WARNING", f"Failed to send success notification: {e}")

                    return {
                        "success": True,
                        "stdout": apply_result.stdout,
                        "stderr": apply_result.stderr,
                        "phase": "apply"
                    }
                else:
                    self._log("ERROR", f"Terraform Apply Failed: {apply_result.stderr}")

                    if self.notification_service:
                        try:
                            from services.notification import NotificationLevel
                            await self.notification_service.send_notification(
                                message=f"Infrastructure provisioning failed for subscription {azure_subscription_id}.\n\n"
                                        f"**Subscription:** {azure_subscription_id}\n"
                                        f"**Error:** {apply_result.stderr[:200]}",
                                level=NotificationLevel.ERROR,
                                title="Infrastructure Provisioning Failed",
                                fields={
                                    "Subscription ID": azure_subscription_id,
                                    "Phase": "Apply",
                                    "Error": apply_result.stderr[:100]
                                }
                            )
                        except Exception as e:
                            self._log("WARNING", f"Failed to send apply failure notification: {e}")

                    return {
                        "success": False,
                        "stdout": apply_result.stdout,
                        "stderr": apply_result.stderr,
                        "phase": "apply"
                    }

            except Exception as e:
                self._log("ERROR", f"Execution Error: {e}")
                import traceback

                if self.notification_service:
                    try:
                        from services.notification import NotificationLevel
                        await self.notification_service.send_notification(
                            message=f"Infrastructure provisioning execution error for subscription {azure_subscription_id}.\n\n"
                                    f"**Subscription:** {azure_subscription_id}\n"
                                    f"**Error:** {str(e)[:200]}\n\n"
                                    f"Traceback: {traceback.format_exc()[:200]}",
                            level=NotificationLevel.ERROR,
                            title="Infrastructure Execution Error",
                            fields={
                                "Subscription ID": azure_subscription_id,
                                "Phase": "Execution",
                                "Error": str(e)[:100]
                            }
                        )
                    except Exception as notification_error:
                        self._log("WARNING", f"Failed to send execution error notification: {notification_error}")

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Execution Error: {str(e)}\n{traceback.format_exc()}",
                    "phase": "execution"
                }

    async def _commit_to_github(
        self,
        client: GitHubClient,
        repo: str,
        files: Dict[str, str],
        branch: str = "main"
    ) -> str:
        """Commits the generated files to a feature branch and opens a PR.
        
        Returns:
            The name of the feature branch that was created.
        """
        from models.github_models import FileChange
        import time

        # Create a unique feature branch
        timestamp = int(time.time())
        feature_branch = f"terraform/autostack-{timestamp}"

        changes = []
        for path, content in files.items():
            # Skip sensitive files like credentials
            if "credentials" in path.lower() or "key" in path.lower():
                logger.warning(f"Skipping sensitive file: {path}")
                continue
            changes.append(FileChange(path=path, content=content, mode="100644"))

        if not changes:
            self._log("WARNING", "No files to commit after filtering sensitive content")
            return branch  # Fallback to the base branch

        try:
            # 1. Create feature branch from the base branch
            await client.create_branch(repo, feature_branch, from_branch=branch)
            self._log("INFO", f"Created feature branch: {feature_branch}")

            # 2. Commit files to the feature branch
            await client.commit_files(
                repo=repo,
                branch=feature_branch,
                files=changes,
                message="[AutoStack] Add Infrastructure Terraform Code"
            )
            self._log("INFO", f"Committed {len(changes)} files to {repo}/{feature_branch}")

            # 3. Open a Pull Request for review
            pr = await client.create_pull_request(
                repo=repo,
                head=feature_branch,
                base=branch,
                title="[AutoStack] Infrastructure Terraform Code",
                body=(
                    "## AutoStack — Terraform Infrastructure\n\n"
                    "This PR was auto-generated by the AutoStack cloud workflow.\n\n"
                    f"**Files changed:** {len(changes)}\n\n"
                    "Please review the Terraform code and approve the PR before "
                    "or after the `terraform apply` step completes.\n"
                )
            )
            self._log("INFO", f"Opened PR #{pr.number} in {repo}: {feature_branch} -> {branch}")

            # Notification
            if self.notification_service:
                try:
                    from services.notification import NotificationLevel
                    await self.notification_service.send_notification(
                        message=(
                            f"Terraform infrastructure code committed to feature branch.\n\n"
                            f"**Repository:** {repo}\n"
                            f"**Branch:** {feature_branch}\n"
                            f"**PR:** #{pr.number}\n"
                            f"**Files:** {len(changes)} Terraform files committed\n\n"
                            f"Review the PR before merging."
                        ),
                        level=NotificationLevel.SUCCESS,
                        title="Terraform Code Committed",
                        fields={
                            "Repository": repo,
                            "Branch": feature_branch,
                            "PR": f"#{pr.number}",
                            "Files Committed": f"{len(changes)} files",
                        }
                    )
                except Exception as e:
                    self._log("WARNING", f"Failed to send commit notification: {e}")

            return feature_branch

        except Exception as e:
            self._log("ERROR", f"Failed to commit code to GitHub: {e}")
            if self.notification_service:
                try:
                    from services.notification import NotificationLevel
                    await self.notification_service.send_notification(
                        message=(
                            f"Failed to commit Terraform infrastructure code.\n\n"
                            f"**Repository:** {repo}\n"
                            f"**Error:** {str(e)}"
                        ),
                        level=NotificationLevel.ERROR,
                        title="Terraform Commit Failed",
                        fields={"Repository": repo, "Error": str(e)}
                    )
                except Exception as notification_error:
                    self._log("WARNING", f"Failed to send commit failure notification: {notification_error}")
            raise

# Register agent with factory
from agents.config import AgentFactory
AgentFactory.register_agent(AgentRole.DEVOPS, DevOpsAgent)
