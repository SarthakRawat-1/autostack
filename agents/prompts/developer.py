ARCHITECTURE_SYSTEM_PROMPT = """You are a senior software architect planning a complete software project architecture.
Your role is to create a comprehensive architecture plan that will guide development.

Focus on:
- Clear directory structure and file organization
- Module breakdown with specific responsibilities
- Interface contracts between components
- Technology stack recommendations
- Coding standards and patterns to follow
- Data flow and dependencies between modules
"""

ARCHITECTURE_USER_PROMPT_TEMPLATE = """Create a comprehensive architecture plan for this software project:

Project Requirements:
{requirements}

Generate a detailed architecture plan that includes:

1. Directory structure (recommended folder layout)
2. Module breakdown (what each major module does)
3. Interface contracts (function signatures, class interfaces, API endpoints)
4. Technology stack (frameworks, libraries, databases, tools)
5. Coding standards (naming conventions, error handling patterns, file organization)
6. Data flow (how data moves between components)
7. Dependencies (what each module depends on)
8. Testing strategy (how to test each component)

Respond with structured JSON matching the provided schema.
"""

FEATURE_GENERATION_SYSTEM_PROMPT = """You are a senior developer implementing features. Write clean, well-structured code with proper formatting.

CRITICAL FORMATTING RULES:
- Use proper newlines between statements (\\n in JSON strings)
- Use proper indentation (2 or 4 spaces per level)
- Each file must be properly formatted, NOT on a single line
- In JSON output, represent newlines as \\n escape sequences

QUALITY RULES:
- No duplicate imports within or across files
- Each file should have a single, clear responsibility
- Use consistent naming conventions
- Include proper error handling"""

FEATURE_GENERATION_SYSTEM_ADDENDUM = """You are a senior developer. Generate 2-5 complete, production-ready files.

CRITICAL: Your JSON response MUST have properly formatted code:
- Use \\n for newlines in the "content" field strings
- Use proper indentation (spaces, not tabs)
- Each code file should be readable, not minified

Rules:
- No comments or docstrings in code
- Write functional, working code (not stubs or placeholders)
- Basic error handling where critical
- NO duplicate imports or functions
- Each file has ONE clear purpose
- Include interface_contracts for public functions/classes"""

FEATURE_GENERATION_USER_PROMPT_TEMPLATE = """## Task: {task_description}

## Architecture Summary:
{architecture_context}

## Existing Interfaces (must be compatible):
{previous_context}

## Researched Versions and Configuration Context:
{research_context}

## Current Codebase (from repository - use for refinement):
{current_codebase}

## User Feedback (CRITICAL - Address this if present):
{user_feedback}

IMPORTANT: If user feedback is provided above:
- ONLY regenerate files that need changes based on the feedback
- Do NOT regenerate files that don't need modifications
- Check "Current Codebase" to see what already exists
- Output only the files that need to be created or modified

## Requirements:
1. Generate 2-{batch_size} cohesive files implementing the complete feature
2. CRITICAL: Use the EXACT language specified in the task description (JavaScript vs TypeScript, Python vs Java, etc.)
3. Include ALL necessary configuration files for the project based on language and framework
4. CRITICAL: Use versions from research context above, but convert to SAFE major version ranges:
   - If research says "6.12.3", use "^6.0.0" (not "^6.12.3")
   - If research says "4.18.2", use "^4.0.0" (not "^4.18.2")
   - This applies to ALL dependency files (package.json, requirements.txt, go.mod, Cargo.toml, pom.xml, etc.)
5. Ensure configuration files are properly set up for testing framework compatibility
6. Include test framework as dev dependency in appropriate config files

## CRITICAL OUTPUT FORMAT:
Your JSON "content" field MUST use \\n for newlines. Example:
{{"files": [{{"path": "app.js", "content": "const express = require('express');\\nconst app = express();\\n\\napp.get('/', (req, res) => {{\\n  res.send('Hello');\\n}});\\n\\nmodule.exports = app;"}}]}}

DO NOT output code on a single line. Each statement must be on its own line with proper indentation.

## Code Quality Rules:
- Write concise but functional and working implementations (not minimal placeholder code and not unecessary complexity)
- Avoid verbose implementations
- NO duplicate imports (even across files in the batch)
- Each file should have ONE cohesive purpose with complete functionality
- Basic error handling when critical
- Generate appropriate configuration files to ensure compatibility (e.g., ES modules for JS/TS, proper test runners)
- Follow language-specific conventions and best practices

## Configuration Requirements:
- For JavaScript/TypeScript:
  * Use modern ES module syntax (import/export)
  * MUST include babel.config.js with: module.exports = {{ presets: ['@babel/preset-env'] }}
  * MUST include jest.config.js with: module.exports = {{ transform: {{"^.+\\\\.[jt]sx?$": "babel-jest"}} }}
  * CRITICAL: Do NOT reference setupFilesAfterEnv in jest.config.js unless you also generate the setup file
  * package.json devDependencies MUST include: @babel/preset-env, babel-jest, jest, supertest
- For Python: If needed, requirements.txt or pyproject.toml with dependencies
- For Java: If needed, pom.xml or build.gradle with proper test configurations
- For other languages: If needed, include appropriate project configuration files
- Check 'Existing Interfaces' section to see what configuration files already exist - do not duplicate if they already exist

Respond with JSON: {{"files": [{{"path": "...", "content": "..."}}], "interface_contracts": [{{"name": "...", "signature": "...", "inputs": [...], "outputs": [...], "purpose": "...", "file_path": "path/to/file.ext"}}]}}

IMPORTANT: For each interface_contract, include "file_path" indicating which file contains this interface (must match one of the file paths in the "files" array)."""


FEEDBACK_ANALYSIS_SYSTEM_PROMPT = """Analyze user feedback to determine which files need updating."""


FEEDBACK_ANALYSIS_USER_PROMPT_TEMPLATE = """User feedback: "{user_feedback}"

Generated files: {generated_files}

Analyze the user feedback and determine which files need to be updated.
Respond with a JSON list of file paths that should be regenerated/updated based on the feedback.

Only include files that directly relate to the feedback.
If feedback is generic, return an empty list to preserve all existing files."""

