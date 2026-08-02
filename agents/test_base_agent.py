"""
test_base_agent.py

Unit tests for Module 1.1 (Agent Core).
Tests BaseAgent.run() through a minimal concrete subclass (EchoAgent)
combined with fake LLM/memory implementations. No real LLM calls,
no network I/O — everything here is pure Python.

Test cases correspond 1:1 to the table in agents/TESTING.md.
"""

import pytest

from agents.base_agent import BaseAgent, AgentResult


# --------------------------------------------------------------------------
# Fakes — satisfy the LLMInterface / AgentMemory Protocols structurally,
# no explicit inheritance needed.
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


class BrokenUpdateMemory(FakeMemory):
    def update_context(self, task, result) -> None:
        raise RuntimeError("memory write failed")


# --------------------------------------------------------------------------
# Minimal concrete subclass used purely for testing BaseAgent's skeleton.
# --------------------------------------------------------------------------

class EchoAgent(BaseAgent):
    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"

    def _parse_output(self, raw_output: str):
        return raw_output.upper()


class BrokenParseAgent(BaseAgent):
    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"

    def _parse_output(self, raw_output: str):
        raise ValueError("could not parse output")


class IncompleteAgent(BaseAgent):
    """Only implements one of the two required abstract methods."""

    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"
    # _parse_output intentionally NOT implemented


# --------------------------------------------------------------------------
# Test 1 — happy path
# --------------------------------------------------------------------------

def test_run_success():
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), FakeMemory())
    result = agent.run("hello")

    assert isinstance(result, AgentResult)
    assert result.success is True
    assert result.agent_name == "Echo"
    assert result.output == "FAKE RESPONSE TO: TASK: HELLO"
    assert result.error is None
    assert len(result.reasoning_log) == 4
    assert [s["step"] for s in result.reasoning_log] == [
        "received_task", "built_prompt", "llm_output", "final_result"
    ]


# --------------------------------------------------------------------------
# Test 2 — LLM failure is caught, not raised
# --------------------------------------------------------------------------

def test_run_failure_llm_error():
    agent = EchoAgent("Echo", "Repeats input", BrokenLLM(), FakeMemory())
    result = agent.run("hello")

    assert result.success is False
    assert result.output is None
    assert result.error == "API down"
    assert result.reasoning_log[-1]["step"] == "error"
    assert result.reasoning_log[-1]["content"] == "API down"


# --------------------------------------------------------------------------
# Test 3 — reasoning log resets between runs
# --------------------------------------------------------------------------

def test_reasoning_log_reset_between_runs():
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), FakeMemory())
    first = agent.run("task one")
    second = agent.run("task two")

    assert len(first.reasoning_log) == 4
    assert len(second.reasoning_log) == 4
    assert first.reasoning_log[0]["content"] == "task one"
    assert second.reasoning_log[0]["content"] == "task two"


# --------------------------------------------------------------------------
# Test 4 — reasoning steps are in the correct order
# --------------------------------------------------------------------------

def test_reasoning_log_step_order():
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), FakeMemory())
    result = agent.run("hello")

    steps = [s["step"] for s in result.reasoning_log]
    assert steps == ["received_task", "built_prompt", "llm_output", "final_result"]


# --------------------------------------------------------------------------
# Test 5 — memory context is actually passed into _build_prompt
# --------------------------------------------------------------------------

def test_memory_context_used_in_prompt():
    received_context = {}

    class ContextCheckingAgent(BaseAgent):
        def _build_prompt(self, task, context) -> str:
            received_context.update(context)
            return f"Task: {task}"

        def _parse_output(self, raw_output: str):
            return raw_output

    memory = FakeMemory()
    memory.context = {"history": ["previous task"]}
    agent = ContextCheckingAgent("Ctx", "desc", FakeLLM(), memory)
    agent.run("hello")

    assert received_context == {"history": ["previous task"]}


# --------------------------------------------------------------------------
# Test 6 — memory is updated exactly once after a successful run
# --------------------------------------------------------------------------

def test_memory_updated_after_run():
    memory = FakeMemory()
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), memory)
    agent.run("hello")

    assert len(memory.update_calls) == 1
    task, result = memory.update_calls[0]
    assert task == "hello"
    assert result == "FAKE RESPONSE TO: TASK: HELLO"


# --------------------------------------------------------------------------
# Test 7 — BaseAgent cannot be instantiated directly
# --------------------------------------------------------------------------

def test_cannot_instantiate_base_agent_directly():
    with pytest.raises(TypeError, match="abstract"):
        BaseAgent("X", "desc", FakeLLM(), FakeMemory())


# --------------------------------------------------------------------------
# Test 8 — subclass missing an abstract method still can't be instantiated
# --------------------------------------------------------------------------

def test_subclass_missing_abstract_method_fails():
    with pytest.raises(TypeError, match="abstract"):
        IncompleteAgent("X", "desc", FakeLLM(), FakeMemory())


# --------------------------------------------------------------------------
# Test 9 — error inside _parse_output is caught, not raised
# --------------------------------------------------------------------------

def test_parse_output_error_is_caught():
    agent = BrokenParseAgent("Broken", "desc", FakeLLM(), FakeMemory())
    result = agent.run("hello")

    assert result.success is False
    assert result.error == "could not parse output"
    assert result.reasoning_log[-1]["step"] == "error"


# --------------------------------------------------------------------------
# Test 10 — AgentResult dataclass equality works as expected
# --------------------------------------------------------------------------

def test_agent_result_is_dataclass_equality():
    r1 = AgentResult(agent_name="A", output="x", reasoning_log=[], success=True, error=None)
    r2 = AgentResult(agent_name="A", output="x", reasoning_log=[], success=True, error=None)
    r3 = AgentResult(agent_name="A", output="y", reasoning_log=[], success=True, error=None)

    assert r1 == r2
    assert r1 != r3


# --------------------------------------------------------------------------
# Bonus — failure scenario from TESTING.md \u00a75: parse succeeds but
# memory.update_context() fails afterward.
# --------------------------------------------------------------------------

def test_memory_update_failure_after_successful_parse():
    agent = EchoAgent("Echo", "Repeats input", FakeLLM(), BrokenUpdateMemory())
    result = agent.run("hello")

    assert result.success is False
    assert result.error == "memory write failed"
    # confirms parse succeeded before memory failed
    assert any(s["step"] == "llm_output" for s in result.reasoning_log)