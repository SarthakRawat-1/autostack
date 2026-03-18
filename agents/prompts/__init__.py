# File: agents/prompts/__init__.py
"""
Agent Prompt Templates

Provides prompt templates for all agents, helping reduce agent file sizes
and enabling reuse of common prompt patterns.
"""

from agents.prompts.developer import (
    ARCHITECTURE_SYSTEM_PROMPT,
    ARCHITECTURE_USER_PROMPT_TEMPLATE,
    FEATURE_GENERATION_SYSTEM_PROMPT,
    FEATURE_GENERATION_USER_PROMPT_TEMPLATE,
)
from agents.prompts.pm import (
    PROJECT_ANALYSIS_SYSTEM_PROMPT,
    PROJECT_ANALYSIS_USER_PROMPT_TEMPLATE,
    TASK_BREAKDOWN_SYSTEM_PROMPT,
    TASK_BREAKDOWN_USER_PROMPT_TEMPLATE,
)
from agents.prompts.qa import (
    QA_REVIEW_SYSTEM_PROMPT,
    QA_REVIEW_USER_PROMPT_TEMPLATE,
)
from agents.prompts.documentation import (
    DOCUMENTATION_SYSTEM_PROMPT,
    DOCUMENTATION_USER_PROMPT_TEMPLATE,
)
from agents.prompts.infra_architect import (
    INFRA_ARCHITECT_SYSTEM_PROMPT,
    INFRA_PLANNING_USER_PROMPT,
)
from agents.prompts.devops import (
    DEVOPS_SYSTEM_PROMPT,
    DEVOPS_GENERATION_USER_PROMPT,
)

__all__ = [
    # Developer prompts
    "ARCHITECTURE_SYSTEM_PROMPT",
    "ARCHITECTURE_USER_PROMPT_TEMPLATE",
    "FEATURE_GENERATION_SYSTEM_PROMPT",
    "FEATURE_GENERATION_USER_PROMPT_TEMPLATE",
    # PM prompts
    "PROJECT_ANALYSIS_SYSTEM_PROMPT",
    "PROJECT_ANALYSIS_USER_PROMPT_TEMPLATE",
    "TASK_BREAKDOWN_SYSTEM_PROMPT",
    "TASK_BREAKDOWN_USER_PROMPT_TEMPLATE",
    # QA prompts
    "QA_REVIEW_SYSTEM_PROMPT",
    "QA_REVIEW_USER_PROMPT_TEMPLATE",
    # Documentation prompts
    "DOCUMENTATION_SYSTEM_PROMPT",
    "DOCUMENTATION_USER_PROMPT_TEMPLATE",
    # Infra Architect prompts
    "INFRA_ARCHITECT_SYSTEM_PROMPT",
    "INFRA_PLANNING_USER_PROMPT",
    # DevOps prompts
    "DEVOPS_SYSTEM_PROMPT",
    "DEVOPS_GENERATION_USER_PROMPT",
]
