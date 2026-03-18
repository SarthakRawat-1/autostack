# File: agents/config.py
"""
Agent Configuration System

This module defines agent roles, configuration dataclasses, and factory
functions for agent instantiation.

Implements: Requirements 2.2, 3.1, 4.1
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Type
from enum import Enum

from agents.base import BaseAgent
from langchain_core.language_models import BaseChatModel
from services.memory import AgentMemory
from utils.logging import log_to_db
import logging

logger = logging.getLogger(__name__)




class AgentRole(str, Enum):
    """
    Agent role enumeration
    
    Defines all available agent roles in the AutoStack system.
    """
    PROJECT_MANAGER = "project_manager"
    DEVELOPER = "developer"
    QA = "qa"
    DOCUMENTATION = "documentation"
    INFRA_ARCHITECT = "infra_architect"
    DEVOPS = "devops"
    SECOPS = "secops"
    
    def __str__(self) -> str:
        return self.value


@dataclass
class AgentConfig:
    """
    Base configuration for all agents
    
    Attributes:
        role: Agent role identifier
        llm_temperature: Temperature for LLM sampling (0.0 to 2.0)
        llm_max_tokens: Maximum tokens for LLM generation
        max_retries: Maximum retry attempts for operations
        enabled: Whether this agent is enabled
        metadata: Additional configuration metadata
    """
    role: AgentRole
    llm_temperature: float = 0.7
    llm_max_tokens: int = 6000
    max_retries: int = 3
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            "role": str(self.role),
            "llm_temperature": self.llm_temperature,
            "llm_max_tokens": self.llm_max_tokens,
            "max_retries": self.max_retries,
            "enabled": self.enabled,
            "metadata": self.metadata
        }


@dataclass
class ProjectManagerConfig(AgentConfig):
    """
    Configuration for Project Manager Agent
    
    Implements: Requirement 2.2 - Task breakdown generation
    
    Attributes:
        role: Fixed to PROJECT_MANAGER
        min_tasks: Minimum number of tasks to generate
        max_tasks: Maximum number of tasks to generate
        task_priority_levels: Number of priority levels (1-10)
        include_dependencies: Whether to analyze task dependencies
    """
    role: AgentRole = field(default=AgentRole.PROJECT_MANAGER, init=False)
    min_tasks: int = 3
    max_tasks: int = 20
    task_priority_levels: int = 5
    include_dependencies: bool = True
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.min_tasks < 1:
            raise ValueError("min_tasks must be at least 1")
        if self.max_tasks < self.min_tasks:
            raise ValueError("max_tasks must be greater than or equal to min_tasks")
        if self.task_priority_levels < 1 or self.task_priority_levels > 10:
            raise ValueError("task_priority_levels must be between 1 and 10")


@dataclass
class DeveloperConfig(AgentConfig):
    """
    Configuration for Developer Agent
    
    Implements: Requirement 3.1 - Code generation
    
    Attributes:
        role: Fixed to DEVELOPER
        github_enabled: Whether GitHub integration is enabled
        branch_prefix: Prefix for feature branches (e.g., "feature/")
        commit_message_template: Template for commit messages
        code_style: Code style preference (e.g., "pep8", "google")
        max_file_size: Maximum file size in bytes for code generation
    """
    role: AgentRole = field(default=AgentRole.DEVELOPER, init=False)
    github_enabled: bool = True
    branch_prefix: str = "feature/"
    commit_message_template: str = "[AutoStack] {task_description}"
    code_style: str = "pep8"
    max_file_size: int = 100000  # 100KB
    batch_size: int = 4  # Number of files to generate per batch (2-5 recommended)

    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.max_file_size < 1000:
            raise ValueError("max_file_size must be at least 1000 bytes")
        if self.batch_size < 1 or self.batch_size > 10:
            raise ValueError("batch_size must be between 1 and 10")


@dataclass
class QAConfig(AgentConfig):
    """
    Configuration for QA Agent
    
    Implements: Requirement 4.1 - Code review and testing
    
    Attributes:
        role: Fixed to QA
        github_enabled: Whether GitHub integration is enabled
        generate_tests: Whether to generate test cases
        execute_tests: Whether to execute generated tests
        test_framework: Test framework to use (e.g., "pytest", "unittest")
        min_test_coverage: Minimum test coverage percentage
        create_pull_requests: Whether to create pull requests
        pr_title_template: Template for PR titles
    """
    role: AgentRole = field(default=AgentRole.QA, init=False)
    github_enabled: bool = True
    generate_tests: bool = True
    execute_tests: bool = True
    test_framework: str = "pytest"
    min_test_coverage: float = 70.0
    create_pull_requests: bool = True
    pr_title_template: str = "[AutoStack] {task_description}"
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.min_test_coverage < 0 or self.min_test_coverage > 100:
            raise ValueError("min_test_coverage must be between 0 and 100")


@dataclass
class DocumentationConfig(AgentConfig):
    """
    Configuration for Documentation Agent (optional)
    
    Attributes:
        role: Fixed to DOCUMENTATION
        github_enabled: Whether GitHub integration is enabled
        generate_readme: Whether to generate README.md
        generate_api_docs: Whether to generate API documentation
        doc_format: Documentation format (e.g., "markdown", "rst")
        include_examples: Whether to include code examples
    """
    role: AgentRole = field(default=AgentRole.DOCUMENTATION, init=False)
    github_enabled: bool = True
    generate_readme: bool = True
    generate_api_docs: bool = True
    doc_format: str = "markdown"
    include_examples: bool = True


@dataclass
class InfraArchitectConfig(AgentConfig):
    """
    Configuration for Infrastructure Architect Agent
    
    Attributes:
        role: Fixed to INFRA_ARCHITECT
        cloud_provider: Target cloud provider (default: "azure")
    """
    role: AgentRole = field(default=AgentRole.INFRA_ARCHITECT, init=False)
    cloud_provider: str = "azure"


@dataclass
class DevOpsConfig(AgentConfig):
    """
    Configuration for DevOps Agent
    
    Attributes:
        role: Fixed to DEVOPS
        terraform_version: Terraform version to use
        auto_approve: Whether to auto-approve plans (not recommended for prod)
    """
    role: AgentRole = field(default=AgentRole.DEVOPS, init=False)
    terraform_version: str = "latest"
    auto_approve: bool = False


@dataclass
class SecOpsConfig(AgentConfig):
    """
    Configuration for SecOps Agent
    
    Attributes:
        role: Fixed to SECOPS
        framework: Security framework (e.g., "checkov")
        strict_mode: Whether to fail on low severity issues
        compliance_standards: List of standards (e.g., ["CIS"])
    """
    role: AgentRole = field(default=AgentRole.SECOPS, init=False)
    framework: str = "checkov"
    strict_mode: bool = False
    compliance_standards: list = field(default_factory=lambda: ["CIS"])


class AgentConfigurationError(Exception):
    """Exception raised for agent configuration errors"""
    pass


class AgentFactory:
    """
    Factory for creating agent instances
    
    Provides methods to instantiate agents with proper configuration
    and dependency injection.
    
    Implements: Requirements 2.2, 3.1, 4.1
    """
    
    # Registry of agent classes by role
    _agent_registry: Dict[AgentRole, Type[BaseAgent]] = {}
    
    # Default configurations by role
    _default_configs: Dict[AgentRole, AgentConfig] = {
        AgentRole.PROJECT_MANAGER: ProjectManagerConfig(),
        AgentRole.DEVELOPER: DeveloperConfig(),
        AgentRole.QA: QAConfig(),
        AgentRole.DOCUMENTATION: DocumentationConfig(),
        AgentRole.INFRA_ARCHITECT: InfraArchitectConfig(),
        AgentRole.DEVOPS: DevOpsConfig(),
        AgentRole.SECOPS: SecOpsConfig()
    }
    
    @classmethod
    def register_agent(cls, role: AgentRole, agent_class: Type[BaseAgent]) -> None:
        """
        Register an agent class for a role
        
        Args:
            role: Agent role
            agent_class: Agent class to register
            
        Example:
            >>> AgentFactory.register_agent(
            ...     AgentRole.DEVELOPER,
            ...     DeveloperAgent
            ... )
        """
        cls._agent_registry[role] = agent_class
        logger.info(f"Registered agent class {agent_class.__name__} for role {role}")
    
    @classmethod
    def create_agent(
        cls,
        role: AgentRole,
        llm: BaseChatModel,
        memory: AgentMemory,
        config: Optional[AgentConfig] = None,
        **kwargs
    ) -> BaseAgent:
        """
        Create an agent instance
        
        Args:
            role: Agent role to create
            llm: LangChain chat model instance
            memory: Agent memory instance
            config: Optional agent configuration (uses default if not provided)
            **kwargs: Additional keyword arguments passed to agent constructor
            
        Returns:
            Instantiated agent
            
        Raises:
            AgentConfigurationError: If agent class not registered or creation fails
            
        Example:
            >>> from agents.llm import get_openrouter_llm
            >>> from services.memory import get_agent_memory
            >>> 
            >>> llm = get_openrouter_llm()
            >>> memory = get_agent_memory()
            >>> 
            >>> agent = AgentFactory.create_agent(
            ...     role=AgentRole.DEVELOPER,
            ...     llm=llm,
            ...     memory=memory
            ... )
        """
        # Check if agent class is registered
        if role not in cls._agent_registry:
            raise AgentConfigurationError(
                f"No agent class registered for role: {role}. "
                f"Available roles: {list(cls._agent_registry.keys())}"
            )
        
        # Get agent class
        agent_class = cls._agent_registry[role]
        
        # Use provided config or default
        if config is None:
            config = cls._default_configs.get(role)
        
        # Validate config matches role
        if config and config.role != role:
            raise AgentConfigurationError(
                f"Configuration role {config.role} does not match requested role {role}"
            )
        
        # Check if agent is enabled
        if config and not config.enabled:
            raise AgentConfigurationError(f"Agent role {role} is disabled in configuration")
        
        try:
            # Create agent instance
            agent = agent_class(
                llm=llm,
                memory=memory,
                config=config,
                **kwargs
            )
            
            logger.info(f"Created {role} agent: {agent}")
            
            return agent
            
        except Exception as e:
            error_msg = f"Failed to create agent for role {role}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise AgentConfigurationError(error_msg) from e
    
    @classmethod
    def create_all_agents(
        cls,
        llm: BaseChatModel,
        memory: AgentMemory,
        configs: Optional[Dict[AgentRole, AgentConfig]] = None,
        include_optional: bool = False
    ) -> Dict[AgentRole, BaseAgent]:
        """
        Create all registered agents
        
        Args:
            llm: LangChain chat model instance
            memory: Agent memory instance
            configs: Optional dictionary of configurations by role
            include_optional: Whether to include optional agents (e.g., Documentation)
            
        Returns:
            Dictionary mapping roles to agent instances
            
        Raises:
            AgentConfigurationError: If agent creation fails
            
        Example:
            >>> agents = AgentFactory.create_all_agents(
            ...     llm=llm,
            ...     memory=memory,
            ...     include_optional=True
            ... )
            >>> pm_agent = agents[AgentRole.PROJECT_MANAGER]
        """
        agents = {}
        
        # Determine which roles to create
        roles_to_create = [
            AgentRole.PROJECT_MANAGER,
            AgentRole.DEVELOPER,
            AgentRole.QA
        ]
        
        if include_optional:
            roles_to_create.append(AgentRole.DOCUMENTATION)
            roles_to_create.append(AgentRole.INFRA_ARCHITECT)
            roles_to_create.append(AgentRole.DEVOPS)
            roles_to_create.append(AgentRole.SECOPS)
        
        # Create each agent
        for role in roles_to_create:
            if role not in cls._agent_registry:
                logger.warning(f"Agent class not registered for role {role}, skipping")
                continue
            
            try:
                config = configs.get(role) if configs else None
                agent = cls.create_agent(
                    role=role,
                    llm=llm,
                    memory=memory,
                    config=config
                )
                agents[role] = agent
                
            except AgentConfigurationError as e:
                logger.error(f"Failed to create {role} agent: {e}")
                # Continue creating other agents
                continue
        
        logger.info(f"Created {len(agents)} agents: {list(agents.keys())}")
        
        return agents
    
    @classmethod
    def get_default_config(cls, role: AgentRole) -> AgentConfig:
        """
        Get default configuration for a role
        
        Args:
            role: Agent role
            
        Returns:
            Default configuration for the role
            
        Raises:
            AgentConfigurationError: If no default config exists for role
        """
        if role not in cls._default_configs:
            raise AgentConfigurationError(f"No default configuration for role: {role}")
        
        return cls._default_configs[role]
    
    @classmethod
    def set_default_config(cls, role: AgentRole, config: AgentConfig) -> None:
        """
        Set default configuration for a role
        
        Args:
            role: Agent role
            config: Configuration to set as default
            
        Raises:
            AgentConfigurationError: If config role doesn't match
        """
        if config.role != role:
            raise AgentConfigurationError(
                f"Configuration role {config.role} does not match {role}"
            )
        
        cls._default_configs[role] = config
        logger.info(f"Updated default configuration for role {role}")
    
    @classmethod
    def list_registered_agents(cls) -> list[AgentRole]:
        """
        List all registered agent roles
        
        Returns:
            List of registered agent roles
        """
        return list(cls._agent_registry.keys())
    
    @classmethod
    def is_registered(cls, role: AgentRole) -> bool:
        """
        Check if an agent role is registered
        
        Args:
            role: Agent role to check
            
        Returns:
            True if registered, False otherwise
        """
        return role in cls._agent_registry


