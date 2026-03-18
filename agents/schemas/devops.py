from typing import Dict, Optional
from pydantic import BaseModel, Field

class TerraformCodebase(BaseModel):
    """
    Structured output for Terraform code generation.
    """
    main_tf: str = Field(..., description="The main terraform configuration file.")
    variables_tf: str = Field(..., description="Variable definitions.")
    provider_tf: str = Field(..., description="Provider configuration.")
    outputs_tf: Optional[str] = Field(None, description="Output values.")
    
    # Optional field for flexible file structure if LLM wants to split more
    extra_files: Optional[Dict[str, str]] = Field(
        default_factory=dict, 
        description="Any additional .tf files needed (e.g. backend.tf)"
    )
