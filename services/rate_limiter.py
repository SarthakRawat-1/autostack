"""
Rate Limiter for LLM API Calls

This module implements a shared token bucket rate limiter for API requests.
Prevents hitting rate limits by throttling requests across all agents.

Ported from the old version (autostack/autostack/services/llm_client.py)
"""

import asyncio
import time
from typing import Dict
from threading import Lock


# Global rate limiter instances to share across clients by service type
_groq_rate_limiters: Dict[str, 'SharedRateLimiter'] = {}
_openrouter_rate_limiters: Dict[str, 'SharedRateLimiter'] = {}
_global_lock = Lock()


class SharedRateLimiter:
    """
    Shared token bucket rate limiter for API requests

    This is a singleton-style rate limiter that shares state across all clients
    that use the same identifier (e.g., same API key).

    Attributes:
        requests_per_minute: Maximum requests allowed per minute
        tokens: Current available tokens
        last_update: Timestamp of last token refill
    """

    def __init__(self, identifier: str, requests_per_minute: int = 20):
        """
        Initialize rate limiter

        Args:
            identifier: Unique identifier for this rate limiter (e.g., hashed API key)
            requests_per_minute: Maximum requests per minute
        """
        self.identifier = identifier
        self.requests_per_minute = requests_per_minute
        self.tokens = float(requests_per_minute)  # Start with full capacity
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire a token for making a request

        Blocks until a token is available.
        """
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.requests_per_minute,
                self.tokens + (elapsed * self.requests_per_minute / 60.0)
            )
            self.last_update = now

            # Wait if no tokens available
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) * 60.0 / self.requests_per_minute
                await asyncio.sleep(wait_time)
                # Refill tokens after waiting
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(
                    self.requests_per_minute,
                    self.tokens + (elapsed * self.requests_per_minute / 60.0)
                )
                self.last_update = now

            self.tokens -= 1.0


def get_groq_rate_limiter(api_key: str, requests_per_minute: int = 30) -> SharedRateLimiter:
    """
    Get shared rate limiter for Groq API key

    Args:
        api_key: Groq API key (hashed for privacy)
        requests_per_minute: Maximum requests per minute (default 30 for free tier)

    Returns:
        Shared rate limiter instance
    """
    # Hash the API key to use as identifier (without exposing the actual key)
    identifier = f"groq_{hash(api_key) % 1000000}"

    with _global_lock:
        if identifier not in _groq_rate_limiters:
            _groq_rate_limiters[identifier] = SharedRateLimiter(identifier, requests_per_minute)
        return _groq_rate_limiters[identifier]


def get_openrouter_rate_limiter(api_key: str, requests_per_minute: int = 20) -> SharedRateLimiter:
    """
    Get shared rate limiter for OpenRouter API key

    Args:
        api_key: OpenRouter API key (hashed for privacy)
        requests_per_minute: Maximum requests per minute

    Returns:
        Shared rate limiter instance
    """
    identifier = f"openrouter_{hash(api_key) % 1000000}"

    with _global_lock:
        if identifier not in _openrouter_rate_limiters:
            _openrouter_rate_limiters[identifier] = SharedRateLimiter(identifier, requests_per_minute)
        return _openrouter_rate_limiters[identifier]


class RateLimiter:
    """
    Rate limiter for LLM clients

    Uses shared rate limiting across all clients with the same API key.
    """

    def __init__(self, api_key: str, service_type: str = "groq", requests_per_minute: int = 30):
        """
        Initialize rate limiter with shared state

        Args:
            api_key: API key (used to identify shared limiter)
            service_type: Service type ("openrouter" or "groq")
            requests_per_minute: Maximum requests per minute
        """
        if service_type.lower() == "groq":
            self.shared_limiter = get_groq_rate_limiter(api_key, requests_per_minute)
        else:  # openrouter
            self.shared_limiter = get_openrouter_rate_limiter(api_key, requests_per_minute)

    async def acquire(self) -> None:
        """
        Acquire a token for making a request
        """
        await self.shared_limiter.acquire()
