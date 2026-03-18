"""
Configuration module for AutoStack API

Loads and validates environment variables using Pydantic Settings.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    
    # Database Configuration
    database_url: str
    
    # PostgreSQL Configuration (for docker-compose)
    postgres_user: str = "autostack_user"
    postgres_password: str = "secure_password"
    postgres_db: str = "autostack"
    
    # OpenRouter Configuration (for Developer and QA agents)
    openrouter_api_key: str
    openrouter_model: str = "qwen/qwen-2.5-72b-instruct"

    # Groq Configuration (for all agents - can be different models)
    groq_api_key: str
    groq_model: str = "qwen/qwen3-32b"  # Default model for code generation
    groq_non_code_model: str = "llama-3.3-70b-versatile"  # Model for PM/docs agents

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 hours

    # Azure OpenAI Configuration (for Embeddings)
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # Azure Configuration (for Infrastructure Provisioning)
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None
    azure_subscription_id: Optional[str] = None

    # GitHub Configuration
    github_token: str
    
    # ChromaDB Configuration (now using Chroma Cloud)
    chroma_api_key: str
    chroma_tenant: str = "default-tenant"  # Default tenant ID
    chroma_database: str = "AutoStack"  # Default database name

    # Notification Services (Optional)
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None

    # Tavily Research Service (Optional)
    tavily_api_key: Optional[str] = None

    @property
    def chroma_url(self) -> str:
        """Return Chroma Cloud identifier for reference purposes"""
        return f"chroma-cloud://{self.chroma_tenant}/{self.chroma_database}"


# Global settings instance
settings = Settings()
