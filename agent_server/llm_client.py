"""LLM API client for question generation.

Supports OpenAI-compatible APIs. Configured via environment variables:
- LLM_BASE_URL: API base URL
- LLM_API_KEY: API key
- LLM_MODEL: Model name
"""

import os
import httpx
from typing import Optional, List, Dict


class LLMClient:
    """Simple LLM client for OpenAI-compatible chat APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        self._available = bool(self.base_url)

    @property
    def available(self) -> bool:
        return self._available

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        max_tokens: int = 200,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat completion request.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            system_prompt: System-level instruction
            max_tokens: Max tokens in response
            temperature: Generation temperature

        Returns:
            The assistant's response text
        """
        if not self.available:
            raise RuntimeError("LLM client not configured (set LLM_BASE_URL)")

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        with httpx.Client(timeout=self.timeout) as client:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": full_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


# Singleton instance, lazily initialized
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> Optional[LLMClient]:
    """Get or create the LLM client singleton.

    Returns None if LLM is not configured.
    """
    global _llm_client
    if _llm_client is None:
        client = LLMClient()
        if client.available:
            _llm_client = client
        else:
            return None
    return _llm_client


def is_llm_available() -> bool:
    """Check if LLM integration is configured and available."""
    client = get_llm_client()
    return client is not None and client.available
