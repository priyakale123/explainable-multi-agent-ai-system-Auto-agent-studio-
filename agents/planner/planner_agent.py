"""
Planner Agent

PlannerAgent analyzes a user task using the existing LLMInterface
(Module 1.2, injected via BaseAgent's constructor -- Module 1.1) and
produces a structured PlannerExecutionPlan: which registered agents
are needed, in what order, with a concise rationale per step.

PlannerAgent does NOT execute agents, does NOT implement retries, and
does NOT register agents -- those remain SupervisorAgent's
responsibility (Module 2.1), untouched by this module.

PlannerTaskRouter adapts PlannerAgent to the EXISTING TaskRouter
abstraction defined in agents/supervisor/supervisor_agent.py, so it
can be injected into SupervisorAgent exactly like SequentialTaskRouter
-- zero changes to SupervisorAgent required.

Author: Priyanka Kale
Project: AutoAgent Studio -- Explainable Multi-Agent AI Platform
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from agents.planner.planner_models import (
    DependencyError,
    PlannerExecutionPlan,
    PlannerRequest,
    PlanStep,
    PlanValidationError,
)
from agents.planner.prompt_templates import build_planning_prompt
from agents.supervisor.supervisor_agent import SequentialTaskRouter, TaskRouter

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """
    LLM-driven task planner.

    Extends the EXISTING BaseAgent (Module 1.1) unchanged -- inherits
    its real __init__(name, role_description, llm_interface, memory)
    and its real run() template method, including reasoning-log
    capture and fault-isolated error handling. Only _build_prompt and
    _parse_output are implemented here, as BaseAgent's contract requires.

    task passed to run() must be a PlannerRequest.
    """

    def _build_prompt(self, task: PlannerRequest, context: dict[str, Any]) -> str:
        if not isinstance(task, PlannerRequest):
            raise PlanValidationError(
                f"PlannerAgent requires a PlannerRequest, got {type(task).__name__}"
            )
        if not str(task.user_task).strip():
            raise PlanValidationError("Cannot plan for an empty task")
        return build_planning_prompt(task.user_task, task.available_agents)

    def _parse_output(self, raw_output: str) -> PlannerExecutionPlan:
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise PlanValidationError(f"Planner LLM did not return valid JSON: {exc}") from exc

        if not isinstance(parsed, dict) or "steps" not in parsed:
            raise PlanValidationError("Planner JSON missing required 'steps' key")

        raw_steps = parsed["steps"]
        if not isinstance(raw_steps, list) or len(raw_steps) == 0:
            raise PlanValidationError("Planner JSON 'steps' must be a non-empty list")

        steps: list[PlanStep] = []
        seen_step_ids: set[str] = set()

        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                raise PlanValidationError("Each step must be a JSON object")

            step_id = raw_step.get("step_id")
            agent_name = raw_step.get("agent_name")
            instruction = raw_step.get("instruction", "")

            if not isinstance(step_id, str) or not step_id:
                raise PlanValidationError("Each step requires a non-empty string 'step_id'")
            if step_id in seen_step_ids:
                raise PlanValidationError(f"Duplicate step_id: '{step_id}'")
            seen_step_ids.add(step_id)

            if not isinstance(agent_name, str) or not agent_name:
                raise PlanValidationError(
                    f"Step '{step_id}' requires a non-empty string 'agent_name'"
                )

            depends_on = raw_step.get("depends_on", [])
            if not isinstance(depends_on, list) or not all(isinstance(d, str) for d in depends_on):
                raise PlanValidationError(
                    f"Step '{step_id}' field 'depends_on' must be a list of strings"
                )

            steps.append(
                PlanStep(
                    step_id=step_id,
                    agent_name=agent_name,
                    instruction=str(instruction),
                    depends_on=depends_on,
                    expected_output=str(raw_step.get("expected_output", "")),
                    rationale=str(raw_step.get("rationale", "")),
                )
            )

        reasoning = parsed.get("reasoning", "")
        if not isinstance(reasoning, str):
            reasoning = str(reasoning)

        plan = PlannerExecutionPlan(steps=steps, reasoning=reasoning)

        # Validate dependency graph eagerly (raises DependencyError on
        # unknown references or cycles) so a broken plan is caught here,
        # inside BaseAgent.run()'s try/except, rather than surfacing
        # later inside PlannerTaskRouter or SupervisorAgent.
        plan.ordered_agent_names()

        return plan


class PlannerTaskRouter(TaskRouter):
    """
    TaskRouter implementation backed by an LLM-driven PlannerAgent.

    Satisfies the EXISTING TaskRouter.decide_agents(task,
    available_agents) -> list[str] contract from
    agents/supervisor/supervisor_agent.py exactly -- SupervisorAgent
    cannot tell this apart from SequentialTaskRouter.

    Falls back to `fallback_router` (SequentialTaskRouter by default)
    whenever planning fails for any reason, so SupervisorAgent is
    never blocked by a broken plan.
    """

    def __init__(
        self,
        planner_agent: PlannerAgent,
        fallback_router: TaskRouter | None = None,
    ) -> None:
        self._planner_agent = planner_agent
        self._fallback_router = fallback_router or SequentialTaskRouter()
        self._last_plan: PlannerExecutionPlan | None = None

    def decide_agents(self, task: Any, available_agents: list[str]) -> list[str]:
        request = PlannerRequest(user_task=task, available_agents=available_agents)
        result = self._planner_agent.run(request)

        if not result.success:
            logger.warning(
                "PlannerAgent failed (%s) -- falling back to %s",
                result.error, type(self._fallback_router).__name__,
            )
            self._last_plan = None
            return self._fallback_router.decide_agents(task, available_agents)

        plan: PlannerExecutionPlan = result.output

        try:
            ordered_names = plan.ordered_agent_names()
        except DependencyError as exc:
            logger.warning(
                "PlannerAgent produced an invalid dependency graph (%s) -- falling back to %s",
                exc, type(self._fallback_router).__name__,
            )
            self._last_plan = None
            return self._fallback_router.decide_agents(task, available_agents)

        available_set = set(available_agents)
        valid_names = [name for name in ordered_names if name in available_set]

        if not valid_names:
            logger.warning(
                "PlannerAgent chose no valid registered agents -- falling back to %s",
                type(self._fallback_router).__name__,
            )
            self._last_plan = None
            return self._fallback_router.decide_agents(task, available_agents)

        self._last_plan = plan
        logger.info(
            "PlannerAgent selected agents: %s | reasoning: %s", valid_names, plan.reasoning
        )
        return valid_names

    def get_last_plan(self) -> PlannerExecutionPlan | None:
        """
        Return the most recent successful PlannerExecutionPlan (with
        per-step and overall rationale), or None if the last
        decide_agents() call fell back.

        Not part of the TaskRouter interface -- an additive method for
        callers who want the Planner's reasoning for explainability,
        without requiring any change to SupervisorAgent.
        """
        return self._last_plan