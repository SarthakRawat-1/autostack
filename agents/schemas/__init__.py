# File: agents/schemas/__init__.py
"""
Agent Pydantic Schemas

This module provides Pydantic models for structured LLM output validation.
These models replace the previous JSON schema dictionaries for type-safe output.
"""

from agents.schemas.developer import (
    ModuleDefinition,
    InterfaceContracts,
    TechStack,
    CodingStandards,
    DataFlow,
    TestingStrategy,
    ArchitecturePlan,
    FileOutput,
    FeatureGeneration,
)
from agents.schemas.pm import (
    FeatureSpec,
    ProjectPlan,
    TaskSpec,
    TaskBreakdown,
)
from agents.schemas.qa import (
    CodeIssue,
    SecurityIssue,
    CodeReview,
    TestCase,
    TestFile,
    TestGeneration,
    ReviewOutput,
    GeneratedTestFile,
    ReviewAndTestsOutput,
)
from agents.schemas.documentation import (
    DocumentationFile,
    DocumentationOutput,
)
from agents.schemas.devops import (
    TerraformCodebase,
)
from agents.schemas.infra_architect import (
    AzureResource,
    ResourcePlan,
)

__all__ = [
    # Developer schemas
    "ModuleDefinition",
    "InterfaceContracts",
    "TechStack",
    "CodingStandards",
    "DataFlow",
    "TestingStrategy",
    "ArchitecturePlan",
    "FileOutput",
    "FeatureGeneration",
    # PM schemas
    "FeatureSpec",
    "ProjectPlan",
    "TaskSpec",
    "TaskBreakdown",
    # QA schemas  
    "CodeIssue",
    "SecurityIssue",
    "CodeReview",
    "TestCase",
    "TestGeneration",
    "ReviewOutput",
    "GeneratedTestFile",
    "ReviewAndTestsOutput",
    # Documentation schemas
    "DocumentationFile",
    "DocumentationOutput",
    # DevOps schemas
    "TerraformCodebase",
    # Infra Architect schemas
    "AzureResource",
    "ResourcePlan",
]
