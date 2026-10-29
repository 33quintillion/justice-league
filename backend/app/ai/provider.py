"""Provider-independent LLM gateway.

The pipelines only see `LLMProvider.generate`, which takes a system prompt, user content and a JSON schema
and returns parsed JSON. The Anthropic implementation is the only one today; tests inject a fake provider.
Without credentials the gateway reports "not configured" rather than pretending to answer.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Protocol

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ProviderError(Exception):
    """The model could not produce a usable answer. The message is safe to show to users."""


class ProviderRefused(ProviderError):
    pass


@dataclass
class Generation:
    data: dict
    model: str
    request_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    served_by_fallback: bool = False
    raw_stop_reason: str = ""
    extra: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, *, system: str, user: str, schema: dict, max_tokens: int) -> Generation: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, *, timeout_s: float = 180.0, http_client=None) -> None:
        import anthropic

        self.model = model
        self._anthropic = anthropic
        kwargs = {"api_key": api_key, "timeout": timeout_s, "max_retries": 2}
        if http_client is not None:
            kwargs["http_client"] = http_client
        self.client = anthropic.Anthropic(**kwargs)

    def generate(self, *, system: str, user: str, schema: dict, max_tokens: int) -> Generation:
        a = self._anthropic
        try:
            # Structured outputs constrain the reply to the schema. `fallbacks: "default"` lets the API retry a
            # safety-classifier decline on Anthropic's recommended fallback model instead of failing outright.
            msg = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}, "effort": "medium"},
            )
        except a.AuthenticationError as e:
            raise ProviderError("The AI service rejected this server's credentials. An administrator needs to check the API key.") from e
        except a.RateLimitError as e:
            raise ProviderError("The AI service is busy right now. Please try again in a minute.") from e
        except a.APIConnectionError as e:  # includes timeouts
            raise ProviderError("We could not reach the AI service. Please try again shortly.") from e
        except a.APIStatusError as e:
            raise ProviderError(f"The AI service returned an error ({e.status_code}). Please try again later.") from e

        if msg.stop_reason == "refusal":
            raise ProviderRefused("The AI model declined to answer this request. Please rephrase it, or speak to a legal aid lawyer.")
        if msg.stop_reason == "max_tokens":
            raise ProviderError("The answer was cut off before it was complete, so we are not showing it. Please ask a narrower question.")
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ProviderError("The AI service returned a malformed answer, so we are not showing it.") from e
        iterations = getattr(msg.usage, "iterations", None) or []
        return Generation(
            data=data,
            model=msg.model,
            request_id=getattr(msg, "_request_id", None),
            input_tokens=getattr(msg.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(msg.usage, "output_tokens", 0) or 0,
            served_by_fallback=any(getattr(i, "type", "") == "fallback_message" for i in iterations),
            raw_stop_reason=msg.stop_reason or "",
        )


def provider_from_env() -> LLMProvider | None:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    return AnthropicProvider(key, os.getenv("JUSTICE_AI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
                             timeout_s=float(os.getenv("JUSTICE_AI_TIMEOUT_SECONDS", "180")))


def get_provider(app) -> LLMProvider | None:
    """Tests set app.state.ai_provider; otherwise the provider comes from the environment (cached)."""
    if hasattr(app.state, "ai_provider"):
        return app.state.ai_provider
    if not hasattr(app.state, "_env_ai_provider"):
        app.state._env_ai_provider = provider_from_env()
    return app.state._env_ai_provider
