# Module 1.2 — LLM Interface

## Purpose
Provides provider-agnostic LLM adapters (`AnthropicLLM`, `OpenAILLM`) that
satisfy the `LLMInterface` Protocol defined in Module 1.1's `base_agent.py`.
`BaseAgent` never imports this file directly — it only depends on the
`generate(prompt) -> str` shape, so any adapter here plugs in without
touching agent code.

## Files
- `llm_interface.py` — `AnthropicLLM`, `OpenAILLM`, `create_llm()` factory

## Key Responsibilities
1. Wrap each provider's SDK behind an identical `generate(prompt) -> str` method.
2. Resolve API keys safely (explicit param → environment variable → error),
   never hardcoded.
3. Convert provider-specific exceptions into a generic `RuntimeError`, so
   `BaseAgent`'s existing error handling (Module 1.1) works unchanged.
4. Offer a factory function (`create_llm`) so the rest of the project
   never hardcodes which provider class to import.

## Setup
Requires API keys as environment variables:
```bash
export ANTHROPIC_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
```
Install dependencies:
```bash
pip install anthropic openai
```

## Usage Example
```python
from agents.llm_interface import create_llm

llm = create_llm("anthropic", model="claude-sonnet-4-6")
response = llm.generate("Explain recursion in one sentence.")
```

## How to Test
```bash
pytest tests/test_llm_interface.py -v
```
All tests use mocked SDK clients — no real API calls or API keys needed
to run the test suite.

## Status
✅ Complete — 11/11 tests passing. Awaiting approval before Module 1.3
(Agent Memory).