"""
Important file detection for RepoMap.

Identifies configuration files, documentation, and other important files
that should be prioritized in the repository map.
"""

import os
from pathlib import Path
from typing import List, Set

# Files that are always considered important
IMPORTANT_FILENAMES: Set[str] = {
    # Documentation
    "README.md", "README.txt", "readme.md", "README.rst", "README",
    "CHANGELOG.md", "CHANGELOG.txt", "HISTORY.md",
    "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
    
    # Python
    "requirements.txt", "Pipfile", "pyproject.toml", "setup.py", "setup.cfg",
    "tox.ini", "pytest.ini", ".pytest.ini",
    ".flake8", ".pylintrc", "mypy.ini",
    
    # JavaScript/Node
    "package.json", "yarn.lock", "package-lock.json", "pnpm-lock.yaml",
    "tsconfig.json", "jsconfig.json",
    
    # Docker
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".dockerignore",
    
    # Git
    ".gitignore", ".gitattributes",
    
    # Build
    "Makefile", "makefile", "CMakeLists.txt",
    
    # License
    "LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING",
    
    # Environment
    ".env", ".env.example", ".env.local",
    
    # Go
    "go.mod", "go.sum",
    
    # Rust
    "Cargo.toml", "Cargo.lock",
    
    # Java
    "pom.xml", "build.gradle", "build.gradle.kts",
    
    # PHP
    "composer.json", "composer.lock",
    
    # Ruby
    "Gemfile", "Gemfile.lock",
}

# Directory patterns with file type filters
IMPORTANT_DIR_PATTERNS = {
    ".github/workflows": lambda fname: fname.endswith((".yml", ".yaml")),
    ".github": lambda fname: fname.endswith((".md", ".yml", ".yaml")),
    "docs": lambda fname: fname.endswith((".md", ".rst", ".txt")),
}


def is_important(rel_file_path: str) -> bool:
    """
    Check if a file is considered important for repository understanding.
    
    Args:
        rel_file_path: Relative path to the file from repository root.
        
    Returns:
        True if the file is important, False otherwise.
    """
    normalized_path = os.path.normpath(rel_file_path)
    file_name = os.path.basename(normalized_path)
    dir_name = os.path.dirname(normalized_path)

    # Check specific directory patterns
    for important_dir, checker_func in IMPORTANT_DIR_PATTERNS.items():
        normalized_important_dir = os.path.normpath(important_dir)
        if dir_name == normalized_important_dir and checker_func(file_name):
            return True
    
    # Check if the full normalized path is important
    if normalized_path in IMPORTANT_FILENAMES:
        return True
    
    # Check if just the basename is important
    if file_name in IMPORTANT_FILENAMES:
        return True
        
    return False


def filter_important_files(file_paths: List[str]) -> List[str]:
    """
    Filter a list of file paths to only include important files.
    
    Args:
        file_paths: List of relative file paths.
        
    Returns:
        List of paths that are considered important.
    """
    return [path for path in file_paths if is_important(path)]


def get_file_priority(rel_file_path: str) -> int:
    """
    Get priority score for a file (higher = more important).
    
    Args:
        rel_file_path: Relative path to the file.
        
    Returns:
        Priority score (0-100).
    """
    file_name = os.path.basename(rel_file_path)
    
    # README gets highest priority
    if file_name.lower().startswith("readme"):
        return 100
    
    # Package manifests
    if file_name in {"package.json", "pyproject.toml", "Cargo.toml", "go.mod"}:
        return 90
    
    # Entry points
    if file_name in {"main.py", "app.py", "index.js", "index.ts", "main.go"}:
        return 85
    
    # Config files
    if file_name.endswith((".json", ".yaml", ".yml", ".toml")) and is_important(rel_file_path):
        return 70
    
    # Other important files
    if is_important(rel_file_path):
        return 60
    
    return 0
