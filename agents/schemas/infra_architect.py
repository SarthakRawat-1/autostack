from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AzureResource(BaseModel):
    """A single Azure resource in the plan."""
    name: str = Field(description="Resource name (e.g. my-app-rg)")
    type: str = Field(description="Azure resource type (e.g. azurerm_resource_group)")
    tier: Optional[str] = Field(default=None, description="SKU / pricing tier")
    region: Optional[str] = Field(default=None, description="Azure region")
    properties: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Additional resource properties",
    )


class ResourcePlan(BaseModel):
    """Structured Infrastructure Resource Plan produced by InfraArchitectAgent."""
    summary: str = Field(description="High-level summary of the plan")
    intent: str = Field(
        description="Classified intent: 'provision', 'deploy', or 'provision_and_deploy'"
    )
    resources: List[AzureResource] = Field(
        description="List of Azure resources to create"
    )
    networking: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Networking configuration notes (VNet, subnets, NSGs)",
    )
    estimated_monthly_cost: Optional[str] = Field(
        default=None,
        description="Rough monthly cost estimate",
    )
    notes: Optional[List[str]] = Field(
        default_factory=list,
        description="Additional recommendations or caveats",
    )
