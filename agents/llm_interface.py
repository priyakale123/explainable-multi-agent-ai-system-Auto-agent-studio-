"""
llm_interface.py

Module 1.2 — LLM Interface
Provider-agnostic LLM adapters that satisfy the LLMInterface Protocol
defined in agents/base_agent.py. BaseAgent depends only on the
`generate(prompt) -> str` shape; it never imports or knows about
AnthropicLLM/OpenAILLM directly.

Concrete implementations:
    - AnthropicLLM  — wraps the Anthropic Python SDK
    - OpenAILLM     — wraps the OpenAI Python SDK

Factory:
    - create_llm(provider, **kwargs) -> LLMInterface
"""

from __future__ import annotations

import logging
import os

from anthropic import Anthropic, APIError as AnthropicAPIError
from openai import OpenAI, APIError as OpenAIAPIError

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Anthropic adapter
# --------------------------------------------------------------------------

class AnthropicLLM:
    """LLMInterface adapter for Anthropic's Claude models."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
    ) -> None:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Anthropic API key not found. Pass api_key= explicitly or "
                "set the ANTHROPIC_API_KEY environment variable."
            )
        self.client = Anthropic(api_key=resolved_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            # response.content is a list of content blocks; take the first
            # text block (defensive against future block types like tool_use)
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    return block.text
            raise RuntimeError("Anthropic response contained no text block")
        except AnthropicAPIError as exc:
            logger.exception("Anthropic API call failed")
            raise RuntimeError(f"Anthropic API call failed: {exc}") from exc


# --------------------------------------------------------------------------
# OpenAI adapter
# --------------------------------------------------------------------------

class OpenAILLM:
    """LLMInterface adapter for OpenAI's GPT models."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        max_tokens: int = 1024,
    ) -> None:
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "OpenAI API key not found. Pass api_key= explicitly or "
                "set the OPENAI_API_KEY environment variable."
            )
        self.client = OpenAI(api_key=resolved_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            choice = response.choices[0]
            content = choice.message.content
            if content is None:
                raise RuntimeError("OpenAI response contained no content")
            return content
        except OpenAIAPIError as exc:
            logger.exception("OpenAI API call failed")
            raise RuntimeError(f"OpenAI API call failed: {exc}") from exc


# --------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------

_PROVIDERS = {
    "anthropic": AnthropicLLM,
    "openai": OpenAILLM,
}


def create_llm(provider: str, **kwargs):
    """
    Instantiate an LLM adapter by provider name.

    Args:
        provider: "anthropic" or "openai"
        **kwargs: forwarded to the adapter's constructor
                  (api_key, model, max_tokens)

    Returns:
        An object satisfying the LLMInterface protocol (has .generate()).

    Raises:
        ValueError: if provider is not recognized.
    """
    try:
        adapter_cls = _PROVIDERS[provider]
    except KeyError:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available providers: {list(_PROVIDERS.keys())}"
        )
    return adapter_cls(**kwargs)