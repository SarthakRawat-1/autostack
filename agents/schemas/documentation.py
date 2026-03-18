from typing import List, Optional
from pydantic import BaseModel, Field


class DocumentationFile(BaseModel):
    """Generated documentation file"""
    file_path: str = Field(description="Documentation file path (e.g., README.md)")
    content: str = Field(description="File content in markdown")
    description: Optional[str] = Field(default=None, description="File description")


class DocumentationOutput(BaseModel):
    """Documentation generation output"""
    summary: str = Field(description="Documentation summary")
    files: List[DocumentationFile] = Field(description="Generated documentation files")
