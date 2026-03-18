"""
Core RepoMap mapper logic.

Generates a token-optimized map of repository structure
highlighting important files and code definitions.
"""

import os
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Callable, Any

from services.repomap.parser import CodeParser, Tag, read_text
from services.repomap.ranker import rank_files, rank_tags
from services.repomap.importance import filter_important_files, is_important


# Token counting using tiktoken
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens in text using tiktoken.
    
    Args:
        text: Text to count tokens for.
        model: Model for tokenization (default: gpt-4).
        
    Returns:
        Token count.
    """
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception:
        # Fallback: estimate ~4 chars per token
        return len(text) // 4


class RepoMapper:
    """
    Core repository mapping class.
    
    Generates a concise, ranked representation of a codebase
    suitable for LLM context.
    """
    
    def __init__(
        self,
        root: str,
        max_tokens: int = 8192,
        model: str = "gpt-4",
        file_reader: Optional[Callable[[str], Optional[str]]] = None,
        verbose: bool = False
    ):
        """
        Initialize the RepoMapper.
        
        Args:
            root: Repository root directory.
            max_tokens: Maximum tokens for the output map.
            model: Model for token counting.
            file_reader: Optional custom file reader function.
            verbose: Enable verbose output.
        """
        self.root = Path(root).resolve()
        self.max_tokens = max_tokens
        self.model = model
        self.file_reader = file_reader or read_text
        self.verbose = verbose
        
        self.parser = CodeParser(file_reader=self.file_reader, verbose=verbose)
        
        # Caches
        self._tags_cache: Dict[str, List[Tag]] = {}
        self._tree_context_cache: Dict[str, Any] = {}
    
    def get_rel_fname(self, fname: str) -> str:
        """Get relative filename from absolute path."""
        try:
            return str(Path(fname).relative_to(self.root))
        except ValueError:
            return fname
    
    def find_source_files(self, directory: Optional[str] = None) -> List[str]:
        """
        Find source files in the repository.
        
        Args:
            directory: Directory to search (default: root).
            
        Returns:
            List of absolute file paths.
        """
        search_dir = Path(directory) if directory else self.root
        
        if not search_dir.is_dir():
            return [str(search_dir)] if search_dir.is_file() else []
        
        # Directories to skip
        skip_dirs = {
            '.git', 'node_modules', '__pycache__', 'venv', 'env',
            '.venv', 'dist', 'build', '.next', '.nuxt', 'coverage',
            '.pytest_cache', '.mypy_cache', 'target', 'vendor'
        }
        
        src_files = []
        for root, dirs, files in os.walk(search_dir):
            # Skip hidden and excluded directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip_dirs]
            
            for file in files:
                if not file.startswith('.'):
                    src_files.append(os.path.join(root, file))
        
        return src_files
    
    def get_tags_for_file(self, fname: str) -> List[Tag]:
        """
        Get cached tags for a file.
        
        Args:
            fname: Absolute file path.
            
        Returns:
            List of tags.
        """
        if fname in self._tags_cache:
            return self._tags_cache[fname]
        
        rel_fname = self.get_rel_fname(fname)
        tags = self.parser.get_tags(fname, rel_fname)
        self._tags_cache[fname] = tags
        
        return tags
    
    def get_repo_map(
        self,
        files: Optional[List[str]] = None,
        priority_files: Optional[List[str]] = None,
        mentioned_files: Optional[Set[str]] = None,
        mentioned_idents: Optional[Set[str]] = None
    ) -> str:
        """
        Generate a repository map.
        
        Args:
            files: Files to include (default: all source files).
            priority_files: Files to prioritize (e.g., currently edited).
            mentioned_files: Files mentioned by user.
            mentioned_idents: Identifiers mentioned by user.
            
        Returns:
            Formatted repository map string.
        """
        # Find files if not specified
        if files is None:
            files = self.find_source_files()
        
        if not files:
            return ""
        
        # Convert to absolute paths
        files = [str(Path(f).resolve()) for f in files if os.path.isfile(f)]
        priority_set = set(str(Path(f).resolve()) for f in (priority_files or []))
        
        # Collect tags for all files
        tags_by_file: Dict[str, List[Tag]] = {}
        for fname in files:
            rel_fname = self.get_rel_fname(fname)
            tags = self.get_tags_for_file(fname)
            if tags:
                tags_by_file[rel_fname] = tags
        
        if not tags_by_file:
            # No parseable code found, return file list
            return self._format_file_list(files)
        
        # Rank files and tags
        rel_priority = {self.get_rel_fname(f) for f in priority_set}
        file_ranks = rank_files(
            tags_by_file,
            priority_files=rel_priority,
            mentioned_files=mentioned_files,
            mentioned_idents=mentioned_idents
        )
        
        ranked_tags = rank_tags(
            tags_by_file,
            file_ranks,
            priority_files=rel_priority,
            mentioned_idents=mentioned_idents
        )
        
        # Format output within token limit
        return self._format_map_with_limit(ranked_tags, files)
    
    def _format_file_list(self, files: List[str]) -> str:
        """Format a simple file list when no code can be parsed."""
        lines = ["Repository files:"]
        for fname in sorted(files)[:50]:  # Limit to 50 files
            rel_fname = self.get_rel_fname(fname)
            lines.append(f"  {rel_fname}")
        return "\n".join(lines)
    
    def _format_map_with_limit(
        self,
        ranked_tags: List[Tuple[float, Tag]],
        all_files: List[str]
    ) -> str:
        """
        Format the map within token limits using binary search.
        
        Args:
            ranked_tags: Ranked list of (score, tag) tuples.
            all_files: All files in the repository.
            
        Returns:
            Formatted map string.
        """
        # Binary search for optimal number of tags
        left, right = 0, len(ranked_tags)
        best_output = ""
        
        while left <= right:
            mid = (left + right) // 2
            output = self._format_tags(ranked_tags[:mid], all_files)
            tokens = count_tokens(output, self.model)
            
            if tokens <= self.max_tokens:
                best_output = output
                left = mid + 1
            else:
                right = mid - 1
        
        return best_output
    
    def _format_tags(
        self,
        tags: List[Tuple[float, Tag]],
        all_files: List[str]
    ) -> str:
        """
        Format tags into readable output.
        
        Args:
            tags: List of (rank, tag) tuples.
            all_files: All files for context.
            
        Returns:
            Formatted string.
        """
        if not tags:
            return ""
        
        # Group by file
        file_tags: Dict[str, List[Tuple[float, Tag]]] = defaultdict(list)
        for rank, tag in tags:
            file_tags[tag.rel_fname].append((rank, tag))
        
        # Sort files by max rank
        sorted_files = sorted(
            file_tags.items(),
            key=lambda x: max(r for r, _ in x[1]),
            reverse=True
        )
        
        # Format output
        parts = []
        for rel_fname, file_tag_list in sorted_files:
            max_rank = max(r for r, _ in file_tag_list)
            
            lines = [f"{rel_fname}:", f"(Rank: {max_rank:.2f})", ""]
            
            # Get unique lines of interest
            lois = sorted(set(tag.line for _, tag in file_tag_list))
            
            # Try to render with context
            abs_fname = str(self.root / rel_fname)
            rendered = self._render_file_context(abs_fname, rel_fname, lois)
            
            if rendered:
                lines.append(rendered)
            else:
                # Fallback: just list the definitions
                for _, tag in sorted(file_tag_list, key=lambda x: x[1].line):
                    lines.append(f"  {tag.line:4d}: {tag.name}")
            
            parts.append("\n".join(lines))
        
        return "\n\n".join(parts)
    
    def _render_file_context(
        self,
        abs_fname: str,
        rel_fname: str,
        lines_of_interest: List[int]
    ) -> str:
        """
        Render file content with context around lines of interest.
        
        Args:
            abs_fname: Absolute file path.
            rel_fname: Relative file path.
            lines_of_interest: Line numbers to highlight.
            
        Returns:
            Formatted code snippet.
        """
        try:
            from grep_ast import TreeContext
            
            code = self.file_reader(abs_fname)
            if not code:
                return ""
            
            if rel_fname not in self._tree_context_cache:
                self._tree_context_cache[rel_fname] = TreeContext(
                    rel_fname,
                    code,
                    color=False
                )
            
            tree_context = self._tree_context_cache[rel_fname]
            return tree_context.format(lines_of_interest)
            
        except Exception:
            # Fallback: show raw lines
            code = self.file_reader(abs_fname)
            if not code:
                return ""
            
            code_lines = code.splitlines()
            result = []
            for loi in lines_of_interest:
                if 1 <= loi <= len(code_lines):
                    result.append(f"  {loi:4d}: {code_lines[loi-1]}")
            
            return "\n".join(result)
