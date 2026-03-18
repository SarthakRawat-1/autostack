"""
RepoMap Service - Main entry point for repository mapping.

Provides a high-level interface for generating repository maps
from remote GitHub repositories by cloning them temporarily.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Set, List

from services.repomap.mapper import RepoMapper


class RepoMapService:
    """
    High-level service for generating repository maps from remote GitHub repos.
    
    Clones repositories to a temporary directory for analysis,
    then cleans up after generating the map.
    """
    
    def __init__(
        self,
        max_tokens: int = 8192,
        model: str = "gpt-4",
        verbose: bool = False
    ):
        """
        Initialize the RepoMap service.
        
        Args:
            max_tokens: Maximum tokens for generated maps.
            model: Model for token counting.
            verbose: Enable verbose output.
        """
        self.max_tokens = max_tokens
        self.model = model
        self.verbose = verbose
        self._temp_dirs: List[str] = []
    
    async def get_repo_map(
        self,
        repo_url: str,
        branch: str = "main",
        priority_files: Optional[List[str]] = None,
        mentioned_files: Optional[Set[str]] = None,
        mentioned_idents: Optional[Set[str]] = None
    ) -> str:
        """
        Generate a repository map from a remote GitHub repository.
        
        Args:
            repo_url: GitHub repository URL (e.g., https://github.com/owner/repo).
            branch: Branch to analyze (default: main).
            priority_files: Files to prioritize in the map.
            mentioned_files: Files mentioned by user.
            mentioned_idents: Identifiers mentioned by user.
            
        Returns:
            Formatted repository map string.
            
        Raises:
            RuntimeError: If cloning fails.
        """
        # Clone the repository
        repo_path = await self._clone_repo(repo_url, branch)
        
        try:
            # Create mapper and generate map
            mapper = RepoMapper(
                root=repo_path,
                max_tokens=self.max_tokens,
                model=self.model,
                verbose=self.verbose
            )
            
            repo_map = mapper.get_repo_map(
                priority_files=priority_files,
                mentioned_files=mentioned_files,
                mentioned_idents=mentioned_idents
            )
            
            return repo_map
            
        finally:
            # Always cleanup since we always clone
            self._cleanup_temp(repo_path)
    
    async def get_repo_map_for_branch(
        self,
        repo_url: str,
        branch: str,
        priority_files: Optional[List[str]] = None
    ) -> str:
        """
        Convenience method to get map for a specific branch.
        
        Args:
            repo_url: GitHub repository URL.
            branch: Branch to analyze.
            priority_files: Files to prioritize.
            
        Returns:
            Repository map string.
        """
        return await self.get_repo_map(
            repo_url=repo_url,
            branch=branch,
            priority_files=priority_files
        )
    
    async def get_repo_map_via_api(
        self,
        github_client,  # GitHubClient instance
        repository: str,  # owner/repo format
        branch: str,
        priority_files: Optional[List[str]] = None,
        max_files: int = 100
    ) -> str:
        """
        Generate a repository map using GitHub API (works with private repos).
        
        Instead of cloning, fetches files via authenticated GitHub API.
        
        Args:
            github_client: Authenticated GitHubClient instance.
            repository: Repository in owner/repo format.
            branch: Branch to analyze.
            priority_files: Files to prioritize.
            max_files: Maximum number of source files to fetch.
            
        Returns:
            Formatted repository map string.
        """
        try:
            # Get list of all files in repo
            all_files = await github_client.list_repository_files(
                repo=repository,
                ref=branch
            )
            
            # Filter to source code files
            code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rb', '.php', '.cs', '.cpp', '.c', '.h'}
            source_files = [
                f for f in all_files 
                if any(f.endswith(ext) for ext in code_extensions)
                and not any(excl in f for excl in ['.git', 'node_modules', '__pycache__', '.min.js', 'dist/', 'build/'])
            ]
            
            # Prioritize files if specified
            if priority_files:
                # Put priority files first
                priority_set = set(priority_files)
                source_files = sorted(source_files, key=lambda f: (f not in priority_set, f))
            
            # Limit number of files to fetch
            files_to_fetch = source_files[:max_files]
            
            # Fetch file contents via GitHub API
            temp_dir = tempfile.mkdtemp(prefix="autostack_repomap_api_")
            self._temp_dirs.append(temp_dir)
            
            try:
                # Create directory structure and write files
                for file_path in files_to_fetch:
                    try:
                        content = await github_client.get_file_content(
                            repo=repository,
                            path=file_path,
                            ref=branch
                        )
                        
                        # Create file in temp directory
                        full_path = os.path.join(temp_dir, file_path)
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    except Exception:
                        continue  # Skip files that fail to fetch
                
                # Use RepoMapper to analyze the fetched files
                mapper = RepoMapper(
                    root=temp_dir,
                    max_tokens=self.max_tokens,
                    model=self.model,
                    verbose=self.verbose
                )
                
                repo_map = mapper.get_repo_map(
                    priority_files=priority_files
                )
                
                return repo_map
                
            finally:
                # Cleanup temp directory
                self._cleanup_temp(temp_dir)
                
        except Exception as e:
            if self.verbose:
                print(f"Failed to generate repo map via API: {e}")
            return ""
    
    async def _clone_repo(self, repo_url: str, branch: str) -> str:
        """
        Clone a repository to a temporary directory.
        
        Uses shallow clone (--depth 1) for efficiency.
        
        Args:
            repo_url: GitHub repository URL.
            branch: Branch to clone.
            
        Returns:
            Path to the cloned repository.
            
        Raises:
            RuntimeError: If clone fails.
        """
        import subprocess
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="autostack_repomap_")
        self._temp_dirs.append(temp_dir)
        
        if self.verbose:
            print(f"Cloning {repo_url} (branch: {branch}) to {temp_dir}")
        
        # Build git clone command
        cmd = [
            "git", "clone",
            "--depth", "1",
            "--branch", branch,
            "--single-branch",
            repo_url,
            temp_dir
        ]
        
        try:
            # Run git clone
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"Git clone failed: {error_msg}")
            
            return temp_dir
            
        except FileNotFoundError:
            raise RuntimeError("Git is not installed or not in PATH")
        except Exception as e:
            # Cleanup on error
            self._cleanup_temp(temp_dir)
            raise RuntimeError(f"Failed to clone repository: {e}")
    
    def _cleanup_temp(self, path: str) -> None:
        """
        Remove a temporary directory.
        
        Args:
            path: Path to the directory to remove.
        """
        try:
            if path in self._temp_dirs:
                self._temp_dirs.remove(path)
            if os.path.exists(path):
                shutil.rmtree(path)
        except Exception as e:
            if self.verbose:
                print(f"Warning: Failed to cleanup temp directory: {e}")
    
    def cleanup_all(self) -> None:
        """Remove all temporary directories created by this service."""
        for temp_dir in list(self._temp_dirs):
            self._cleanup_temp(temp_dir)
    
    def __del__(self):
        """Cleanup on garbage collection."""
        self.cleanup_all()


# Singleton instance
_repomap_service: Optional[RepoMapService] = None


def get_repomap_service(
    max_tokens: int = 8192,
    verbose: bool = False
) -> RepoMapService:
    """
    Get the singleton RepoMap service instance.
    
    Args:
        max_tokens: Maximum tokens for generated maps.
        verbose: Enable verbose output.
        
    Returns:
        RepoMapService instance.
    """
    global _repomap_service
    
    if _repomap_service is None:
        _repomap_service = RepoMapService(
            max_tokens=max_tokens,
            verbose=verbose
        )
    
    return _repomap_service
