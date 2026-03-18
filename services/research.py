# File: services/research.py
"""
Tavily Research Service

Provides real-time web search for agent context enrichment.
Uses Tavily AI search API optimized for LLM applications.

This service helps agents get up-to-date information about:
- Current package versions and compatibility
- Tech stack recommendations
- Best practices and patterns
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TavilyResearchService:
    """
    Real-time web search service for agents
    
    Provides methods for searching current tech stack info,
    package versions, and best practices.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Tavily research service
        
        Args:
            api_key: Tavily API key. If not provided, tries to load from config.
        """
        self._api_key = api_key
        self._client = None
        self._initialized = False
        
    def _ensure_initialized(self) -> bool:
        """Lazy initialization of Tavily client"""
        if self._initialized:
            return self._client is not None
            
        self._initialized = True
        
        try:
            # Try to import tavily
            from tavily import TavilyClient
            
            # Get API key
            if not self._api_key:
                from api.config import settings
                self._api_key = getattr(settings, 'tavily_api_key', None)
            
            if not self._api_key:
                logger.warning("Tavily API key not configured - research service disabled")
                return False
            
            self._client = TavilyClient(api_key=self._api_key)
            logger.info("Tavily research service initialized successfully")
            return True
            
        except ImportError:
            logger.warning("tavily-python not installed - research service disabled")
            return False
        except Exception as e:
            logger.warning(f"Failed to initialize Tavily client: {e}")
            return False
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = False
    ) -> Dict[str, Any]:
        """
        Perform a general web search using Tavily's native summarization.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            search_depth: "basic" (NLP summary per URL) or "advanced" (semantic chunks)
            include_answer: If True, returns LLM-generated answer (most token-efficient!)
            
        Returns:
            Dict with 'results' list and optional 'answer' (pre-summarized by Tavily)
        """
        if not self._ensure_initialized():
            return {"results": [], "answer": None}
        
        try:
            response = self._client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=include_answer  # Use Tavily's built-in LLM summarization!
            )
            
            results = response.get("results", [])
            answer = response.get("answer")  # Pre-summarized answer from Tavily
            logger.info(f"Tavily search for '{query}' returned {len(results)} results" + 
                       (f" with answer" if answer else ""))
            return {"results": results, "answer": answer}
            
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return {"results": [], "answer": None}
    
    async def search_tech_stack(
        self,
        project_type: str,
        requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for current tech stack recommendations using Tavily's native LLM answer.
        
        Args:
            project_type: Type of project (e.g., "REST API", "web app", "CLI tool")
            requirements: Optional additional requirements
            
        Returns:
            Dict with pre-summarized recommendations from Tavily
        """
        query = f"best tech stack for {project_type} 2024 compatible versions"
        if requirements:
            query += f" {requirements}"
        
        # Use include_answer=True for Tavily's built-in LLM summarization!
        response = await self.search(query, max_results=3, include_answer=True)
        
        # Prefer Tavily's pre-generated answer (most token-efficient)
        if response.get("answer"):
            return {
                "recommendations": response["answer"],
                "source": "tavily_answer",
                "query": query
            }
        
        # Fallback: results are already NLP-summarized by Tavily (search_depth=basic)
        results = response.get("results", [])
        if not results:
            return {"recommendations": "", "source": "none"}
        
        # Content is already summarized by Tavily's NLP, just combine
        combined = " | ".join([r.get('content', '')[:200] for r in results[:2]])
        
        return {
            "recommendations": combined,
            "source": "tavily_results",
            "query": query,
            "result_count": len(results)
        }
    
    async def search_package_versions(
        self,
        language: str,
        packages: List[str]
    ) -> Dict[str, str]:
        """
        Search for current compatible package versions using Tavily's native answer.
        
        Args:
            language: Programming language (e.g., "python", "javascript")
            packages: List of package names
            
        Returns:
            Dict with version info (pre-summarized by Tavily)
        """
        package_list = ", ".join(packages)
        
        # Query for actively maintained packages with recent updates
        query = f"{language} {package_list} actively maintained latest stable version 2024 not deprecated"
        
        # Use include_answer for pre-summarized version info
        response = await self.search(query, max_results=3, include_answer=True)
        
        # Prefer Tavily's answer
        if response.get("answer"):
            return {
                "packages": packages,
                "language": language,
                "version_info": response["answer"],
                "source": "tavily_answer"
            }
        
        # Fallback: NLP-summarized results
        results = response.get("results", [])
        if not results:
            return {"packages": packages, "language": language, "version_info": ""}
        
        return {
            "packages": packages,
            "language": language,
            "version_info": results[0].get('content', '')[:300],  # First result's summary
            "source": "tavily_results"
        }
    
    async def search_best_practices(
        self,
        topic: str,
        language: Optional[str] = None
    ) -> str:
        """
        Search for current best practices using Tavily's native LLM answer.
        
        Args:
            topic: Topic to search (e.g., "REST API design", "pytest testing")
            language: Optional programming language context
            
        Returns:
            Pre-summarized best practices from Tavily
        """
        query = f"{topic} best practices 2024"
        if language:
            query = f"{language} {query}"
        
        # Use include_answer for concise, pre-summarized response
        response = await self.search(query, max_results=2, include_answer=True)
        
        # Prefer Tavily's LLM-generated answer
        if response.get("answer"):
            return response["answer"]
        
        # Fallback: NLP-summarized results (already compact)
        results = response.get("results", [])
        if not results:
            return ""
        
        return " | ".join([r.get('content', '')[:200] for r in results[:2]])
    
    async def search_project_structure(
        self,
        framework: str,
        project_type: str
    ) -> str:
        """
        Search for project structure using Tavily's native answer.
        
        Args:
            framework: Framework being used (e.g., "Flask", "FastAPI", "Next.js")
            project_type: Type of project
            
        Returns:
            Pre-summarized project structure recommendations
        """
        query = f"{framework} {project_type} project structure directory layout 2024"
        
        # Use include_answer for concise structure recommendation
        response = await self.search(query, max_results=2, include_answer=True)
        
        if response.get("answer"):
            return response["answer"]
        
        # Fallback: first result's NLP summary
        results = response.get("results", [])
        if not results:
            return ""
        
        return results[0].get('content', '')[:400]
    
    async def get_context_for_code_generation(
        self,
        language: str,
        framework: str,
        project_type: str,
        features: List[str]
    ) -> Dict[str, Any]:
        """
        Get comprehensive context for code generation using Tavily's native summarization.
        
        All searches use include_answer=True to get pre-summarized responses,
        eliminating the need for custom extraction logic.
        
        Args:
            language: Programming language
            framework: Main framework
            project_type: Type of project
            features: List of features to implement
            
        Returns:
            Dict with all gathered context (pre-summarized by Tavily)
        """
        context = {
            "language": language,
            "framework": framework,
            "project_type": project_type
        }
        
        # All these methods now use Tavily's include_answer=True for pre-summarization
        
        # Search for package versions (Tavily answer is already concise)
        packages_result = await self.search_package_versions(
            language=language,
            packages=[framework] + features[:3]
        )
        context["package_info"] = packages_result.get("version_info", "")
        
        # Search for project structure (Tavily answer is already concise)
        context["project_structure"] = await self.search_project_structure(framework, project_type)
        
        # Search for best practices (Tavily answer is already concise)
        context["best_practices"] = await self.search_best_practices(
            topic=f"{framework} {project_type}",
            language=language
        )
        
        # Search for testing setup (Tavily answer is already concise)
        context["testing_setup"] = await self.search_best_practices(
            topic=f"testing framework setup configuration",
            language=language
        )
        
        logger.info(f"Gathered research context for {language}/{framework}/{project_type}")
        
        return context


# Singleton instance (lazy initialized)
_research_service: Optional[TavilyResearchService] = None


def get_research_service() -> TavilyResearchService:
    """Get or create the singleton research service"""
    global _research_service
    if _research_service is None:
        _research_service = TavilyResearchService()
    return _research_service
