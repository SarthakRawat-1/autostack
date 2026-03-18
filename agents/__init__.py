"""
AutoStack Agents Module

This module contains all agent implementations including:
- BaseAgent: Abstract base class for all agents
- ProjectManagerAgent: Analyzes requirements and creates task breakdowns
- DeveloperAgent: Generates code implementations
- QAAgent: Reviews code and generates tests
- DocumentationAgent: Generates project documentation (optional)
"""

from agents.base import BaseAgent, BaseAgentError, TaskResult
from agents.config import (
    AgentRole,
    AgentConfig,
    ProjectManagerConfig,
    DeveloperConfig,
    QAConfig,
    DocumentationConfig,
    InfraArchitectConfig,
    DevOpsConfig,
    SecOpsConfig,
    AgentFactory,
    AgentConfigurationError
)
from agents.project_manager import ProjectManagerAgent
from agents.developer import DeveloperAgent
from agents.qa import QAAgent
from agents.documentation import DocumentationAgent

from agents.infra_architect import InfraArchitectAgent
from agents.devops import DevOpsAgent
from agents.secops import SecOpsAgent

__version__ = "0.1.0"

__all__ = [
    # Base classes
    "BaseAgent",
    "BaseAgentError",
    "TaskResult",

    # Configuration
    "AgentRole",
    "AgentConfig",
    "ProjectManagerConfig",
    "DeveloperConfig",
    "QAConfig",
    "DocumentationConfig",
    "InfraArchitectConfig",
    "DevOpsConfig",
    "SecOpsConfig",
    "AgentFactory",
    "AgentConfigurationError",

    # Agents
    "ProjectManagerAgent",
    "DeveloperAgent",
    "QAAgent",
    "DocumentationAgent",
    "InfraArchitectAgent",
    "DevOpsAgent",
    "SecOpsAgent",
]
