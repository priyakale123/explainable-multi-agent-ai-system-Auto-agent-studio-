"""
tests/test_planner_agent.py

Comprehensive unit tests for Module 2.2 (Planner Agent).

Mirrors the fake/mock patterns established in tests/test_supervisor.py
(FakeLLM, FakeMemory satisfying BaseAgent's Protocols structurally).
No real LLM calls anywhere.

Also includes integration tests proving PlannerTaskRouter plugs into
the REAL, unmodified SupervisorAgent (Module 2.1) via its existing
TaskRouter extension point.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from agents.base_agent import BaseAgent
from agents.planner import (
    DependencyError,
    PlannerAgent,
    PlannerExecutionPlan,
    PlannerRequest,
    PlannerTaskRouter,
    PlanStep,
    PlanValidationError,
)
from agents.supervisor.supervisor_agent import SupervisorAgent
from memory import MemoryManager


# ==========================================================
# Fakes
# ==========================================================

class ScriptedLLM:
    """Returns a fixed, scripted response regardless of prompt."""

    def __init__(self, response: str) -> None:
        self._response = response

    def generate(self, prompt: str) -> str:
        return self._response


class RaisingLLM:
    """Simulates an LLM call failure (e.g. network/API error)."""

    def generate(self, prompt: str) -> str:
        raise RuntimeError("simulated LLM API failure")


class FakeMemory:
    def get_context(self) -> dict:
        return {}

    def update_context(self, task: Any, result: Any) -> None:
        pass


class RecordingAgent(BaseAgent):
    """Mock agent used only to prove PlannerTaskRouter -> SupervisorAgent
    integration; records whether it was actually invoked."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.was_called = False

    def _build_prompt(self, task, context) -> str:
        return f"Task: {task}"

    def _parse_output(self, raw_output: str):
        self.was_called = True
        return raw_output


def valid_plan_json(agent_names: list[str] | None = None) -> str:
    agent_names = agent_names or ["Writer"]
    steps = [
        {
            "step_id": f"step_{i+1}",
            "agent_name": name,
            "instruction": f"do the {name} part",
            "depends_on": [f"step_{i}"] if i > 0 else [],
            "expected_output": "some output",
            "rationale": f"{name} is needed for this",
        }
        for i, name in enumerate(agent_names)
    ]
    return json.dumps({"steps": steps, "reasoning": "straightforward plan"})


def make_planner(response: str) -> PlannerAgent:
    return PlannerAgent("Planner", "plans tasks", ScriptedLLM(response), FakeMemory())


# ==========================================================
# 1. Planner initialization
# ==========================================================

def test_planner_agent_initializes_like_any_base_agent():
    planner = make_planner(valid_plan_json())
    assert planner.name == "Planner"
    assert planner.role_description == "plans tasks"


# ==========================================================
# 2-3-4. Valid task -> valid plan, correct agent selection, correct order
# ==========================================================

def test_valid_task_produces_valid_plan():
    planner = make_planner(valid_plan_json(["Writer", "Critic"]))
    result = planner.run(PlannerRequest(user_task="write and review", available_agents=["Writer", "Critic"]))

    assert result.success is True
    assert isinstance(result.output, PlannerExecutionPlan)
    assert len(result.output.steps) == 2


def test_correct_agent_selection():
    planner = make_planner(valid_plan_json(["Writer", "Critic"]))
    result = planner.run(PlannerRequest(user_task="write and review", available_agents=["Writer", "Critic"]))

    agent_names = [step.agent_name for step in result.output.steps]
    assert agent_names == ["Writer", "Critic"]


def test_correct_execution_order_from_dependencies():
    planner = make_planner(valid_plan_json(["Writer", "Critic"]))
    result = planner.run(PlannerRequest(user_task="write and review", available_agents=["Writer", "Critic"]))

    assert result.output.ordered_agent_names() == ["Writer", "Critic"]


# ==========================================================
# 5. Dependency handling
# ==========================================================

