from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ModuleDefinition(BaseModel):
    """Definition of a code module"""
    description: str = Field(description="Module description")
    files: List[str] = Field(description="Files in this module")
    responsibilities: List[str] = Field(description="Module responsibilities")


class InterfaceContracts(BaseModel):
    """Interface contracts and signatures"""
    function_names: Optional[List[str]] = Field(default=None, description="Function signatures")
    class_interfaces: Optional[List[str]] = Field(default=None, description="Class interface definitions")


class TechStack(BaseModel):
    """Technology stack specification"""
    frameworks: Optional[List[str]] = Field(default=None, description="Frameworks to use")
    libraries: Optional[List[str]] = Field(default=None, description="Libraries to use")
    databases: Optional[List[str]] = Field(default=None, description="Databases to use")
    tools: Optional[List[str]] = Field(default=None, description="Development tools")


class CodingStandards(BaseModel):
    """Coding standards and conventions"""
    naming_conventions: Optional[str] = Field(default=None, description="Naming convention rules")
    error_handling: Optional[str] = Field(default=None, description="Error handling approach")
    file_organization: Optional[str] = Field(default=None, description="File organization rules")


class DataFlow(BaseModel):
    """Data flow architecture"""
    entry_points: Optional[List[str]] = Field(default=None, description="Entry points")
    data_processing: Optional[List[str]] = Field(default=None, description="Data processing steps")
    dependencies: Optional[Dict[str, List[str]]] = Field(default=None, description="Module dependencies")


class TestingStrategy(BaseModel):
    """Testing strategy specification"""
    unit_test_types: Optional[List[str]] = Field(default=None, description="Unit test categories")
    integration_test_types: Optional[List[str]] = Field(default=None, description="Integration test categories")
    testing_tools: Optional[List[str]] = Field(default=None, description="Testing tools to use")


class ArchitecturePlan(BaseModel):
    """Complete architecture plan for a project"""
    directory_structure: List[str] = Field(description="Recommended directory structure")
    modules: Dict[str, ModuleDefinition] = Field(description="Module definitions")
    interface_contracts: InterfaceContracts = Field(description="Interface contracts")
    tech_stack: TechStack = Field(description="Technology stack")
    coding_standards: Optional[CodingStandards] = Field(default=None)
    data_flow: Optional[DataFlow] = Field(default=None)
    testing_strategy: Optional[TestingStrategy] = Field(default=None)


class FileOutput(BaseModel):
    """Generated file output"""
    path: str = Field(description="Relative file path")
    content: str = Field(description="File content with proper formatting. MUST include newlines (\\n) and indentation. NOT minified.")
    description: Optional[str] = Field(default=None, description="Brief description")


class InterfaceContract(BaseModel):
    """Interface contract definition"""
    name: str = Field(description="Name of function, class, or API endpoint")
    signature: str = Field(description="Full signature including parameters and return type")
    inputs: List[str] = Field(description="Descriptions of expected input parameters")
    outputs: List[str] = Field(description="Descriptions of expected outputs")
    purpose: str = Field(description="Brief purpose of this interface")
    file_path: str = Field(description="File path where this interface is defined (e.g., 'src/auth.py')")
    dependencies: Optional[List[str]] = Field(default=None, description="Other interfaces this depends on")
    usages: Optional[List[str]] = Field(default=None, description="How other parts should use this")


class FeatureGeneration(BaseModel):
    """Feature code generation output"""
    files: List[FileOutput] = Field(description="Generated files")
    interface_contracts: Optional[List[InterfaceContract]] = Field(default=None, description="Interface contracts defined")
    summary: Optional[str] = Field(default=None, description="Generation summary")
