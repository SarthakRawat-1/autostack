# File: agents/secops.py
"""
SecOps Agent

This agent acts as the 'Security Auditor'.
It validates the generated Terraform code against compliance policies (using Checkov)
and estimates cloud costs (using Infracost).
"""

import logging
import json
import os
import subprocess
import tempfile
from typing import Dict, Any, List

from agents.base import BaseAgent
from agents.config import AgentConfig, AgentRole
from utils.logging import log_to_db

logger = logging.getLogger(__name__)


class SecOpsAgent(BaseAgent):
    """
    SecOps Agent
    
    Responsibilities:
    1. Scan Terraform code for security vulnerabilities (Checkov).
    2. Estimate cloud costs (Infracost).
    3. Produce a Pass/Fail validation report.
    """
    
    def __init__(
        self,
        llm,
        memory,
        config: AgentConfig,
        **kwargs
    ):
        super().__init__(llm, memory, config, **kwargs)
        # We might want to check if tools are installed here or in validation step

    async def validate_infrastructure(
        self,
        tf_files: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Main entry point: Validates the terraform files.
        
        Args:
            tf_files: Dict of Filename -> Content
            
        Returns:
            Validation Report (JSON)
        """
        
        with tempfile.TemporaryDirectory() as tmpdirname:
            # Write files to temp dir
            for fname, content in tf_files.items():
                if "/" in fname: continue # Skip subdirs
                with open(os.path.join(tmpdirname, fname), 'w', encoding='utf-8') as f:
                    f.write(content)

            # 1. Run Security Scan
            security_result = self._run_checkov(tmpdirname)

            # 2. Run Cost Estimate
            cost_result = self._run_infracost(tmpdirname)

            # 3. Analyze & Decide
            has_failures = security_result.get("failed_checks", 0) > 0
            if has_failures and self.config.strict_mode:
                status = "FAILED"
            elif has_failures:
                status = "WARNING"
            else:
                status = "PASSED"

            report = {
                "status": status,
                "security_summary": security_result,
                "cost_estimate": cost_result,
                "recommendations": self._generate_recommendations(security_result)
            }

            self._log("INFO", f"SecOps validation finished. Status: {status}")
            return report

    def _run_checkov(self, directory: str) -> Dict[str, Any]:
        """Runs checkov on the directory."""
        try:
            # Checkov output as JSON
            cmd = ["checkov", "-d", directory, "-o", "json", "--quiet"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0 and not result.stdout.strip().startswith("{"):
                # Checkov returns exit code 1 if issues found, but output should still be JSON
                # If stdout is empty or not JSON, something crashed
                pass

            try:
                data = json.loads(result.stdout)
                # Checkov might return a list if multiple runners or a dict
                if isinstance(data, list):
                    # Combine results? usually one object for terraform
                    data = data[0] if data else {}

                summary = data.get("summary", {})
                return {
                    "passed_checks": summary.get("passed", 0),
                    "failed_checks": summary.get("failed", 0),
                    "skipped_checks": summary.get("skipped", 0),
                    "details": data.get("results", {}).get("failed_checks", [])
                }
            except json.JSONDecodeError:
                self._log("WARNING", "Checkov output valid JSON parsing failed")
                return {"error": "Checkov failed to produce JSON", "raw": result.stdout[:200]}

        except FileNotFoundError:
            self._log("WARNING", "Checkov binary not found")
            return {"error": "Checkov not installed"}

    def _run_infracost(self, directory: str) -> Dict[str, Any]:
        """Runs infracost breakdown."""
        try:
            # Requires infracost API key in env
            if not os.environ.get("INFRACOST_API_KEY"):
                return {"error": "No Infracost API Key"}

            cmd = ["infracost", "breakdown", "--path", directory, "--format", "json"]
            result = subprocess.run(cmd, capture_output=True, check=False, text=True)

            try:
                data = json.loads(result.stdout)
                total_monthly = data.get("totalMonthlyCost", "0.0")
                return {
                    "total_monthly_cost": total_monthly,
                    "currency": data.get("currency", "USD")
                }
            except json.JSONDecodeError:
                return {"error": "Infracost JSON parsing failed"}

        except FileNotFoundError:
            self._log("WARNING", "Infracost binary not found")
            return {"error": "Infracost not installed"}

    def _generate_recommendations(self, security_result: Dict[str, Any]) -> List[str]:
        """Generate human-readable recommendations from failures."""
        recs = []
        failures = security_result.get("details", [])
        for fail in failures:
            # Checkov format: check_id, check_name, ...
            cid = fail.get("check_id")
            name = fail.get("check_name")
            recs.append(f"Fix {cid}: {name}")
        return recs

# Register agent with factory
from agents.config import AgentFactory
AgentFactory.register_agent(AgentRole.SECOPS, SecOpsAgent)
