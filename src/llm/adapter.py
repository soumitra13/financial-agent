"""
LLM provider protocol + factory.

The agent loop talks only to LLMAdapter — it never imports Ollama or OpenAI
directly, so swapping providers is a one-line config change.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class Message(dict):
    """A chat message: {"role": "user"|"assistant"|"system", "content": "..."}"""


class ToolCall:
    """Represents a tool call requested by the LLM."""

    def __init__(self, name: str, arguments: dict[str, Any], call_id: str = ""):
        self.name = name
        self.arguments = arguments
        self.call_id = call_id

    def __repr__(self) -> str:
        return f"ToolCall(name={self.name!r}, arguments={self.arguments})"


class LLMResponse:
    """Unified response from any LLM provider."""

    def __init__(
        self,
        content: str | None,
        tool_calls: list[ToolCall] | None = None,
        raw: dict[str, Any] | None = None,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.raw = raw or {}

    @property
    def is_tool_call(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_final_answer(self) -> bool:
        return not self.is_tool_call and self.content is not None

    def __repr__(self) -> str:
        if self.is_tool_call:
            return f"LLMResponse(tool_calls={self.tool_calls})"
        return f"LLMResponse(content={self.content!r:.80})"


@runtime_checkable
class LLMAdapter(Protocol):
    """Protocol every LLM backend must implement."""

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...


def get_llm_adapter() -> LLMAdapter:
    """
    Factory — returns the right adapter based on LLM_PROVIDER in .env.
    Imported lazily so unused providers don't need to be installed.
    """
    from src.config import get_settings

    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "mock":
        from src.llm.mock import MockAdapter
        return MockAdapter()
    elif provider == "ollama":
        from src.llm.ollama import OllamaAdapter
        return OllamaAdapter(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    elif provider == "openai":
        from src.llm.openai import OpenAIAdapter
        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    elif provider == "groq":
        from src.llm.groq import GroqAdapter
        return GroqAdapter(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use 'mock', 'ollama', 'openai', or 'groq'.")
