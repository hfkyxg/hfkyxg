from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import litellm
from litellm import acompletion

from agent_framework.config.settings import settings
from agent_framework.core.errors import ProviderError
from agent_framework.core.messages import Message, ToolCall
from agent_framework.core.tool import ToolSpec

if TYPE_CHECKING:
    from agent_framework.core.persona import Persona

litellm.drop_params = True  # ignore unsupported params gracefully


@dataclass
class ProviderResponse:
    message: Message
    stop_reason: Literal["tool_calls", "end_turn", "max_tokens", "error"]
    raw: Any = None


class ModelProvider:
    def __init__(
        self,
        model: str,
        *,
        api_base: str | None = None,
        extra_params: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.model = model
        self.api_base = api_base
        self.extra_params = extra_params or {}
        self.temperature = temperature

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        lm = self._to_litellm_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": lm,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            **self.extra_params,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Inject API keys litellm needs from our settings
        if "anthropic/" in self.model or self.model.startswith("claude"):
            kwargs.setdefault("api_key", settings.anthropic_api_key or None)
        elif "openai/" in self.model or self.model.startswith("gpt"):
            kwargs.setdefault("api_key", settings.openai_api_key or None)
        elif "ollama/" in self.model:
            kwargs["api_base"] = self.api_base or settings.ollama_api_base

        try:
            resp = await acompletion(**kwargs)
        except Exception as exc:
            raise ProviderError(f"LLM call failed: {exc}") from exc

        return self._from_litellm_response(resp)

    def _to_litellm_messages(self, messages: list[Message]) -> list[dict]:
        out = []
        for m in messages:
            if m.role == "tool":
                for tr in m.tool_results:
                    out.append({
                        "role": "tool",
                        "tool_call_id": tr.tool_call_id,
                        "content": tr.content,
                    })
            elif m.tool_calls:
                out.append({
                    "role": "assistant",
                    "content": m.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in m.tool_calls
                    ],
                })
            else:
                d: dict[str, Any] = {"role": m.role, "content": m.content or ""}
                if m.name:
                    d["name"] = m.name
                out.append(d)
        return out

    def _from_litellm_response(self, resp: Any) -> ProviderResponse:
        choice = resp.choices[0]
        raw_msg = choice.message
        finish = choice.finish_reason or "stop"

        tool_calls: list[ToolCall] = []
        if getattr(raw_msg, "tool_calls", None):
            for tc in raw_msg.tool_calls:
                args = self._parse_args(tc.function.arguments, tc.function.name)
                tool_calls.append(ToolCall(
                    id=tc.id or uuid.uuid4().hex,
                    name=tc.function.name,
                    arguments=args,
                ))

        stop_reason: Literal["tool_calls", "end_turn", "max_tokens", "error"]
        if tool_calls or finish == "tool_calls":
            stop_reason = "tool_calls"
        elif finish == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        message = Message(
            role="assistant",
            content=getattr(raw_msg, "content", None),
            tool_calls=tool_calls,
        )
        return ProviderResponse(message=message, stop_reason=stop_reason, raw=resp)

    def _parse_args(self, raw: str | None, tool_name: str) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Try removing trailing commas and other common JSON issues
        cleaned = re.sub(r",\s*([}\]])", r"\1", raw.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # Last resort: extract first {...} or [...] block
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        raise ProviderError(f"Could not parse tool call arguments for '{tool_name}': {raw!r}")

    @classmethod
    def from_persona(cls, persona: Persona) -> ModelProvider:
        api_base: str | None = None
        if "ollama/" in persona.provider:
            api_base = settings.ollama_api_base
        return cls(model=persona.provider, api_base=api_base, temperature=persona.temperature)