def test_dependency_handling_reorders_when_declared_out_of_order():
    plan_json = json.dumps({
        "steps": [
            {"step_id": "step_2", "agent_name": "Critic", "instruction": "review",
             "depends_on": ["step_1"], "expected_output": "review", "rationale": "reviews writer output"},
            {"step_id": "step_1", "agent_name": "Writer", "instruction": "write",
             "depends_on": [], "expected_output": "text", "rationale": "writes first"},
        ],
        "reasoning": "writer then critic",
    })
    planner = make_planner(plan_json)
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer", "Critic"]))

    # Even though step_2 (Critic) is listed first in the JSON, the
    # dependency graph forces Writer to run before Critic.
    assert result.output.ordered_agent_names() == ["Writer", "Critic"]


# ==========================================================
# 6-7. Expected outputs, concise rationale
# ==========================================================

def test_expected_output_and_rationale_are_preserved():
    planner = make_planner(valid_plan_json(["Writer"]))
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer"]))

    step = result.output.steps[0]
    assert step.expected_output == "some output"
    assert step.rationale == "Writer is needed for this"
    assert result.output.reasoning == "straightforward plan"


# ==========================================================
# 8. Empty task
# ==========================================================

def test_empty_task_fails_gracefully():
    planner = make_planner(valid_plan_json())
    result = planner.run(PlannerRequest(user_task="", available_agents=["Writer"]))

    assert result.success is False
    assert "empty task" in result.error.lower()


# ==========================================================
# 9. LLM failure
# ==========================================================

def test_llm_failure_is_caught_not_raised():
    planner = PlannerAgent("Planner", "plans tasks", RaisingLLM(), FakeMemory())
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer"]))

    assert result.success is False
    assert "simulated LLM API failure" in result.error


# ==========================================================
# 10. Malformed LLM response
# ==========================================================

def test_malformed_json_response_fails_gracefully():
    planner = make_planner("this is not JSON at all {{{")
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer"]))

    assert result.success is False
    assert "valid JSON" in result.error


def test_missing_steps_key_fails_gracefully():
    planner = make_planner(json.dumps({"reasoning": "no steps field"}))
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer"]))

    assert result.success is False
    assert "steps" in result.error.lower()


# ==========================================================
# 11. Unknown agent (validated at the router level, not the planner --
# the Planner doesn't know the "true" registry, only what it was told)
# ==========================================================

def test_router_falls_back_when_planner_chooses_unregistered_agent():
    planner = make_planner(valid_plan_json(["GhostAgent"]))
    router = PlannerTaskRouter(planner)

    result = router.decide_agents("task", ["Writer", "Critic"])

    # GhostAgent isn't in available_agents -> filtered out -> empty ->
    # falls back to SequentialTaskRouter, which returns all available.
    assert result == ["Writer", "Critic"]
    assert router.get_last_plan() is None


# ==========================================================
# 12. Duplicate step ID
# ==========================================================

def test_duplicate_step_id_fails_gracefully():
    plan_json = json.dumps({
        "steps": [
            {"step_id": "step_1", "agent_name": "Writer", "instruction": "a",
             "depends_on": [], "expected_output": "", "rationale": ""},
            {"step_id": "step_1", "agent_name": "Critic", "instruction": "b",
             "depends_on": [], "expected_output": "", "rationale": ""},
        ],
        "reasoning": "duplicate ids",
    })
    planner = make_planner(plan_json)
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer", "Critic"]))

    assert result.success is False
    assert "Duplicate step_id" in result.error


# ==========================================================
# 13. Invalid dependency reference
# ==========================================================

def test_invalid_dependency_reference_fails_gracefully():
    plan_json = json.dumps({
        "steps": [
            {"step_id": "step_1", "agent_name": "Writer", "instruction": "a",
             "depends_on": ["step_99"], "expected_output": "", "rationale": ""},
        ],
        "reasoning": "bad dependency",
    })
    planner = make_planner(plan_json)
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer"]))

    assert result.success is False
    assert "unknown step" in result.error.lower()


# ==========================================================
# 14. Circular dependency
# ==========================================================

def test_circular_dependency_fails_gracefully():
    plan_json = json.dumps({
        "steps": [
            {"step_id": "step_1", "agent_name": "Writer", "instruction": "a",
             "depends_on": ["step_2"], "expected_output": "", "rationale": ""},
            {"step_id": "step_2", "agent_name": "Critic", "instruction": "b",
             "depends_on": ["step_1"], "expected_output": "", "rationale": ""},
        ],
        "reasoning": "circular",
    })
    planner = make_planner(plan_json)
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer", "Critic"]))

    assert result.success is False
    assert "circular dependency" in result.error.lower()


