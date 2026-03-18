"""
Provides factory functions for creating LangChain chat models
for OpenRouter and Groq providers.
"""

from typing import Optional
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from api.config import settings


def get_groq_llm(
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    max_retries: int = 3,
    model: Optional[str] = None
) -> ChatGroq:
    return ChatGroq(
        model=model or settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )


def get_openrouter_llm(
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    max_retries: int = 3,
    model: Optional[str] = None
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model or settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        default_headers={
            "HTTP-Referer": "https://github.com/autostack",
            "X-Title": "AutoStack"
        }
    )


def get_code_llm(
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
):
    """Get LLM optimized for code generation (Developer and QA agents)"""
    return get_groq_llm(
        model=settings.groq_model,  # Qwen model for code generation
        temperature=temperature,
        max_tokens=max_tokens
    )

def get_non_code_llm(
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
):
    """Get LLM optimized for non-code tasks (PM and Documentation agents)"""
    return get_groq_llm(
        model=settings.groq_non_code_model,  # Specialized model for non-code tasks (e.g., Llama)
        temperature=temperature,
        max_tokens=max_tokens
    )
