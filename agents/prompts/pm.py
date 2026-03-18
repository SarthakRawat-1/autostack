PROJECT_ANALYSIS_SYSTEM_PROMPT = """You are a senior PM analyzing project requirements.
Break down requirements into features, assess complexity, identify technical approach and challenges."""

PROJECT_ANALYSIS_USER_PROMPT_TEMPLATE = """## Project: {project_name}

{project_description}

## Existing Codebase (IMPORTANT - Plan changes to this if provided):
{current_codebase}

## User Feedback (CRITICAL - Address this if present):
{user_feedback}

## Previous Plan (Refine this based on feedback, if present):
{previous_plan}

IMPORTANT: If "Existing Codebase" is provided above, you are MODIFYING an existing project.
- Analyze the current structure before planning
- Plan targeted changes, not a complete rewrite
- Identify which existing files need modification and what new files need creation

Create plan with: goals, features (with priorities), technical approach, complexity (low/medium/high), challenges.
Respond with JSON matching the schema."""


PROJECT_ANALYSIS_WITH_FEEDBACK_USER_PROMPT_TEMPLATE = """## Project: {project_name}

{project_description}

## Previous Plan:
{previous_plan}

## Current Codebase:
{current_codebase}

## User Feedback (CRITICAL - Address this comprehensively):
{user_feedback}

IMPORTANT: You are revising the entire plan based on user feedback.
- Analyze the feedback carefully and understand what changes are requested
- Create a COMPLETE new plan that addresses all feedback points
- Maintain consistency with the project requirements while incorporating feedback
- Ensure the new plan is comprehensive and complete (not just changes)
- Update goals, features, technical approach, and challenges as needed based on feedback

Create a complete plan with: goals, features (with priorities), technical approach, complexity (low/medium/high), challenges.
Respond with complete JSON matching the schema."""

TASK_BREAKDOWN_SYSTEM_PROMPT = """Break down project into tasks for developer, qa, documentation agents.
Rules: Small tasks, priority 1-10, developer before qa, qa before docs. Include dependencies."""

TASK_BREAKDOWN_USER_PROMPT_TEMPLATE = """## Project Plan:
{project_plan}

Requirements: {requirements}

Create {min_tasks}-{max_tasks} tasks with: description, agent_role (developer/qa/documentation), priority (1-10), requirements, dependencies.
Respond with JSON containing "tasks" array."""

