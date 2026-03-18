import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
import logging
import openai
from api.config import settings

logger = logging.getLogger(__name__)


class AzureOpenAIEmbeddingFunction:
    """ChromaDB-compatible embedding function using Azure OpenAI with API key auth."""

    def __init__(self, endpoint: str, deployment: str, api_key: str):
        self._client = openai.AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-01"
        )
        self._deployment = deployment

    def __call__(self, input: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            input=input,
            model=self._deployment
        )
        return [item.embedding for item in response.data]

class AgentMemoryError(Exception):
    pass

class AgentMemory:
    AGENT_MEMORY_COLLECTION = "agent_memory"
    CODE_ARTIFACTS_COLLECTION = "code_artifacts"
    
    def __init__(
        self,
        chroma_api_key: Optional[str] = None,
        chroma_tenant: Optional[str] = None,
        chroma_database: Optional[str] = None
    ):
        self.chroma_api_key = chroma_api_key or settings.chroma_api_key
        self.chroma_tenant = chroma_tenant or settings.chroma_tenant
        self.chroma_database = chroma_database or settings.chroma_database
        self.client = None
        self.agent_memory_collection = None
        self.code_artifacts_collection = None
        self.embedding_fn = None
        self._connected = False
    
    def connect(self) -> None:
        try:
            # Use HttpClient with Chroma Cloud
            self.client = chromadb.HttpClient(
                host="api.trychroma.com",
                ssl=True,
                headers={
                    "x-chroma-token": self.chroma_api_key,
                },
                tenant=self.chroma_tenant,
                database=self.chroma_database
            )

            # Use Azure OpenAI embeddings
            self.embedding_fn = AzureOpenAIEmbeddingFunction(
                endpoint=settings.azure_openai_endpoint,
                deployment=settings.azure_openai_embedding_deployment,
                api_key=settings.azure_openai_api_key
            )

            self.agent_memory_collection = self.client.get_or_create_collection(
                name=self.AGENT_MEMORY_COLLECTION,
                embedding_function=self.embedding_fn,
                metadata={
                    "description": "Agent memory storage for context and decisions",
                    "created_at": datetime.utcnow().isoformat()
                }
            )

            self.code_artifacts_collection = self.client.get_or_create_collection(
                name=self.CODE_ARTIFACTS_COLLECTION,
                embedding_function=self.embedding_fn,
                metadata={
                    "description": "Code artifacts storage with metadata",
                    "created_at": datetime.utcnow().isoformat()
                }
            )

            self._connected = True

        except Exception as e:
            raise AgentMemoryError(f"Failed to connect to Chroma Cloud: {str(e)}")
    

    async def store(
        self,
        content: str,
        metadata: Dict[str, Any],
        collection_type: str = "agent_memory",
        memory_id: Optional[str] = None
    ) -> str:
        if not self._connected:
            raise AgentMemoryError("Not connected to Chroma Cloud. Call connect() first.")

        if memory_id is None:
            memory_id = f"mem-{uuid.uuid4().hex[:12]}"

        if "timestamp" not in metadata:
            metadata["timestamp"] = datetime.utcnow().isoformat()

        if collection_type == "agent_memory":
            collection = self.agent_memory_collection
        elif collection_type == "code_artifacts":
            collection = self.code_artifacts_collection
        else:
            raise AgentMemoryError(f"Invalid collection type: {collection_type}")
        
        try:
            await asyncio.to_thread(
                collection.add,
                documents=[content],
                metadatas=[metadata],
                ids=[memory_id]
            )
            
            return memory_id
            
        except Exception as e:
            raise AgentMemoryError(f"Failed to store memory: {str(e)}")
    
    async def retrieve(
        self,
        query: str,
        collection_type: str = "agent_memory",
        limit: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not self._connected:
            raise AgentMemoryError("Not connected to Chroma Cloud. Call connect() first.")

        if collection_type == "agent_memory":
            collection = self.agent_memory_collection
        elif collection_type == "code_artifacts":
            collection = self.code_artifacts_collection
        else:
            raise AgentMemoryError(f"Invalid collection type: {collection_type}")
        
        try:
            chroma_filter = None
            if metadata_filter:
                conditions = []
                for key, value in metadata_filter.items():
                    if isinstance(value, (str, int, float)):
                        conditions.append({key: {"$eq": value}})
                    elif isinstance(value, list):
                        for item in value:
                            conditions.append({key: {"$eq": item}})
                    else:
                        conditions.append({key: {"$eq": str(value)}})

                if len(conditions) == 1:
                    chroma_filter = conditions[0]
                elif len(conditions) > 1:
                    chroma_filter = {"$and": conditions}

            results = await asyncio.to_thread(
                collection.query,
                query_texts=[query],
                n_results=limit,
                where=chroma_filter
            )

            memories = []
            if results["documents"] and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    memory = {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i]
                    }
                    memories.append(memory)
            
            return memories
            
        except Exception as e:
            raise AgentMemoryError(f"Failed to retrieve memories: {str(e)}")
    
    async def retrieve_by_key(
        self,
        key: str,
        collection_type: str = "agent_memory",
        project_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific memory by exact key match (not semantic search).
        
        Uses ChromaDB's get() with metadata filter for reliable retrieval
        of critical memories like architecture plans and research context.
        
        Args:
            key: The exact key value to match in metadata
            collection_type: Collection to search ("agent_memory" or "code_artifacts")
            project_id: Optional project ID to scope the search
            
        Returns:
            Memory dict with id, content, metadata or None if not found
        """
        if not self._connected:
            raise AgentMemoryError("Not connected to Chroma Cloud. Call connect() first.")

        if collection_type == "agent_memory":
            collection = self.agent_memory_collection
        elif collection_type == "code_artifacts":
            collection = self.code_artifacts_collection
        else:
            raise AgentMemoryError(f"Invalid collection type: {collection_type}")
        
        try:
            # Build filter for exact key match
            conditions = [{"key": {"$eq": key}}]
            if project_id:
                conditions.append({"project_id": {"$eq": project_id}})
            
            if len(conditions) == 1:
                chroma_filter = conditions[0]
            else:
                chroma_filter = {"$and": conditions}
            
            # Use get() instead of query() for exact matching
            results = await asyncio.to_thread(
                collection.get,
                where=chroma_filter,
                limit=1
            )
            
            if results["ids"] and len(results["ids"]) > 0:
                return {
                    "id": results["ids"][0],
                    "content": results["documents"][0],
                    "metadata": results["metadatas"][0]
                }
            
            return None
            
        except Exception as e:
            raise AgentMemoryError(f"Failed to retrieve memory by key: {str(e)}")
    
    async def clear(
        self,
        collection_type: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> int:
        if not self._connected:
            raise AgentMemoryError("Not connected to Chroma Cloud. Call connect() first.")
        
        total_cleared = 0
        
        try:
            collections_to_clear = []
            if collection_type is None:
                collections_to_clear = [
                    ("agent_memory", self.agent_memory_collection),
                    ("code_artifacts", self.code_artifacts_collection)
                ]
            elif collection_type == "agent_memory":
                collections_to_clear = [("agent_memory", self.agent_memory_collection)]
            elif collection_type == "code_artifacts":
                collections_to_clear = [("code_artifacts", self.code_artifacts_collection)]
            else:
                raise AgentMemoryError(f"Invalid collection type: {collection_type}")

            for col_name, collection in collections_to_clear:
                if metadata_filter:
                    results = await asyncio.to_thread(
                        collection.get,
                        where=metadata_filter
                    )
                    
                    if results["ids"]:
                        await asyncio.to_thread(
                            collection.delete,
                            ids=results["ids"]
                        )
                        total_cleared += len(results["ids"])
                else:
                    count = collection.count()
                    await asyncio.to_thread(
                        self.client.delete_collection,
                        name=col_name
                    )
                    
                    if col_name == "agent_memory":
                        self.agent_memory_collection = self.client.get_or_create_collection(
                            name=self.AGENT_MEMORY_COLLECTION,
                            embedding_function=self.embedding_fn
                        )
                    else:
                        self.code_artifacts_collection = self.client.get_or_create_collection(
                            name=self.CODE_ARTIFACTS_COLLECTION,
                            embedding_function=self.embedding_fn
                        )
                    
                    total_cleared += count
            
            return total_cleared
            
        except Exception as e:
            raise AgentMemoryError(f"Failed to clear memories: {str(e)}")
    
_agent_memory_instance = None


def get_agent_memory() -> AgentMemory:
    global _agent_memory_instance
    
    if _agent_memory_instance is None:
        _agent_memory_instance = AgentMemory()
        _agent_memory_instance.connect()
    
    return _agent_memory_instance