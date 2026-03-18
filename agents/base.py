"""
Common functionality for LLM invocation, memory operations, error
handling, and logging.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Type
from datetime import datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from services.memory import AgentMemory, AgentMemoryError
from services.rate_limiter import RateLimiter
from models.models import Task, TaskStatus
from utils.logging import log_to_db, log_agent_event, LogType
from api.config import settings

logger = logging.getLogger(__name__)


class TaskResult:
    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
    
    def __repr__(self) -> str:
        return f"<TaskResult(success={self.success}, error={self.error})>"


class BaseAgentError(Exception):
    pass


class BaseAgent(ABC):
    def __init__(
        self,
        llm: BaseChatModel,
        memory: AgentMemory,
        config: Optional[Any] = None,
        **kwargs
    ):
        self.llm = llm
        self.memory = memory
        self.config = config
        self.role = self.get_role()
        self._current_project_id: Optional[str] = None
        # Initialize rate limiter (30 req/min for Groq free tier)
        self._rate_limiter = RateLimiter(
            api_key=settings.groq_api_key or "default",
            service_type="groq",
            requests_per_minute=30
        )
        logger.info(f"Initialized {self.role} agent with rate limiting")
    
    def set_project_context(self, project_id: str) -> None:
        """Set the current project context for logging"""
        self._current_project_id = project_id
    
    def _log(self, level: str, message: str, log_type: Optional[LogType] = None) -> None:
        """Internal logging helper"""
        logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.role}] {message}")
        if self._current_project_id:
            log_to_db(
                project_id=self._current_project_id,
                level=level,
                message=message,
                agent_role=self.role,
                log_type=log_type
            )
    
    @abstractmethod
    def get_role(self) -> str:
        pass
    
    @abstractmethod
    async def process_task(self, task: Task, context: Dict[str, Any]) -> TaskResult:
        pass
    
    async def invoke_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        # Rate limit before making request
        await self._rate_limiter.acquire()
        
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        self._log("DEBUG", f"LLM request: {prompt_preview}", LogType.LLM_REQUEST)
        
        try:
            response = await self.llm.ainvoke(messages)
            response_preview = response.content[:100] + "..." if len(response.content) > 100 else response.content
            self._log("DEBUG", f"LLM response: {response_preview}", LogType.LLM_RESPONSE)
            return response.content
        except Exception as e:
            error_msg = f"LLM invocation failed: {str(e)}"
            self._log("ERROR", error_msg, LogType.LLM_ERROR)
            raise BaseAgentError(error_msg) from e
    
    async def invoke_llm_structured(
        self,
        prompt: str,
        schema: Union[Dict[str, Any], Type],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        import json
        
        # Rate limit before making request
        await self._rate_limiter.acquire()
        
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        # Try structured output (tool calling) first
        try:
            if isinstance(schema, type):
                # Pydantic model - use native tool calling
                structured_llm = self.llm.with_structured_output(schema)
                response = await structured_llm.ainvoke(messages)
                return response.model_dump() if hasattr(response, 'model_dump') else response
            else:
                # Dict schema - use JSON instruction in prompt
                schema_text = f"\n\nYou must respond with valid JSON matching this schema:\n```json\n{json.dumps(schema, indent=2)}\n```"
                messages[-1] = HumanMessage(content=prompt + schema_text)
                response = await self.llm.ainvoke(messages)
                return json.loads(response.content)
                
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if this is a Groq tool_use_failed error - fallback to JSON mode
            if 'tool_use_failed' in error_str or 'failed to call a function' in error_str:
                self._log("WARNING", "Groq tool calling failed, falling back to JSON mode...")
                
                try:
                    # Fallback: Use JSON mode instead of tool calling
                    await self._rate_limiter.acquire()
                    
                    # Get JSON schema from Pydantic model if needed
                    if isinstance(schema, type) and hasattr(schema, 'model_json_schema'):
                        json_schema = schema.model_json_schema()
                    elif isinstance(schema, type) and hasattr(schema, 'schema'):
                        json_schema = schema.schema()
                    else:
                        json_schema = schema
                    
                    # Rebuild messages with schema in prompt
                    fallback_messages = []
                    if system_prompt:
                        fallback_messages.append(SystemMessage(
                            content=system_prompt + "\n\nYou must respond with valid JSON only."
                        ))
                    
                    schema_instruction = f"\n\nRespond with valid JSON matching this schema:\n```json\n{json.dumps(json_schema, indent=2)}\n```\n\nReturn ONLY the JSON object, no other text."
                    fallback_messages.append(HumanMessage(content=prompt + schema_instruction))
                    
                    # Use JSON mode (response_format)
                    json_llm = self.llm.bind(response_format={"type": "json_object"})
                    response = await json_llm.ainvoke(fallback_messages)
                    
                    # Parse JSON response
                    parsed = json.loads(response.content)
                    
                    # Validate and construct Pydantic model if schema is a class
                    if isinstance(schema, type) and hasattr(schema, 'model_validate'):
                        validated = schema.model_validate(parsed)
                        return validated.model_dump()
                    
                    return parsed
                    
                except Exception as fallback_error:
                    error_msg = f"Structured LLM failed (both tool calling and JSON fallback): {str(fallback_error)}"
                    raise BaseAgentError(error_msg) from fallback_error
            
            # Not a tool_use_failed error - raise original
            error_msg = f"Structured LLM invocation failed: {str(e)}"
            raise BaseAgentError(error_msg) from e
    
    async def store_memory(
        self,
        key: str,
        value: Any,
        memory_type: str = "context",
        project_id: Optional[str] = None,
        collection_type: str = "agent_memory"
    ) -> str:
        """Store information in agent memory"""
        try:
            content = str(value) if not isinstance(value, str) else value
            metadata = {
                "agent_role": self.role,
                "memory_type": memory_type,
                "key": key,
                "timestamp": datetime.utcnow().isoformat()
            }
            if project_id:
                metadata["project_id"] = project_id
            
            memory_id = await self.memory.store(
                content=content,
                metadata=metadata,
                collection_type=collection_type
            )
            return memory_id
        except AgentMemoryError as e:
            raise BaseAgentError(f"Failed to store memory: {str(e)}") from e
    
    async def retrieve_memory(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
        project_id: Optional[str] = None,
        collection_type: str = "agent_memory"
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant information from memory"""
        try:
            metadata_filter = {}
            if memory_type:
                metadata_filter["memory_type"] = memory_type
            if project_id:
                metadata_filter["project_id"] = project_id
            
            memories = await self.memory.retrieve(
                query=query,
                collection_type=collection_type,
                limit=limit,
                metadata_filter=metadata_filter if metadata_filter else None
            )
            return memories
        except AgentMemoryError as e:
            raise BaseAgentError(f"Failed to retrieve memory: {str(e)}") from e
    
    async def clear_memory(
        self,
        project_id: Optional[str] = None,
        collection_type: Optional[str] = None
    ) -> int:
        """Clear memories from agent memory"""
        try:
            metadata_filter = {"project_id": project_id} if project_id else None
            count = await self.memory.clear(
                collection_type=collection_type,
                metadata_filter=metadata_filter
            )
            return count
        except AgentMemoryError as e:
            raise BaseAgentError(f"Failed to clear memory: {str(e)}") from e
    
    async def retrieve_memory_by_key(
        self,
        key: str,
        project_id: Optional[str] = None,
        collection_type: str = "agent_memory"
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific memory by exact key match (not semantic search).
        
        Use this for critical lookups like architecture plans and research context
        where semantic similarity may not reliably find the exact document.
        
        Args:
            key: The exact key value to match
            project_id: Optional project ID to scope the search
            collection_type: Collection to search
            
        Returns:
            Memory dict with id, content, metadata or None if not found
        """
        try:
            return await self.memory.retrieve_by_key(
                key=key,
                collection_type=collection_type,
                project_id=project_id
            )
        except AgentMemoryError as e:
            raise BaseAgentError(f"Failed to retrieve memory by key: {str(e)}") from e
    

    
    def build_system_prompt(self, additional_instructions: Optional[str] = None) -> str:
        """Build system prompt for this agent"""
        # Skip redundant intro if additional_instructions already sets context
        if additional_instructions:
            return additional_instructions
        return f"You are a {self.role.replace('_', ' ')} agent."
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(role={self.role})>"
