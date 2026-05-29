"""
Ollama LLM adapter.

Uses stdlib urllib with stream=false and no timeout — the model runs until
it finishes. Python 3.14 + asyncio + httpx deadlocks are avoided by running
the sync urllib call in a ThreadPoolExecutor.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.llm.adapter import LLMResponse, ToolCall

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ollama")


def _sync_chat(base_url: str, payload: dict) -> dict:
    """Blocking urllib POST — runs in a thread, zero asyncio involvement."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # timeout=None — no socket timeout, model runs until done
    with urllib.request.urlopen(req, timeout=None) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OllamaAdapter:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 800},
        }
        if tools:
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

        print(f"    [ollama] calling {self.model}...", flush=True)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(_executor, _sync_chat, self.base_url, payload)
        print("    [ollama] response received", flush=True)

        message = data.get("message", {})
        content = message.get("content") or None
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls = [
            ToolCall(
                name=tc["function"]["name"],
                arguments=tc["function"].get("arguments", {}),
                call_id=str(i),
            )
            for i, tc in enumerate(raw_tool_calls)
        ]

        return LLMResponse(content=content, tool_calls=tool_calls, raw=data)
