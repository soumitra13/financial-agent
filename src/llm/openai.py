"""
OpenAI LLM adapter.

Uses sync httpx in a thread executor — same pattern as ollama.py —
to avoid Python 3.14 async httpx deadlocks.
"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from src.llm.adapter import LLMResponse, ToolCall

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="openai")


def _sync_chat(api_key: str, model: str, payload: dict) -> dict:
    """Blocking httpx call — runs in a thread, safe from asyncio."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
    )
    response.raise_for_status()
    return response.json()


class OpenAIAdapter:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if tools:
            # Strip non-standard fields (e.g. "category") before sending
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            _executor, _sync_chat, self.api_key, self.model, payload
        )

        choice = data["choices"][0]["message"]
        content = choice.get("content")
        raw_tool_calls = choice.get("tool_calls") or []

        tool_calls = [
            ToolCall(
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"]["arguments"]),
                call_id=tc.get("id", str(i)),
            )
            for i, tc in enumerate(raw_tool_calls)
        ]

        return LLMResponse(content=content, tool_calls=tool_calls, raw=data)
