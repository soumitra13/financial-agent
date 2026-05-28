"""
Groq LLM adapter.

Groq exposes an OpenAI-compatible REST API, so the payload format is identical
to OpenAI. Tool-call arguments arrive as a JSON *string* and must be parsed.

Uses httpx (already in project deps) with a proper User-Agent so Cloudflare
does not block the request (raw urllib without User-Agent gets CF error 1010).
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from src.llm.adapter import LLMResponse, ToolCall

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# httpx client reused across calls (connection pooling)
_client = httpx.AsyncClient(
    timeout=60.0,
    headers={
        "User-Agent": "financial-agent/1.0 (httpx)",
    },
)


class GroqAdapter:
    """
    Groq cloud LLM adapter.

    Recommended models (free tier):
      - llama-3.3-70b-versatile   — best tool-calling accuracy
      - llama-3.1-8b-instant      — fastest, good for simple tasks
      - mixtral-8x7b-32768        — large context window
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key.strip()   # strip CRLF/whitespace from env file
        self.model = model.strip()

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 1024,
            "stream": False,
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
            payload["tool_choice"] = "auto"

        print(f"    [groq] calling {self.model}...", flush=True)

        try:
            response = await _client.post(
                GROQ_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = e.response.text
            print(f"    [groq] HTTP {e.response.status_code} — {body}", flush=True)
            raise RuntimeError(f"Groq API error {e.response.status_code}: {body}") from e

        print(f"    [groq] response received", flush=True)
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or None
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", "{}")
            # Groq (like OpenAI) returns arguments as a JSON string — parse it
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
            else:
                args = raw_args

            tool_calls.append(
                ToolCall(
                    name=fn.get("name", ""),
                    arguments=args,
                    call_id=tc.get("id", ""),
                )
            )

        return LLMResponse(content=content, tool_calls=tool_calls, raw=data)
