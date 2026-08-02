"""
tests/test_base_agent.py

Full pytest suite for Module 1.1 (Agent Core) — agents/base_agent.py.

Covers:
    - AgentResult dataclass behavior (defaults, equality)
    - Successful execution path
    - Failure handling (LLM error, memory error, invalid output parsing)
    - Abstract method enforcement
    - Reasoning log correctness (order, reset between runs)
    - Dependency wiring (memory get/update calls)

No real LLM calls or network I/O are made — all dependencies are fakes.
"""

import pytest

from agents.base_agent import BaseAgent, AgentResult


# --------------------------------------------------------------------------
# Fakes — satisfy LLMInterface / AgentMemory Protocols structurally.
# --------------------------------------------------------------------------

class FakeLLM:
    def generate(self, prompt: str) -> str:
        return f"fake response to: {prompt}"


class BrokenLLM:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("API down")


class FakeMemory:
    def __init__(self):
        self.context = {"history": []}
        self.update_calls = []

    def get_context(self) -> dict:
        return self.context

    def update_context(self, task, result) -> None:
        self.update_calls.append((task, result))


class BrokenGetContextMemory:
    def get_context(self) -> dict:
        raise RuntimeError("memory read failed")

    def update_context(self, task, result) -> None:
        pass


# --------------------------------------------------------------------------
# Minimal concrete subclasses used purely to exercise BaseAgent's skeleton.
# --------------------------------------------------------------------------

class EchoAgent(BaseAgent):
    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"

    def _parse_output(self, raw_output: str):
        return raw_output.upper()


class InvalidParsingAgent(BaseAgent):
    """Simulates an agent whose output-parsing logic rejects the LLM's
    raw output (e.g. expecting JSON and getting plain text)."""

    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"

    def _parse_output(self, raw_output: str):
        if not raw_output.startswith("fake"):
            raise ValueError(f"invalid output format: {raw_output!r}")
        raise ValueError("simulated invalid output parsing")


class MissingParseOutputAgent(BaseAgent):
    """Implements only _build_prompt — _parse_output is left out."""

    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"


class MissingBuildPromptAgent(BaseAgent):
    """Implements only _parse_output — _build_prompt is left out."""

    def _parse_output(self, raw_output: str):
        return raw_output


# ==========================================================================
# 1-2. AgentResult dataclass
# ==========================================================================

def test_agent_result_default_values():
    result = AgentResult(agent_name="A", output="x", reasoning_log=[])
    assert result.success is True
    assert result.error is None


def test_agent_result_equality():
    r1 = AgentResult(agent_name="A", output="x", reasoning_log=[], success=True, error=None)
    r2 = AgentResult(agent_name="A", output="x", reasoning_log=[], success=True, error=None)
    r3 = AgentResult(agent_name="A", output="y", reasoning_log=[], success=True, error=None)

    assert r1 == r2
    assert r1 != r3


# ==========================================================================
# 3-4. Successful execution
# ==========================================================================

def test_run_success_returns_agent_result():
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), FakeMemory())
    result = agent.run("hello")

    assert isinstance(result, AgentResult)
    assert result.success is True
    assert result.agent_name == "Echo"
    assert result.output == "FAKE RESPONSE TO: TASK: HELLO"
    assert result.error is None


def test_run_records_reasoning_steps_in_order():
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), FakeMemory())
    result = agent.run("hello")

    steps = [entry["step"] for entry in result.reasoning_log]
    assert steps == ["received_task", "built_prompt", "llm_output", "final_result"]


def test_run_calls_memory_get_and_update():
    memory = FakeMemory()
    memory.context = {"history": ["previous task"]}
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), memory)
    agent.run("hello")

    assert len(memory.update_calls) == 1
    task, result_value = memory.update_calls[0]
    assert task == "hello"
    assert result_value == "FAKE RESPONSE TO: TASK: HELLO"


# ==========================================================================
# 5-6-7. Failure handling
# ==========================================================================

def test_run_failure_on_llm_exception():
    agent = EchoAgent("Echo", "Repeats input", BrokenLLM(), FakeMemory())
    result = agent.run("hello")

    assert result.success is False
    assert result.output is None
    assert result.error == "API down"
    assert result.reasoning_log[-1]["step"] == "error"


def test_run_failure_on_memory_get_context_exception():
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), BrokenGetContextMemory())
    result = agent.run("hello")

    assert result.success is False
    assert result.error == "memory read failed"
    assert result.reasoning_log[-1]["step"] == "error"


def test_run_failure_on_invalid_output_parsing():
    agent = InvalidParsingAgent("Invalid", "Rejects bad output", FakeLLM(), FakeMemory())
    result = agent.run("hello")

    assert result.success is False
    assert result.output is None
    assert result.error == "simulated invalid output parsing"
    assert result.reasoning_log[-1]["step"] == "error"
    # confirms the LLM call itself succeeded before parsing failed
    assert any(entry["step"] == "llm_output" for entry in result.reasoning_log)


# ==========================================================================
# 8. Reasoning log resets between runs
# ==========================================================================

def test_reasoning_log_resets_between_runs():
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), FakeMemory())
    first = agent.run("task one")
    second = agent.run("task two")

    assert len(first.reasoning_log) == 4
    assert len(second.reasoning_log) == 4
    assert first.reasoning_log[0]["content"] == "task one"
    assert second.reasoning_log[0]["content"] == "task two"


# ==========================================================================
# 9-10-11. Abstract method enforcement
# ==========================================================================

def test_cannot_instantiate_base_agent_directly():
    with pytest.raises(TypeError, match="abstract"):
        BaseAgent("X", "desc", FakeLLM(), FakeMemory())


def test_subclass_missing_parse_output_fails():
    with pytest.raises(TypeError, match="abstract"):
        MissingParseOutputAgent("X", "desc", FakeLLM(), FakeMemory())


def test_subclass_missing_build_prompt_fails():
    with pytest.raises(TypeError, match="abstract"):
        MissingBuildPromptAgent("X", "desc", FakeLLM(), FakeMemory())