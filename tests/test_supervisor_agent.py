"""
tests/test_supervisor.py

Comprehensive unit tests for Module 2.1 (Supervisor Agent).

Uses MOCK agents (simple BaseAgent subclasses with scripted behavior)
-- never a real Planner/Research/Coding agent, since those are not
part of this module. No real LLM calls anywhere.
"""

from __future__ import annotations

from typing import Any

import pytest

from agents.base_agent import AgentResult, BaseAgent
from memory import MemoryManager
from agents.supervisor.supervisor_agent import (
    AgentExecutionStatus,
    AgentRegistry,
    RetryPolicy,
    SequentialExecutionStrategy,
    SequentialTaskRouter,
    SupervisorAgent,
)


# ==========================================================
# Mock agents
# ==========================================================

class FakeLLM:
    def generate(self, prompt: str) -> str:
        return f"generated: {prompt}"


class FakeMemory:
    def get_context(self) -> dict:
        return {}

    def update_context(self, task: Any, result: Any) -> None:
        pass


class AlwaysSucceedsAgent(BaseAgent):
    """Mock agent that always succeeds, echoing the task."""

    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"

    def _parse_output(self, raw_output: str):
        return raw_output


class AlwaysFailsAgent(BaseAgent):
    """Mock agent whose _parse_output always raises, forcing failure."""

    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"

    def _parse_output(self, raw_output: str):
        raise ValueError("simulated permanent failure")


