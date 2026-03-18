from typing import List, Optional
from pydantic import BaseModel, Field


class FeatureSpec(BaseModel):
    """Feature specification"""
    name: str = Field(description="Feature name")
    description: str = Field(description="Feature description")
    priority: str = Field(description="Priority level: high, medium, low")


class ProjectPlan(BaseModel):
    """Project planning output"""
    goals: List[str] = Field(description="Project goals")
    features: List[FeatureSpec] = Field(description="Features to implement")
    technical_approach: str = Field(description="Technical approach summary")
    complexity: str = Field(description="Project complexity: low, medium, high")
    challenges: Optional[List[str]] = Field(default=None, description="Potential challenges")


class TaskSpec(BaseModel):
    """Task specification"""
    description: str = Field(description="Task description")
    agent_role: str = Field(description="Agent role: developer, qa, documentation")
    priority: int = Field(description="Priority (1=highest)", ge=1, le=10)
    requirements: Optional[str] = Field(default=None, description="Task requirements")
    dependencies: Optional[List[int]] = Field(default=None, description="Task dependencies (indices)")


class TaskBreakdown(BaseModel):
    """Task breakdown output"""
    tasks: List[TaskSpec] = Field(description="Generated tasks")
    summary: Optional[str] = Field(default=None, description="Breakdown summary")


class FeedbackImpactAnalysis(BaseModel):
    """Analysis of user feedback impact on plan components"""
    needs_new_technical_approach: bool = Field(default=False, description="Whether technical approach needs updating")
    needs_new_features: bool = Field(default=False, description="Whether features need updating")
    needs_new_goals: bool = Field(default=False, description="Whether goals need updating")
    needs_new_challenges: bool = Field(default=False, description="Whether challenges need updating")