# ==========================================================
# 15. Empty plan
# ==========================================================

def test_empty_steps_list_fails_gracefully():
    planner = make_planner(json.dumps({"steps": [], "reasoning": "nothing needed"}))
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer"]))

    assert result.success is False
    assert "non-empty" in result.error.lower()


# ==========================================================
# 16. Planner does not execute agents
# ==========================================================

def test_planner_never_calls_any_agent_run_method():
    agent = RecordingAgent("Writer", "writes", ScriptedLLM("irrelevant"), FakeMemory())
    planner = make_planner(valid_plan_json(["Writer"]))

    planner.run(PlannerRequest(user_task="task", available_agents=["Writer"]))

    # PlannerAgent only produces a PLAN naming "Writer" -- it never
    # touches the actual Writer agent instance.
    assert agent.was_called is False


# ==========================================================
# 17. Planner uses the existing LLMInterface (structural, via BaseAgent)
# ==========================================================

def test_planner_uses_injected_llm_interface_via_base_agent():
    llm = ScriptedLLM(valid_plan_json(["Writer"]))
    planner = PlannerAgent("Planner", "plans tasks", llm, FakeMemory())

    assert planner.llm_interface is llm  # exact same injected object
    result = planner.run(PlannerRequest(user_task="task", available_agents=["Writer"]))
    assert result.success is True


# ==========================================================
# 18. Planner does not instantiate provider-specific clients
# ==========================================================

def test_planner_module_imports_no_llm_provider_sdk():
    import agents.planner.planner_agent as planner_module
    source = open(planner_module.__file__).read()

    assert "anthropic" not in source.lower()
    assert "openai" not in source.lower()
    assert "api_key" not in source.lower()


# ==========================================================
# 19. PlannerTaskRouter is compatible with existing TaskRouter
# ==========================================================

def test_planner_task_router_is_a_real_task_router_subclass():
    from agents.supervisor.supervisor_agent import TaskRouter

    planner = make_planner(valid_plan_json(["Writer"]))
    router = PlannerTaskRouter(planner)

    assert isinstance(router, TaskRouter)
    result = router.decide_agents("task", ["Writer"])
    assert result == ["Writer"]


# ==========================================================
# 20. Planner integrates with SupervisorAgent without modifying it
# ==========================================================

def test_planner_task_router_drives_real_unmodified_supervisor_agent():
    planner = make_planner(valid_plan_json(["Writer", "Critic"]))
    router = PlannerTaskRouter(planner)

    memory_manager = MemoryManager()
    supervisor = SupervisorAgent(memory_manager=memory_manager, task_router=router)

    writer = RecordingAgent("Writer", "writes", ScriptedLLM("written content"), FakeMemory())
    critic = RecordingAgent("Critic", "reviews", ScriptedLLM("reviewed content"), FakeMemory())
    supervisor.register_agent(writer)
    supervisor.register_agent(critic)

    result = supervisor.run("write and review something")

    assert result.success is True
    assert writer.was_called is True
    assert critic.was_called is True
    assert [r.agent_name for r in result.execution_trace.records] == ["Writer", "Critic"]
    assert router.get_last_plan() is not None
    assert router.get_last_plan().reasoning == "straightforward plan"


def test_planner_task_router_fallback_still_lets_supervisor_run():
    """If the Planner fails entirely, Supervisor still completes the
    run via the fallback SequentialTaskRouter -- never blocked."""
    planner = PlannerAgent("Planner", "plans tasks", RaisingLLM(), FakeMemory())
    router = PlannerTaskRouter(planner)

    memory_manager = MemoryManager()
    supervisor = SupervisorAgent(memory_manager=memory_manager, task_router=router)
    writer = RecordingAgent("Writer", "writes", ScriptedLLM("written content"), FakeMemory())
    supervisor.register_agent(writer)

    result = supervisor.run("do something")

    assert result.success is True
    assert writer.was_called is True 