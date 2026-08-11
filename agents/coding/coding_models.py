"""
Coding Models

Coding-specific structured data: the input request, an individual
CodeFile, the overall CodeGenerationResult, and the exception
CodingAgent raises when LLM output fails validation.

Does not duplicate any model already defined by Supervisor
(agents/supervisor/supervisor_agent.py), Planner
(agents/planner/planner_models.py), or Research
(agents/research/research_models.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Allowed values for CodeFile.language. Kept as a small, explicit,
# defensively-checked set rather than an open string -- consistent
# with the project's "never trust raw LLM output" posture. Extend
# this set (not the validation logic) when a new language is needed.
ALLOWED_LANGUAGES: frozenset[str] = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "html",
        "css",
        "json",
        "yaml",
        "sql",
        "bash",
        "markdown",
    }
)


class CodingValidationError(Exception):
    """
    Raised when LLM output for a coding task is structurally
    invalid: malformed JSON, missing required fields, an
    unrecognized language, empty code content, or a duplicate
    file_id.
    """


@dataclass(slots=True)
class CodingRequest:
    """
    Input to CodingAgent.

    Attributes:
        objective: what should be implemented -- a feature
            description, function signature, or task description.
        context_notes: optional supplementary information to
            implement against (e.g. existing code conventions,
            constraints, prior agent outputs such as a
            ResearchReport or PlannerExecutionPlan step). CodingAgent
            has no filesystem access and no live project visibility
            (see DESIGN.md "Context Limitation") -- it reasons only
            over the objective and whatever context_notes/memory
            context it is given, and never fabricates project
            information it was not given.
    """

    objective: Any
    context_notes: str = ""


@dataclass(slots=True)
class CodeFile:
    """
    One individual generated code file.

    Attributes:
        file_id: unique identifier for this file within the result
            (e.g. "f1").
        filename: relative filename/path for the generated file
            (e.g. "agents/example/example_agent.py"). CodingAgent
            never writes this file to disk -- it is a proposed path
            only.
        language: the programming/markup language of `content`.
            Must be one of ALLOWED_LANGUAGES.
        content: the generated code itself, stated in full.
            CodingAgent never executes this content and never
            claims it has been run or tested.
        purpose: one-line description of this file's role within
            the overall implementation -- for explainability.
    """

    file_id: str
    filename: str
    language: str
    content: str
    purpose: str = ""


@dataclass(slots=True)
class CodeGenerationResult:
    """
    Final structured output of a CodingAgent run.

    Attributes:
        objective: the original coding objective, echoed back.
        files: the generated files, each uniquely identified.
        dependencies: external imports/packages the generated code
            requires. Declared only -- CodingAgent never installs,
            imports, or verifies these; that is a future module's
            responsibility.
        assumptions: explicit assumptions CodingAgent made while
            generating code (e.g. about missing context, unspecified
            behavior, or interfaces it could not confirm). Must not
            be silently omitted -- an empty list means CodingAgent
            made none, not that they went unrecorded.
        explanation: concise, high-level explanation of the overall
            implementation.
        rationale: concise explanation of how `explanation` and the
            generated `files` follow from the objective and
            context_notes -- explainability, not chain-of-thought.
    """

    objective: Any
    files: list[CodeFile] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    explanation: str = ""
    rationale: str = ""