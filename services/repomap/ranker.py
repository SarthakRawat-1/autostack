"""
PageRank-based file ranking for RepoMap.

Ranks files by importance based on cross-references using the PageRank algorithm.
"""

from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

import networkx as nx

from services.repomap.parser import Tag


def build_reference_graph(
    tags_by_file: Dict[str, List[Tag]]
) -> nx.MultiDiGraph:
    """
    Build a directed graph of file references.
    
    Nodes are files, edges represent symbol references between files.
    
    Args:
        tags_by_file: Dictionary mapping file paths to their tags.
        
    Returns:
        NetworkX directed multigraph of file references.
    """
    # Collect definitions and references
    defines: Dict[str, Set[str]] = defaultdict(set)  # symbol -> files that define it
    references: Dict[str, Set[str]] = defaultdict(set)  # symbol -> files that reference it
    
    for rel_fname, tags in tags_by_file.items():
        for tag in tags:
            if tag.kind == "def":
                defines[tag.name].add(rel_fname)
            elif tag.kind == "ref":
                references[tag.name].add(rel_fname)
    
    # Build graph
    G = nx.MultiDiGraph()
    
    # Add all files as nodes
    for rel_fname in tags_by_file.keys():
        G.add_node(rel_fname)
    
    # Add edges: reference file -> definition file
    for symbol_name, ref_files in references.items():
        def_files = defines.get(symbol_name, set())
        for ref_file in ref_files:
            for def_file in def_files:
                if ref_file != def_file:  # Don't add self-loops
                    G.add_edge(ref_file, def_file, name=symbol_name)
    
    return G


def rank_files(
    tags_by_file: Dict[str, List[Tag]],
    priority_files: Optional[Set[str]] = None,
    mentioned_files: Optional[Set[str]] = None,
    mentioned_idents: Optional[Set[str]] = None
) -> Dict[str, float]:
    """
    Rank files by importance using PageRank.
    
    Args:
        tags_by_file: Dictionary mapping file paths to their tags.
        priority_files: Files to boost (e.g., currently edited files).
        mentioned_files: Files explicitly mentioned by user.
        mentioned_idents: Identifiers explicitly mentioned by user.
        
    Returns:
        Dictionary mapping file paths to their rank scores.
    """
    if not tags_by_file:
        return {}
    
    # Build the reference graph
    G = build_reference_graph(tags_by_file)
    
    if not G.nodes():
        return {f: 1.0 for f in tags_by_file.keys()}
    
    # Set up personalization for priority files
    personalization = None
    if priority_files:
        personalization = {}
        for node in G.nodes():
            if node in priority_files:
                personalization[node] = 100.0
            else:
                personalization[node] = 1.0
    
    # Run PageRank
    try:
        if personalization:
            ranks = nx.pagerank(G, personalization=personalization, alpha=0.85)
        else:
            ranks = nx.pagerank(G, alpha=0.85)
    except Exception:
        # Fallback to uniform ranking
        ranks = {node: 1.0 for node in G.nodes()}
    
    # Boost mentioned files and identifiers
    if mentioned_files or mentioned_idents:
        ranks = boost_ranks(
            ranks,
            tags_by_file,
            mentioned_files or set(),
            mentioned_idents or set()
        )
    
    return ranks


def boost_ranks(
    ranks: Dict[str, float],
    tags_by_file: Dict[str, List[Tag]],
    mentioned_files: Set[str],
    mentioned_idents: Set[str]
) -> Dict[str, float]:
    """
    Boost file ranks based on mentions.
    
    Args:
        ranks: Current file rankings.
        tags_by_file: Tags indexed by file.
        mentioned_files: Files to boost.
        mentioned_idents: Identifiers to boost.
        
    Returns:
        Updated rankings with boosts applied.
    """
    boosted = dict(ranks)
    
    for rel_fname, rank in ranks.items():
        boost = 1.0
        
        # Boost if file is mentioned
        if rel_fname in mentioned_files:
            boost *= 5.0
        
        # Boost if file contains mentioned identifiers
        if mentioned_idents:
            tags = tags_by_file.get(rel_fname, [])
            file_symbols = {t.name for t in tags if t.kind == "def"}
            if file_symbols & mentioned_idents:
                boost *= 10.0
        
        boosted[rel_fname] = rank * boost
    
    return boosted


def rank_tags(
    tags_by_file: Dict[str, List[Tag]],
    file_ranks: Dict[str, float],
    priority_files: Optional[Set[str]] = None,
    mentioned_idents: Optional[Set[str]] = None
) -> List[Tuple[float, Tag]]:
    """
    Rank individual tags based on file ranks and boosts.
    
    Args:
        tags_by_file: Tags indexed by file.
        file_ranks: File rank scores.
        priority_files: Files to prioritize.
        mentioned_idents: Identifiers to boost.
        
    Returns:
        List of (rank, Tag) tuples sorted by rank descending.
    """
    ranked_tags = []
    priority_files = priority_files or set()
    mentioned_idents = mentioned_idents or set()
    
    for rel_fname, tags in tags_by_file.items():
        file_rank = file_ranks.get(rel_fname, 0.0)
        
        for tag in tags:
            if tag.kind != "def":
                continue
            
            # Calculate boost
            boost = 1.0
            
            if tag.name in mentioned_idents:
                boost *= 10.0
            
            if rel_fname in priority_files:
                boost *= 20.0
            
            final_rank = file_rank * boost
            ranked_tags.append((final_rank, tag))
    
    # Sort by rank descending
    ranked_tags.sort(key=lambda x: x[0], reverse=True)
    
    return ranked_tags