class SucceedsOnSecondAttemptAgent(BaseAgent):
    """Mock agent that fails once, then succeeds -- for retry tests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._call_count = 0

    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"

    def _parse_output(self, raw_output: str):
        self._call_count += 1
        if self._call_count < 2:
            raise ValueError("transient failure")
        return raw_output


def make_agent(cls, name: str) -> BaseAgent:
    return cls(name, f"{name} description", FakeLLM(), FakeMemory())


# ==========================================================
# AgentRegistry
# ==========================================================

def test_agent_registry_register_and_get():
    registry = AgentRegistry()
    agent = make_agent(AlwaysSucceedsAgent, "Writer")
    registry.register(agent)

    assert registry.get("Writer") is agent
    assert "Writer" in registry
    assert registry.list_names() == ["Writer"]


def test_agent_registry_get_missing_returns_none():
    registry = AgentRegistry()
    assert registry.get("Nonexistent") is None


def test_agent_registry_unregister():
    registry = AgentRegistry()
    registry.register(make_agent(AlwaysSucceedsAgent, "Writer"))
    registry.unregister("Writer")

    assert registry.get("Writer") is None
    assert "Writer" not in registry


def test_agent_registry_register_overwrites():
    registry = AgentRegistry()
    first = make_agent(AlwaysSucceedsAgent, "Writer")
    second = make_agent(AlwaysSucceedsAgent, "Writer")
    registry.register(first)
    registry.register(second)

    assert registry.get("Writer") is second
    assert registry.list_names() == ["Writer"]  # not duplicated


# ==========================================================
# SequentialTaskRouter
# ==========================================================

def test_sequential_task_router_default_returns_all_in_order():
    router = SequentialTaskRouter()
    result = router.decide_agents("any task", ["A", "B", "C"])
    assert result == ["A", "B", "C"]


def test_sequential_task_router_explicit_order_filters_unavailable():
    router = SequentialTaskRouter(order=["C", "A", "Z"])
    result = router.decide_agents("any task", ["A", "B", "C"])
    assert result == ["C", "A"]  # Z dropped, order preserved


# ==========================================================
# SupervisorAgent -- registration
# ==========================================================

def test_supervisor_register_and_list_agents():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Critic"))

    assert supervisor.list_agents() == ["Writer", "Critic"]


def test_supervisor_unregister_agent():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))
    supervisor.unregister_agent("Writer")

    assert supervisor.list_agents() == []


# ==========================================================
# SupervisorAgent -- successful execution
# ==========================================================

def test_supervisor_run_success_single_agent():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))

    result = supervisor.run("hello")

    assert result.success is True
    assert result.outputs["Writer"] == "generated: Task: hello"
    assert len(result.execution_trace.records) == 1
    assert result.execution_trace.records[0].status == AgentExecutionStatus.SUCCESS


def test_supervisor_run_success_multiple_agents_sequential_order():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Critic"))

    result = supervisor.run("hello")

    names_in_order = [r.agent_name for r in result.execution_trace.records]
    assert names_in_order == ["Writer", "Critic"]


def test_supervisor_run_respects_explicit_agent_order():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Critic"))

    result = supervisor.run("hello", agent_order=["Critic", "Writer"])

    names_in_order = [r.agent_name for r in result.execution_trace.records]
    assert names_in_order == ["Critic", "Writer"]


# ==========================================================
# SupervisorAgent -- failure handling
# ==========================================================

def test_supervisor_run_records_agent_failure():
    supervisor = SupervisorAgent(
        memory_manager=MemoryManager(),
        retry_policy=RetryPolicy(max_retries=0),
    )
    supervisor.register_agent(make_agent(AlwaysFailsAgent, "Broken"))

    result = supervisor.run("hello")

    assert result.success is False
    assert result.execution_trace.records[0].status == AgentExecutionStatus.FAILED
    assert result.execution_trace.records[0].error == "simulated permanent failure"


def test_supervisor_run_missing_agent_is_skipped_not_crashed():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))

    result = supervisor.run("hello", agent_order=["Writer", "Nonexistent"])

    statuses = {r.agent_name: r.status for r in result.execution_trace.records}
    assert statuses["Writer"] == AgentExecutionStatus.SUCCESS
    assert statuses["Nonexistent"] == AgentExecutionStatus.SKIPPED
    assert result.success is False  # one agent skipped -> not fully successful


def test_supervisor_run_no_agents_registered():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    result = supervisor.run("hello")

    assert result.success is False
    assert result.execution_trace.records == []


# ==========================================================
# Retry mechanism
# ==========================================================

def test_supervisor_retries_and_recovers():
    supervisor = SupervisorAgent(
        memory_manager=MemoryManager(),
        retry_policy=RetryPolicy(max_retries=1, retry_on_failure=True),
    )
    supervisor.register_agent(make_agent(SucceedsOnSecondAttemptAgent, "Flaky"))

    result = supervisor.run("hello")

    assert result.success is True
    assert result.execution_trace.records[0].attempts == 2
    assert result.execution_trace.records[0].status == AgentExecutionStatus.SUCCESS


def test_supervisor_no_retry_when_disabled():
    supervisor = SupervisorAgent(
        memory_manager=MemoryManager(),
        retry_policy=RetryPolicy(max_retries=5, retry_on_failure=False),
    )
    supervisor.register_agent(make_agent(SucceedsOnSecondAttemptAgent, "Flaky"))

    result = supervisor.run("hello")

    assert result.success is False
    assert result.execution_trace.records[0].attempts == 1


def test_supervisor_exhausts_max_retries_on_permanent_failure():
    supervisor = SupervisorAgent(
        memory_manager=MemoryManager(),
        retry_policy=RetryPolicy(max_retries=2, retry_on_failure=True),
    )
    supervisor.register_agent(make_agent(AlwaysFailsAgent, "Broken"))

    result = supervisor.run("hello")

    assert result.success is False
    assert result.execution_trace.records[0].attempts == 3  # 1 initial + 2 retries


# ==========================================================
# Execution trace & reasoning log
# ==========================================================

def test_supervisor_reasoning_log_has_expected_steps():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))

    result = supervisor.run("hello")

    steps = [entry["step"] for entry in result.execution_trace.supervisor_reasoning]
    assert steps == [
        "received_task",
        "agents_selected",
        "execution_complete",
        "report_built",
        "stored_to_memory",
    ]


def test_supervisor_agent_execution_record_carries_agent_reasoning_log():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))

    result = supervisor.run("hello")

    agent_reasoning_steps = [
        entry["step"] for entry in result.execution_trace.records[0].reasoning_log
    ]
    assert agent_reasoning_steps == [
        "received_task", "built_prompt", "llm_output", "final_result"
    ]


def test_get_last_execution_trace_returns_most_recent_run():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))

    assert supervisor.get_last_execution_trace() is None
    result = supervisor.run("hello")

    assert supervisor.get_last_execution_trace() is result.execution_trace


# ==========================================================
# Memory integration
# ==========================================================

def test_supervisor_stores_result_in_memory_manager():
    memory_manager = MemoryManager()
    supervisor = SupervisorAgent(memory_manager=memory_manager, name="Sup1")
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))

    result = supervisor.run("hello")

    recent = memory_manager.get_recent("Sup1", n=1)
    assert len(recent) == 1
    assert recent[0].result == result.final_report
    assert recent[0].metadata["success"] is True


def test_supervisor_multiple_runs_accumulate_in_memory():
    memory_manager = MemoryManager()
    supervisor = SupervisorAgent(memory_manager=memory_manager, name="Sup1")
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))

    supervisor.run("task one")
    supervisor.run("task two")

    stats = memory_manager.get_statistics("Sup1")
    assert stats.total_entries == 2


# ==========================================================
# Final report
# ==========================================================

def test_final_report_contains_agent_names_and_status():
    supervisor = SupervisorAgent(memory_manager=MemoryManager())
    supervisor.register_agent(make_agent(AlwaysSucceedsAgent, "Writer"))
    supervisor.register_agent(make_agent(AlwaysFailsAgent, "Broken"))

    result = supervisor.run("hello")

    assert "Writer" in result.final_report
    assert "Broken" in result.final_report
    assert "FAILED" in result.final_report


# ==========================================================
# SequentialExecutionStrategy in isolation
# ==========================================================

def test_execution_strategy_runs_agents_in_given_order():
    strategy = SequentialExecutionStrategy()
    agents = [
        make_agent(AlwaysSucceedsAgent, "First"),
        make_agent(AlwaysSucceedsAgent, "Second"),
    ]

    records = strategy.run(agents, "hello", RetryPolicy())

    assert [r.agent_name for r in records] == ["First", "Second"]
    assert all(r.status == AgentExecutionStatus.SUCCESS for r in records) 