"""
Coding Agent

CodingAgent analyzes a coding objective using the existing
LLMInterface (Module 1.2, injected via BaseAgent's constructor --
Module 1.1) and produces a structured CodeGenerationResult: a set of
generated files with declared dependencies, explicit assumptions,
and a high-level explanation/rationale.

CodingAgent does NOT execute generated code, does NOT run shell
commands, does NOT run tests, does NOT modify files on disk, does
NOT route tasks, does NOT orchestrate other agents, and does NOT
implement retry logic -- all of that remains SupervisorAgent's
responsibility (Module 2.1) or a future module's, untouched by this
class. CodingAgent is registered directly with SupervisorAgent like
any other worker agent -- unlike PlannerAgent (Module 2.2), it needs
no TaskRouter adapter, since it doesn't plug into Supervisor's
routing extension point (same as ResearchAgent, Module 2.3).

Context Limitation: this repository contains no filesystem-access or
project-introspection abstraction. CodingAgent reasons only over the
objective and whatever context_notes/memory context it is given --
it has no live view of the surrounding project and never fabricates
project details, files, or conventions it was not given. It also
never claims that generated code has been executed or tested; those
are explicitly out of scope (see DESIGN.md).

Author: Priyanka Kale
Project: AutoAgent Studio -- Explainable Multi-Agent AI Platform
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from agents.coding.coding_models import (
    ALLOWED_LANGUAGES,
    CodeFile,
    CodeGenerationResult,
    CodingRequest,
    CodingValidationError,
)
from agents.coding.prompt_templates import build_coding_prompt

logger = logging.getLogger(__name__)


class CodingAgent(BaseAgent):
    """
    LLM-driven code-generation planner and generator.

    Extends the EXISTING BaseAgent (Module 1.1) unchanged -- inherits
    its real __init__(name, role_description, llm_interface, memory)
    and its real run() template method, including reasoning-log
    capture and fault-isolated error handling. Only _build_prompt and
    _parse_output are implemented here, as BaseAgent's contract requires.

    task passed to run() must be a CodingRequest.

    CodingAgent is responsible ONLY for code-generation planning and
    code generation. It never executes, tests, or persists the code
    it produces -- that separation is enforced structurally (this
    class has no execution/filesystem/shell dependency of any kind),
    not merely by convention.
    """

    def _build_prompt(self, task: CodingRequest, context: dict[str, Any]) -> str:
        if not isinstance(task, CodingRequest):
            raise CodingValidationError(
                f"CodingAgent requires a CodingRequest, got {type(task).__name__}"
            )
        if not str(task.objective).strip():
            raise CodingValidationError("Cannot generate code for an empty objective")
        self._current_objective = task.objective
        return build_coding_prompt(task.objective, task.context_notes)

    def _parse_output(self, raw_output: str) -> CodeGenerationResult:
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise CodingValidationError(
                f"Coding LLM did not return valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict) or "files" not in parsed:
            raise CodingValidationError("Coding JSON missing required 'files' key")

        raw_files = parsed["files"]
        if not isinstance(raw_files, list) or len(raw_files) == 0:
            raise CodingValidationError("Coding JSON 'files' must be a non-empty list")

        files: list[CodeFile] = []
        seen_file_ids: set[str] = set()

        for raw_file in raw_files:
            if not isinstance(raw_file, dict):
                raise CodingValidationError("Each file must be a JSON object")

            file_id = raw_file.get("file_id")
            filename = raw_file.get("filename")
            language = raw_file.get("language")
            content = raw_file.get("content")

            if not isinstance(file_id, str) or not file_id:
                raise CodingValidationError(
                    "Each file requires a non-empty string 'file_id'"
                )
            if file_id in seen_file_ids:
                raise CodingValidationError(f"Duplicate file_id: '{file_id}'")
            seen_file_ids.add(file_id)

            if not isinstance(filename, str) or not filename.strip():
                raise CodingValidationError(
                    f"File '{file_id}' requires a non-empty string 'filename'"
                )

            if not isinstance(language, str) or language not in ALLOWED_LANGUAGES:
                raise CodingValidationError(
                    f"File '{file_id}' has unrecognized language '{language}'. "
                    f"Must be one of: {sorted(ALLOWED_LANGUAGES)}"
                )

            if not isinstance(content, str) or not content.strip():
                raise CodingValidationError(
                    f"File '{file_id}' requires non-empty string 'content'"
                )

            files.append(
                CodeFile(
                    file_id=file_id,
                    filename=filename.strip(),
                    language=language,
                    content=content,
                    purpose=str(raw_file.get("purpose", "")),
                )
            )

        dependencies = parsed.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(dep, str) for dep in dependencies
        ):
            raise CodingValidationError("'dependencies' must be a list of strings")

        assumptions = parsed.get("assumptions", [])
        if not isinstance(assumptions, list) or not all(
            isinstance(assumption, str) for assumption in assumptions
        ):
            raise CodingValidationError("'assumptions' must be a list of strings")

        explanation = parsed.get("explanation", "")
        if not isinstance(explanation, str):
            explanation = str(explanation)

        rationale = parsed.get("rationale", "")
        if not isinstance(rationale, str):
            rationale = str(rationale)

        return CodeGenerationResult(
            objective=getattr(self, "_current_objective", None),
            files=files,
            dependencies=dependencies,
            assumptions=assumptions,
            explanation=explanation,
            rationale=rationale,
        )