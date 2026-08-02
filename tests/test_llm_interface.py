"""
tests/test_llm_interface.py

Unit tests for Module 1.2 (LLM Interface) — agents/llm_interface.py.

No real network calls are made. The Anthropic/OpenAI SDK clients are
mocked so we can verify our adapter logic (key resolution, response
parsing, error wrapping) without needing real API keys.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from agents.llm_interface import AnthropicLLM, OpenAILLM, create_llm


# ==========================================================================
# API key resolution
# ==========================================================================

def test_anthropic_llm_uses_explicit_api_key():
    with patch("agents.llm_interface.Anthropic") as mock_client_cls:
        AnthropicLLM(api_key="explicit-key-123")
        mock_client_cls.assert_called_once_with(api_key="explicit-key-123")


def test_anthropic_llm_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-456")
    with patch("agents.llm_interface.Anthropic") as mock_client_cls:
        AnthropicLLM()
        mock_client_cls.assert_called_once_with(api_key="env-key-456")


def test_anthropic_llm_raises_without_any_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key not found"):
        AnthropicLLM()


def test_openai_llm_raises_without_any_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key not found"):
        OpenAILLM()


# ==========================================================================
# generate() — success paths (mocked SDK responses)
# ==========================================================================

def test_anthropic_generate_returns_text_block():
    with patch("agents.llm_interface.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_block = MagicMock(type="text", text="hello from claude")
        mock_client.messages.create.return_value = MagicMock(content=[mock_block])
        mock_client_cls.return_value = mock_client

        llm = AnthropicLLM(api_key="fake-key")
        result = llm.generate("hi")

        assert result == "hello from claude"
        mock_client.messages.create.assert_called_once()


def test_openai_generate_returns_message_content():
    with patch("agents.llm_interface.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "hello from gpt"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_client_cls.return_value = mock_client

        llm = OpenAILLM(api_key="fake-key")
        result = llm.generate("hi")

        assert result == "hello from gpt"


# ==========================================================================
# generate() — failure paths
# ==========================================================================

def test_anthropic_generate_wraps_api_error():
    from anthropic import APIError

    with patch("agents.llm_interface.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = APIError(
            "rate limited", request=MagicMock(), body=None
        )
        mock_client_cls.return_value = mock_client

        llm = AnthropicLLM(api_key="fake-key")
        with pytest.raises(RuntimeError, match="Anthropic API call failed"):
            llm.generate("hi")


def test_anthropic_generate_no_text_block_raises():
    with patch("agents.llm_interface.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_block = MagicMock(type="tool_use")  # no text block present
        mock_client.messages.create.return_value = MagicMock(content=[mock_block])
        mock_client_cls.return_value = mock_client

        llm = AnthropicLLM(api_key="fake-key")
        with pytest.raises(RuntimeError, match="no text block"):
            llm.generate("hi")


# ==========================================================================
# Factory function
# ==========================================================================

def test_create_llm_anthropic():
    with patch("agents.llm_interface.Anthropic"):
        llm = create_llm("anthropic", api_key="fake-key")
        assert isinstance(llm, AnthropicLLM)


def test_create_llm_openai():
    with patch("agents.llm_interface.OpenAI"):
        llm = create_llm("openai", api_key="fake-key")
        assert isinstance(llm, OpenAILLM)


def test_create_llm_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        create_llm("bogus-provider", api_key="fake-key")