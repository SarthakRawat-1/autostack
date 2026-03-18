from typing import List, Optional
from pydantic import BaseModel, Field


class CodeIssue(BaseModel):
    """Code quality issue"""
    file_path: str = Field(description="File path with issue")
    line_number: Optional[int] = Field(default=None, description="Line number")
    severity: str = Field(description="Severity: critical, high, medium, low")
    issue_type: str = Field(description="Issue type: bug, style, performance, etc.")
    description: str = Field(description="Issue description")
    suggestion: Optional[str] = Field(default=None, description="Fix suggestion")


class SecurityIssue(BaseModel):
    """Security vulnerability"""
    file_path: str = Field(description="File path with vulnerability")
    severity: str = Field(description="Severity: critical, high, medium, low")
    vulnerability_type: str = Field(description="Type of vulnerability")
    description: str = Field(description="Vulnerability description")
    remediation: str = Field(description="Remediation steps")


class CodeReview(BaseModel):
    """Code review output"""
    summary: str = Field(description="Review summary")
    issues: List[CodeIssue] = Field(default=[], description="Code issues found")
    security_issues: List[SecurityIssue] = Field(default=[], description="Security issues")
    recommendations: Optional[List[str]] = Field(default=None, description="Recommendations")
    approved: bool = Field(default=True, description="Whether code is approved")


class TestCase(BaseModel):
    """Generated test case"""
    name: str = Field(description="Test name")
    description: str = Field(description="Test description")
    test_type: str = Field(description="Type: unit, integration, e2e")


class TestFile(BaseModel):
    """Generated test file"""
    file_path: str = Field(description="Test file path")
    content: str = Field(description="Test file content")
    test_cases: List[TestCase] = Field(description="Test cases in this file")


class TestGeneration(BaseModel):
    """Test generation output"""
    files: List[TestFile] = Field(description="Generated test files")
    summary: str = Field(description="Test generation summary")
    coverage_estimate: Optional[float] = Field(default=None, description="Estimated coverage %")


# Schema for combined review and test generation (used by review_and_generate_tests)
class ReviewOutput(BaseModel):
    """Code review output for PR"""
    overall_quality: str = Field(description="Quality: excellent, good, fair, poor")
    security_issues: Optional[List[str]] = Field(default=[], description="Security concerns")
    code_smells: Optional[List[str]] = Field(default=[], description="Code smells found")
    performance_issues: Optional[List[str]] = Field(default=[], description="Performance issues")
    suggestions: Optional[List[str]] = Field(default=[], description="Improvement suggestions")
    feedback_comment: str = Field(description="Markdown-formatted PR comment")


class GeneratedTestFile(BaseModel):
    """Single test file output"""
    file_path: str = Field(description="Test file path (e.g., tests/test_auth.py)")
    content: str = Field(description="Complete test file content with proper formatting. MUST include newlines (\\n) and indentation. NOT minified.")


class ReviewAndTestsOutput(BaseModel):
    """Combined review and test generation output"""
    review: ReviewOutput = Field(description="Code review results")
    tests: List[GeneratedTestFile] = Field(description="Generated test files")
