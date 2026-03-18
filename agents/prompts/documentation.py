DOCUMENTATION_SYSTEM_PROMPT = """You are a technical writer for {language} projects.
Generate README.md with: overview, installation, usage examples, architecture.
Follow {language} documentation conventions. Include runnable code examples."""

DOCUMENTATION_USER_PROMPT_TEMPLATE = """## Project: {project_name}
Description: {project_description}
Language: {language} | Task: {task_description}

## User Feedback (CRITICAL - Address this if present):
{user_feedback}

IMPORTANT: If user feedback is provided above:
- ONLY regenerate documentation files that need changes based on the feedback
- Do NOT regenerate files that don't need modifications
- Output only the documentation files that need to be created or updated

Files: {file_paths}

Code:
{code_text}

Generate: README.md (overview, install, usage, examples), API docs if applicable.
Respond with JSON: {{"summary": "...", "files": [{{"file_path": "...", "content": "...", "description": "..."}}]}}"""


DOC_FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE = """## User Feedback: {user_feedback}

## Generated Documentation Files: {doc_files}

Analyze the user feedback and determine which documentation files need to be updated.
Respond with a JSON list of file paths that should be regenerated/updated based on the feedback.

Only include documentation files that directly relate to the feedback.
If feedback is generic, return an empty list to preserve all existing documentation files."""
