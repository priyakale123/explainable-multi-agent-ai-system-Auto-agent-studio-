"""
base_agent.py

Module 1.1 — Agent Core
Defines the abstract BaseAgent class that every specialized agent
(ResearchAgent, CoderAgent, CriticAgent, etc.) will inherit from.

Design pattern: Template Method (the run() loop is fixed; subclasses
only customize prompt-building and output-parsing).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Placeholder interfaces for future modules.
# These will be replaced by real implementations in Module 1.2 (LLM
# Interface) and Module 1.3 (Agent Memory). Defining them as Protocols
# here keeps base_agent.py self-contained and independently testable.
# --------------------------------------------------------------------------

class LLMInterface(Protocol):
    """Minimal contract any LLM wrapper must satisfy."""

    def generate(self, prompt: str) -> str:
        """Send a prompt to an LLM and return the raw text response."""
        ...


class AgentMemory(Protocol):
    """Minimal contract any memory store must satisfy."""

    def get_context(self) -> dict:
        """Return the current context relevant to this agent."""
        ...

    def update_context(self, task: Any, result: Any) -> None:
        """Persist the outcome of this run into memory."""
        ...


# --------------------------------------------------------------------------
# Result container
# --------------------------------------------------------------------------

@dataclass
class AgentResult:
    """Structured output returned by every agent's run() call."""

    agent_name: str
    output: Any
    reasoning_log: list[dict] = field(default_factory=list)
    success: bool = True
    error: str | None = None


# --------------------------------------------------------------------------
# Base Agent
# --------------------------------------------------------------------------

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Subclasses must implement:
        - _build_prompt(task, context) -> str
        - _parse_output(raw_output) -> Any

    The run() method is the template method: it defines the fixed
    sequence every agent follows, and automatically records a
    reasoning trace at each step (used later by the Internal
    Reasoning Summary Engine — Milestone 3).
    """

    def __init__(
        self,
        name: str,
        role_description: str,
        llm_interface: LLMInterface,
        memory: AgentMemory,
    ) -> None:
        self.name = name
        self.role_description = role_description
        self.llm_interface = llm_interface
        self.memory = memory
        self.reasoning_log: list[dict] = []

    def run(self, task: Any) -> AgentResult:
        """Execute the agent's full task-handling pipeline."""
        self.reasoning_log = []  # reset trace for this run
        logger.info("Agent '%s' started task: %s", self.name, task)
        self._record_reasoning("received_task", task)

        try:
            context = self.memory.get_context()
            prompt = self._build_prompt(task, context)
            self._record_reasoning("built_prompt", prompt)

            raw_output = self.llm_interface.generate(prompt)
            self._record_reasoning("llm_output", raw_output)

            result = self._parse_output(raw_output)
            self.memory.update_context(task, result)
            self._record_reasoning("final_result", result)

            logger.info("Agent '%s' completed task successfully", self.name)
            return AgentResult(
                agent_name=self.name,
                output=result,
                reasoning_log=self.reasoning_log,
                success=True,
            )

        except Exception as exc:  # noqa: BLE001 - intentional broad catch
            logger.exception("Agent '%s' failed on task: %s", self.name, task)
            self._record_reasoning("error", str(exc))
            return AgentResult(
                agent_name=self.name,
                output=None,
                reasoning_log=self.reasoning_log,
                success=False,
                error=str(exc),
            )

    @abstractmethod
    def _build_prompt(self, task: Any, context: dict) -> str:
        """Turn a task + memory context into an LLM-ready prompt."""
        raise NotImplementedError

    @abstractmethod
    def _parse_output(self, raw_output: str) -> Any:
        """Turn raw LLM text into structured output for this agent."""
        raise NotImplementedError

    def _record_reasoning(self, step_label: str, content: Any) -> None:
        """Append one step to this run's reasoning trace."""
        self.reasoning_log.append(
            {
                "step": step_label,
                "content": content,
                "timestamp": time.time(),
            }
        )