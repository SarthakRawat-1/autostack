"""
Tree-sitter code parser for RepoMap.

Extracts code definitions (functions, classes, methods) and references
from source files using Tree-sitter parsing.
"""

import os
import sys
from collections import namedtuple
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

# Tag represents a code symbol (definition or reference)
Tag = namedtuple("Tag", ["rel_fname", "fname", "line", "name", "kind"])


def get_queries_dir() -> Path:
    """Get the path to the Tree-sitter queries directory."""
    return Path(__file__).parent / "queries"


def get_scm_fname(lang: str) -> Optional[str]:
    """
    Get the Tree-sitter query file path for a language.
    
    Args:
        lang: Language identifier (e.g., 'python', 'javascript').
        
    Returns:
        Path to the .scm query file, or None if not found.
    """
    queries_dir = get_queries_dir()
    scm_file = queries_dir / f"tree-sitter-{lang}-tags.scm"
    
    if scm_file.exists():
        return str(scm_file)
    
    # Try alternate naming
    scm_file = queries_dir / f"{lang}-tags.scm"
    if scm_file.exists():
        return str(scm_file)
    
    return None


def read_text(filename: str, encoding: str = "utf-8", silent: bool = False) -> Optional[str]:
    """
    Read text content from a file.
    
    Args:
        filename: Path to the file.
        encoding: Text encoding (default: utf-8).
        silent: If True, suppress error messages.
        
    Returns:
        File contents as string, or None on error.
    """
    try:
        with open(filename, "r", encoding=encoding, errors="ignore") as f:
            return f.read()
    except Exception as e:
        if not silent:
            print(f"Error reading {filename}: {e}", file=sys.stderr)
        return None


class CodeParser:
    """
    Parser for extracting code structure using Tree-sitter.
    """
    
    def __init__(
        self,
        file_reader: Callable[[str], Optional[str]] = read_text,
        verbose: bool = False
    ):
        """
        Initialize the code parser.
        
        Args:
            file_reader: Function to read file contents.
            verbose: Enable verbose output.
        """
        self.file_reader = file_reader
        self.verbose = verbose
        self._parsers_cache: Dict[str, Any] = {}
        self._languages_cache: Dict[str, Any] = {}
    
    def get_tags(self, fname: str, rel_fname: str) -> List[Tag]:
        """
        Extract all tags (definitions and references) from a file.
        
        Args:
            fname: Absolute path to the file.
            rel_fname: Relative path for display.
            
        Returns:
            List of Tag objects representing code symbols.
        """
        try:
            from grep_ast import filename_to_lang
        except ImportError:
            print("Error: grep-ast is required. Install with: pip install grep-ast")
            return []
        
        lang = filename_to_lang(fname)
        if not lang:
            return []
        
        return self._parse_file(fname, rel_fname, lang)
    
    def _parse_file(self, fname: str, rel_fname: str, lang: str) -> List[Tag]:
        """
        Parse a single file and extract tags.
        
        Args:
            fname: Absolute file path.
            rel_fname: Relative file path.
            lang: Language identifier.
            
        Returns:
            List of extracted tags.
        """
        try:
            from grep_ast.tsl import get_language, get_parser
            from tree_sitter import QueryCursor
        except ImportError as e:
            if self.verbose:
                print(f"Import error: {e}", file=sys.stderr)
            return []
        
        # Get parser and language
        try:
            if lang not in self._parsers_cache:
                self._parsers_cache[lang] = get_parser(lang)
                self._languages_cache[lang] = get_language(lang)
            
            parser = self._parsers_cache[lang]
            language = self._languages_cache[lang]
        except Exception as e:
            if self.verbose:
                print(f"Error getting parser for {lang}: {e}", file=sys.stderr)
            return []
        
        # Get query file
        scm_fname = get_scm_fname(lang)
        if not scm_fname:
            return []
        
        # Read source code
        code = self.file_reader(fname)
        if not code:
            return []
        
        # Parse and extract tags
        try:
            tree = parser.parse(bytes(code, "utf-8"))
            
            query_text = read_text(scm_fname, silent=True)
            if not query_text:
                return []
            
            query = language.query(query_text)
            cursor = QueryCursor(query)
            captures = cursor.captures(tree.root_node)
            
            tags = []
            for capture_name, nodes in captures.items():
                for node in nodes:
                    if "name.definition" in capture_name:
                        kind = "def"
                    elif "name.reference" in capture_name:
                        kind = "ref"
                    else:
                        continue
                    
                    line_num = node.start_point[0] + 1
                    name = node.text.decode("utf-8") if node.text else ""
                    
                    tags.append(Tag(
                        rel_fname=rel_fname,
                        fname=fname,
                        line=line_num,
                        name=name,
                        kind=kind
                    ))
            
            return tags
            
        except Exception as e:
            if self.verbose:
                print(f"Error parsing {fname}: {e}", file=sys.stderr)
            return []
    
    def get_definitions(self, fname: str, rel_fname: str) -> List[Tag]:
        """
        Extract only definition tags from a file.
        
        Args:
            fname: Absolute file path.
            rel_fname: Relative file path.
            
        Returns:
            List of definition tags only.
        """
        tags = self.get_tags(fname, rel_fname)
        return [t for t in tags if t.kind == "def"]
    
    def get_references(self, fname: str, rel_fname: str) -> List[Tag]:
        """
        Extract only reference tags from a file.
        
        Args:
            fname: Absolute file path.
            rel_fname: Relative file path.
            
        Returns:
            List of reference tags only.
        """
        tags = self.get_tags(fname, rel_fname)
        return [t for t in tags if t.kind == "ref"]
