"""
Supervisor Agent

The central orchestrator of the multi-agent system. Receives a task,
decides which registered agents should handle it, runs them (with
retry on failure), collects their outputs, records a full execution
trace for explainability, and persists the outcome via MemoryManager.

Depends only on:
    - agents.base_agent.BaseAgent   (Module 1.1)
    - agents.memory.MemoryManager   (Module 1.3)

Never imports or references any LLM provider, any concrete agent
implementation, or FAISS -- those are all injected or registered
from outside, keeping this module provider-independent and testable
in isolation with mock agents.

Author: Priyanka Kale
Project: AutoAgent Studio -- Explainable Multi-Agent AI Platform
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.base_agent import BaseAgent
from memory import MemoryManager

logger = logging.getLogger(__name__)


# ==========================================================
# Enums & Data Classes
# ==========================================================

class AgentExecutionStatus(str, Enum):
    """Lifecycle status of a single agent's execution within a run."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class RetryPolicy:
    """
    Configures retry behavior for agent execution.

    Attributes:
        max_retries: number of retries AFTER an initial failed attempt.
            max_retries=1 means: try once, and if it fails, try one
            more time (2 attempts total).
        retry_on_failure: if False, no retries are attempted regardless
            of max_retries -- useful for agents whose failures are
            known to be non-transient.
    """

    max_retries: int = 1
    retry_on_failure: bool = True


@dataclass(slots=True)
class AgentExecutionRecord:
    """
    Full record of one agent's execution within a Supervisor run.
    Forms the atomic unit of the execution trace.
    """

    agent_name: str
    status: AgentExecutionStatus
    attempts: int
    output: Any
    error: str | None
    started_at: float
    ended_at: float
    reasoning_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionTrace:
    """
    Full explainability trace for one Supervisor.run() call.

    Combines the Supervisor's own reasoning (why it chose these agents,
    in this order) with each agent's individual execution record
    (which already contains that agent's own reasoning_log from
    BaseAgent -- Module 1.1).
    """

    task: Any
    records: list[AgentExecutionRecord] = field(default_factory=list)
    supervisor_reasoning: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class SupervisorResult:
    """Final structured response returned by SupervisorAgent.run()."""

    success: bool
    task: Any
    outputs: dict[str, Any]
    execution_trace: ExecutionTrace
    final_report: str


# ==========================================================
# Agent Registry  (Single Responsibility: registration only)
# ==========================================================

