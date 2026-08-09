"""
Research Models

Research-specific structured data: the input request, an individual
Finding, the overall ResearchReport, and the exception ResearchAgent
raises when LLM output fails validation.

Does not duplicate any model already defined by Supervisor
(agents/supervisor/supervisor_agent.py) or Planner
(agents/planner/planner_models.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ResearchValidationError(Exception):
    """
    Raised when LLM output for a research task is structurally
    invalid: malformed JSON, missing required fields, an
    out-of-range confidence value, or a duplicate finding_id.
    """


@dataclass(slots=True)
class ResearchRequest:
    """
    Input to ResearchAgent.

    Attributes:
        objective: what should be researched -- a question, topic,
            or task description.
        context_notes: optional supplementary information to research
            against (e.g. prior findings, provided reference text).
            ResearchAgent has no live web/search capability (see
            DESIGN.md "Source/Retrieval Limitation") -- it reasons
            over the objective and whatever context_notes/memory
            context it is given, not the open web.
    """

    objective: Any
    context_notes: str = ""


@dataclass(slots=True)
class Finding:
    """
    One individual research finding.

    Attributes:
        finding_id: unique identifier for this finding (e.g. "f1").
        statement: the finding itself, stated concisely.
        confidence: 0.0-1.0, how confident the finding is.
        supporting_evidence: concise evidence in favor, if any.
        conflicting_evidence: concise evidence against / conflicting
            findings, if any -- non-empty signals a genuine conflict
            for the reader to weigh, not a hidden internal doubt.
        source: a reference/citation string if one was given in the
            input context; "" if no source information is available
            (ResearchAgent never fabricates a source).
    """

    finding_id: str
    statement: str
    confidence: float
    supporting_evidence: str = ""
    conflicting_evidence: str = ""
    source: str = ""


@dataclass(slots=True)
class ResearchReport:
    """
    Final structured output of a ResearchAgent run.

    Attributes:
        objective: the original research objective, echoed back.
        findings: deduplicated list of Finding objects.
        summary: concise synthesis of all findings.
        rationale: concise explanation of how the summary was reached
            from the findings -- explainability, not chain-of-thought.
    """

    objective: Any
    findings: list[Finding] = field(default_factory=list)
    summary: str = ""
    rationale: str = ""