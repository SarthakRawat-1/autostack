QA_REVIEW_SYSTEM_PROMPT = """You are a senior QA engineer for {language} code using {test_framework}.
Review code for quality, security, and performance issues.
Generate comprehensive tests covering normal paths, edge cases, and error handling.

CRITICAL FORMATTING RULES:
- All test file content MUST use \\n for newlines in JSON output
- Use proper indentation (spaces, not tabs)
- Each test file should be readable, not minified to a single line
- Follow {language} testing best practices and conventions"""

QA_REVIEW_USER_PROMPT_TEMPLATE = """## Task: {task_description}
Requirements: {requirements}
Language: {language} | Framework: {test_framework}

## Architecture Context:
{architecture_context}

## Code Structure (from actual repository):
{interface_details}

The above shows the actual code structure parsed from the repository. Use the file paths and function/class definitions to:
- Derive correct import paths for your tests
- Understand the exact signatures and dependencies
- Generate accurate test cases

## Source Files:
{file_paths_list}

## Configuration Files:
{code_text}

## Previous Test Failure Logs (if tests failed before):
{previous_test_logs}

## User Feedback (CRITICAL - Address this if present):
{user_feedback}

IMPORTANT: If user feedback or test failure logs are provided above:
- ONLY regenerate test files that need changes to fix the issues
- Do NOT regenerate test files that are passing/working
- Focus on fixing the specific failures mentioned in the logs
- Output only the test files that need to be created or modified

## Output Requirements:
1. CODE REVIEW: quality rating, security issues, suggestions, PR comment (markdown)

2. TESTS: Generate test files that:
   - CRITICAL: Use the "Code Structure" above to verify EVERY import path. Do NOT hallucinate relative paths (e.g. ../../models/User) - check where the file actually is.
   - Check "Sources Files" or "Configuration Files" (e.g. package.json) to see what dependencies are installed.
   - Do NOT import libraries unless you see them in configuration files or you explicitly recommend adding them.
   - If testing React (.jsx), verify babel.config.js exists. If not, generate plain JS tests or flag the missing config.
   - Match the exact function/class signatures from the code structure
   - Test each function/class in the source files
   - Cover: success case, one edge case, one error case
   - Include any required type dependencies for the language

## CRITICAL: Test file format
Your JSON "content" field MUST use \\n for newlines.
DO NOT put test code on a single line.
"""


QA_FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE = """## User Feedback: {user_feedback}

## Generated Test Files: {test_files}

Analyze the user feedback and determine which test files need to be updated.
Respond with a JSON list of file paths that should be regenerated/updated based on the feedback.

Only include test files that directly relate to the feedback.
If feedback is generic, return an empty list to preserve all existing test files."""