class AgentRegistry:
    """
    Tracks registered BaseAgent instances by name.

    Kept as its own small class (rather than a dict inside
    SupervisorAgent) so registration concerns are testable and
    replaceable independently of orchestration concerns -- e.g. a
    future DistributedAgentRegistry backed by a service directory
    could implement the same shape without SupervisorAgent changing.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register (or replace) an agent under its own `.name`."""
        if agent.name in self._agents:
            logger.warning("Overwriting existing agent registration: '%s'", agent.name)
        self._agents[agent.name] = agent
        logger.info("Agent registered: '%s'", agent.name)

    def unregister(self, name: str) -> None:
        """Remove an agent registration, if present."""
        if name in self._agents:
            del self._agents[name]
            logger.info("Agent unregistered: '%s'", name)

    def get(self, name: str) -> BaseAgent | None:
        """Return the registered agent for `name`, or None if absent."""
        return self._agents.get(name)

    def list_names(self) -> list[str]:
        """Return all currently registered agent names, in registration order."""
        return list(self._agents.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._agents


# ==========================================================
# Task Routing  (Open/Closed: swap routing strategy without
# touching SupervisorAgent)
# ==========================================================

class TaskRouter(ABC):
    """
    Decides which registered agents should handle a given task, and
    in what order.

    This is the seam where a future LLM-driven Planner Agent, a
    rule-based classifier, or a Workflow Optimizer would plug in --
    SupervisorAgent only ever talks to this abstraction.
    """

    @abstractmethod
    def decide_agents(self, task: Any, available_agents: list[str]) -> list[str]:
        """Return an ordered subset of `available_agents` to execute."""
        raise NotImplementedError


class SequentialTaskRouter(TaskRouter):
    """
    Default, provider-independent router.

    If constructed with an explicit `order`, returns that order
    filtered to agents that are actually registered (preserving the
    given sequence). Otherwise, returns every registered agent in
    registration order. No LLM call, no task analysis -- this is
    intentionally the simplest possible router, since Module 2.1
    does not implement a real Planner Agent yet.
    """

    def __init__(self, order: list[str] | None = None) -> None:
        self._order = order

    def decide_agents(self, task: Any, available_agents: list[str]) -> list[str]:
        if self._order is None:
            return list(available_agents)
        available_set = set(available_agents)
        return [name for name in self._order if name in available_set]


# ==========================================================
# Execution Strategy  (Open/Closed: sequential today, parallel/
# async later -- without changing SupervisorAgent's own code)
# ==========================================================

class ExecutionStrategy(ABC):
    """
    Decides HOW a list of agents is executed for a given task.

    SupervisorAgent depends only on this abstraction. A future
    ParallelExecutionStrategy or AsyncExecutionStrategy implements
    the same `run()` signature and can be injected without any
    change to SupervisorAgent -- this is the primary extension point
    for the 100+ agent / parallel / async roadmap mentioned in the
    project brief.
    """

    @abstractmethod
    def run(
        self,
        agents: list[BaseAgent],
        task: Any,
        retry_policy: RetryPolicy,
    ) -> list[AgentExecutionRecord]:
        """Execute `agents` against `task` and return their records."""
        raise NotImplementedError


class SequentialExecutionStrategy(ExecutionStrategy):
    """
    Runs agents one after another, in list order, with retry-on-failure.

    This is the only strategy implemented in Module 2.1. Parallel and
    async strategies are intentionally NOT implemented here (per
    project scope) but require no change to this class or to
    SupervisorAgent to add later -- they would simply be additional
    ExecutionStrategy subclasses.
    """

    def run(
        self,
        agents: list[BaseAgent],
        task: Any,
        retry_policy: RetryPolicy,
    ) -> list[AgentExecutionRecord]:
        records: list[AgentExecutionRecord] = []
        for agent in agents:
            records.append(self._execute_with_retry(agent, task, retry_policy))
        return records

    def _execute_with_retry(
        self,
        agent: BaseAgent,
        task: Any,
        retry_policy: RetryPolicy,
    ) -> AgentExecutionRecord:
        started_at = time.time()
        max_attempts = (retry_policy.max_retries + 1) if retry_policy.retry_on_failure else 1

        attempts = 0
        last_result = None
        while attempts < max_attempts:
            attempts += 1
            logger.info(
                "Executing agent '%s' (attempt %d/%d)", agent.name, attempts, max_attempts
            )
            last_result = agent.run(task)
            if last_result.success:
                break
            logger.warning(
                "Agent '%s' failed on attempt %d: %s",
                agent.name, attempts, last_result.error,
            )

        ended_at = time.time()
        status = AgentExecutionStatus.SUCCESS if last_result.success else AgentExecutionStatus.FAILED

        return AgentExecutionRecord(
            agent_name=agent.name,
            status=status,
            attempts=attempts,
            output=last_result.output,
            error=last_result.error,
            started_at=started_at,
            ended_at=ended_at,
            reasoning_log=last_result.reasoning_log,
        )


# ==========================================================
# Supervisor Agent
# ==========================================================

class SupervisorAgent:
    """
    Central orchestrator for the multi-agent system.

    Responsibilities (per project brief):
        - receive a user task
        - decide which registered agents are required (via TaskRouter)
        - execute them in order (via ExecutionStrategy), with retries
        - collect outputs and build a structured final report
        - maintain a full execution trace for explainability
        - persist the run's outcome via MemoryManager
        - remain provider-independent (never imports an LLM SDK,
          never imports a concrete agent implementation)

    Dependencies are injected (Dependency Inversion): SupervisorAgent
    depends on the BaseAgent abstraction (via AgentRegistry), the
    MemoryManager facade (Module 1.3), and the TaskRouter /
    ExecutionStrategy / RetryPolicy abstractions -- never on a
    concrete LLM provider or a concrete agent class.
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
        task_router: TaskRouter | None = None,
        execution_strategy: ExecutionStrategy | None = None,
        retry_policy: RetryPolicy | None = None,
        name: str = "Supervisor",
    ) -> None:
        """
        Args:
            memory_manager: Module 1.3 MemoryManager used to persist
                execution history under this Supervisor's `name`.
            task_router: strategy for deciding which agents run.
                Defaults to SequentialTaskRouter() (registration order).
            execution_strategy: strategy for how agents run. Defaults
                to SequentialExecutionStrategy().
            retry_policy: retry configuration. Defaults to
                RetryPolicy(max_retries=1, retry_on_failure=True).
            name: identifies this Supervisor in memory and logs --
                relevant once multiple Supervisors coexist (future).
        """
        self.name = name
        self._memory_manager = memory_manager
        self._registry = AgentRegistry()
        self._task_router = task_router or SequentialTaskRouter()
        self._execution_strategy = execution_strategy or SequentialExecutionStrategy()
        self._retry_policy = retry_policy or RetryPolicy()
        self._last_trace: ExecutionTrace | None = None

    # ------------------------------------------------------
    # Dynamic agent registration
    # ------------------------------------------------------

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent so it becomes eligible for task routing."""
        self._registry.register(agent)

    def unregister_agent(self, name: str) -> None:
        """Remove an agent from the registry."""
        self._registry.unregister(name)

    def list_agents(self) -> list[str]:
        """Return the names of all currently registered agents."""
        return self._registry.list_names()

    # ------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------

    def run(self, task: Any, agent_order: list[str] | None = None) -> SupervisorResult:
        """
        Execute a task across the appropriate registered agents.

        Args:
            task: the user task. Passed as-is to each agent's run().
            agent_order: optional explicit list of agent names to run,
                in order. If omitted, the configured TaskRouter decides.

        Returns:
            A SupervisorResult with per-agent outputs, a full
            execution trace, and a human-readable final report.
            Never raises for agent-level failures -- those are
            captured in the trace, matching BaseAgent's fault
            isolation philosophy (Module 1.1).
        """
        supervisor_reasoning: list[dict[str, Any]] = []

        def log_reasoning(step: str, content: Any) -> None:
            supervisor_reasoning.append(
                {"step": step, "content": content, "timestamp": time.time()}
            )

        log_reasoning("received_task", task)
        logger.info("Supervisor '%s' received task: %s", self.name, task)

        available = self._registry.list_names()
        chosen_names = agent_order if agent_order is not None else self._task_router.decide_agents(
            task, available
        )
        log_reasoning("agents_selected", chosen_names)
        logger.info("Supervisor '%s' selected agents: %s", self.name, chosen_names)

        resolved_agents: list[BaseAgent] = []
        skipped_records: list[AgentExecutionRecord] = []
        for name in chosen_names:
            agent = self._registry.get(name)
            if agent is None:
                logger.error("Requested agent '%s' is not registered -- skipping", name)
                skipped_records.append(
                    AgentExecutionRecord(
                        agent_name=name,
                        status=AgentExecutionStatus.SKIPPED,
                        attempts=0,
                        output=None,
                        error=f"Agent '{name}' is not registered",
                        started_at=time.time(),
                        ended_at=time.time(),
                        reasoning_log=[],
                    )
                )
            else:
                resolved_agents.append(agent)

        executed_records = self._execution_strategy.run(
            resolved_agents, task, self._retry_policy
        )
        records = skipped_records + executed_records
        log_reasoning(
            "execution_complete",
            {r.agent_name: r.status.value for r in records},
        )

        outputs = {record.agent_name: record.output for record in records}
        overall_success = bool(records) and all(
            record.status == AgentExecutionStatus.SUCCESS for record in records
        )

        trace = ExecutionTrace(
            task=task, records=records, supervisor_reasoning=supervisor_reasoning
        )
        self._last_trace = trace

        final_report = self._build_final_report(trace, overall_success)
        log_reasoning("report_built", final_report)

        self._memory_manager.store(
            name=self.name,
            task=task,
            result=final_report,
            metadata={"outputs": outputs, "success": overall_success},
        )
        log_reasoning("stored_to_memory", {"memory_store": self.name})

        return SupervisorResult(
            success=overall_success,
            task=task,
            outputs=outputs,
            execution_trace=trace,
            final_report=final_report,
        )

    def get_last_execution_trace(self) -> ExecutionTrace | None:
        """Return the ExecutionTrace from the most recent run(), if any."""
        return self._last_trace

    # ------------------------------------------------------
    # Reporting
    # ------------------------------------------------------

    def _build_final_report(self, trace: ExecutionTrace, overall_success: bool) -> str:
        """Build a human-readable summary of one execution run."""
        lines = [
            f"Execution {'SUCCEEDED' if overall_success else 'FAILED'} "
            f"for task: {trace.task!r}"
        ]
        for record in trace.records:
            lines.append(
                f"  - {record.agent_name}: {record.status.value} "
                f"(attempts={record.attempts})"
                + (f" | error: {record.error}" if record.error else "")
            )
        return "\n".join(lines)