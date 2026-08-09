"""
Planner Models

Planner-specific structured data: a single PlanStep, the overall
PlannerExecutionPlan, and the exceptions PlannerAgent raises when a
generated plan fails validation.

Does not duplicate any model already defined in
agents/supervisor/supervisor_agent.py (AgentExecutionRecord,
ExecutionTrace, SupervisorResult, etc.) -- those remain Supervisor's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PlanValidationError(Exception):
    """
    Raised when a generated plan is structurally invalid: malformed
    JSON, missing fields, unknown agent names, or duplicate step IDs.
    """


class DependencyError(PlanValidationError):
    """
    Raised when a plan's step dependencies are invalid: a reference
    to a step ID that doesn't exist, or a circular dependency chain.
    """


@dataclass(slots=True)
class PlannerRequest:
    """Input to PlannerAgent: the user's task plus which agents exist."""

    user_task: Any
    available_agents: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PlanStep:
    """
    One step in a planner-generated execution plan.

    Attributes:
        step_id: unique identifier for this step (e.g. "step_1").
        agent_name: which registered agent should perform this step.
        instruction: what the agent should do (task/instruction text).
        depends_on: step_ids that must complete before this step runs.
        expected_output: brief description of what this step should produce.
        rationale: concise reason this agent/step was chosen -- for
            explainability. Must NOT contain hidden chain-of-thought,
            only a short, human-readable justification.
    """

    step_id: str
    agent_name: str
    instruction: str
    depends_on: list[str] = field(default_factory=list)
    expected_output: str = ""
    rationale: str = ""


@dataclass(slots=True)
class PlannerExecutionPlan:
    """
    A full plan produced by PlannerAgent: an ordered set of PlanSteps
    plus a concise overall rationale.
    """

    steps: list[PlanStep] = field(default_factory=list)
    reasoning: str = ""

    def ordered_agent_names(self) -> list[str]:
        """
        Return agent names in a valid execution order, resolved from
        each step's `depends_on` via topological sort.

        Raises:
            DependencyError: if a step depends on an unknown step_id,
                or if the dependency graph contains a cycle.
        """
        steps_by_id = {step.step_id: step for step in self.steps}

        for step in self.steps:
            for dep in step.depends_on:
                if dep not in steps_by_id:
                    raise DependencyError(
                        f"Step '{step.step_id}' depends on unknown step '{dep}'"
                    )

        visited: set[str] = set()
        in_progress: set[str] = set()
        ordered_ids: list[str] = []

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            if step_id in in_progress:
                raise DependencyError(
                    f"Circular dependency detected involving step '{step_id}'"
                )
            in_progress.add(step_id)
            for dep in steps_by_id[step_id].depends_on:
                visit(dep)
            in_progress.discard(step_id)
            visited.add(step_id)
            ordered_ids.append(step_id)

        for step in self.steps:
            visit(step.step_id)

        return [steps_by_id[step_id].agent_name for step_id in ordered_ids]