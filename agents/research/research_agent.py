"""
Research Agent

ResearchAgent analyzes a research objective using the existing
LLMInterface (Module 1.2, injected via BaseAgent's constructor --
Module 1.1) and produces a structured ResearchReport: deduplicated
findings with confidence, evidence, and conflict information, plus
a concise overall summary and synthesis rationale.

ResearchAgent does NOT execute other agents, does NOT route tasks,
does NOT register agents, and does NOT implement retry logic -- all
of that remains SupervisorAgent's responsibility (Module 2.1),
untouched by this module. ResearchAgent is registered directly with
SupervisorAgent like any other worker agent -- unlike PlannerAgent
(Module 2.2), it needs no TaskRouter adapter, since it doesn't plug
into Supervisor's routing extension point.

Source/Retrieval Limitation: this repository contains no web/search
retrieval abstraction. ResearchAgent reasons only over the objective
and whatever context_notes/memory context it is given -- it has no
live web access and never fabricates a source. See DESIGN.md for how
a retrieval capability could be injected later without changing this
class's public interface.

Author: Priyanka Kale
Project: AutoAgent Studio -- Explainable Multi-Agent AI Platform
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from agents.research.prompt_templates import build_research_prompt
from agents.research.research_models import (
    Finding,
    ResearchReport,
    ResearchRequest,
    ResearchValidationError,
)

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """
    LLM-driven research agent.

    Extends the EXISTING BaseAgent (Module 1.1) unchanged -- inherits
    its real __init__(name, role_description, llm_interface, memory)
    and its real run() template method, including reasoning-log
    capture and fault-isolated error handling. Only _build_prompt and
    _parse_output are implemented here, as BaseAgent's contract requires.

    task passed to run() must be a ResearchRequest.
    """

    def _build_prompt(self, task: ResearchRequest, context: dict[str, Any]) -> str:
        if not isinstance(task, ResearchRequest):
            raise ResearchValidationError(
                f"ResearchAgent requires a ResearchRequest, got {type(task).__name__}"
            )
        if not str(task.objective).strip():
            raise ResearchValidationError("Cannot research an empty objective")
        # BaseAgent._parse_output() only receives raw_output, not the
        # original task, so the objective is captured here (each run()
        # call resets this before use, matching how BaseAgent itself
        # resets reasoning_log per run -- single call in flight at a time).
        self._current_objective = task.objective
        return build_research_prompt(task.objective, task.context_notes)

    def _parse_output(self, raw_output: str) -> ResearchReport:
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ResearchValidationError(
                f"Research LLM did not return valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict) or "findings" not in parsed:
            raise ResearchValidationError("Research JSON missing required 'findings' key")

        raw_findings = parsed["findings"]
        if not isinstance(raw_findings, list) or len(raw_findings) == 0:
            raise ResearchValidationError("Research JSON 'findings' must be a non-empty list")

        findings: list[Finding] = []
        seen_finding_ids: set[str] = set()
        seen_statements: set[str] = set()

        for raw_finding in raw_findings:
            if not isinstance(raw_finding, dict):
                raise ResearchValidationError("Each finding must be a JSON object")

            finding_id = raw_finding.get("finding_id")
            statement = raw_finding.get("statement")
            confidence = raw_finding.get("confidence")

            if not isinstance(finding_id, str) or not finding_id:
                raise ResearchValidationError(
                    "Each finding requires a non-empty string 'finding_id'"
                )
            if finding_id in seen_finding_ids:
                raise ResearchValidationError(f"Duplicate finding_id: '{finding_id}'")
            seen_finding_ids.add(finding_id)

            if not isinstance(statement, str) or not statement.strip():
                raise ResearchValidationError(
                    f"Finding '{finding_id}' requires a non-empty string 'statement'"
                )

            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                raise ResearchValidationError(
                    f"Finding '{finding_id}' requires a numeric 'confidence'"
                )
            if not (0.0 <= float(confidence) <= 1.0):
                raise ResearchValidationError(
                    f"Finding '{finding_id}' confidence must be between 0.0 and 1.0, "
                    f"got {confidence}"
                )

            # Duplicate-content detection: same statement (case-insensitive,
            # whitespace-normalized) reported under a different finding_id
            # is silently merged (skipped) rather than kept as a repeat --
            # the LLM was explicitly asked not to repeat findings, but
            # this is a defensive backstop.
            normalized_statement = " ".join(statement.strip().lower().split())
            if normalized_statement in seen_statements:
                logger.info(
                    "Skipping duplicate finding '%s' (same statement as an earlier finding)",
                    finding_id,
                )
                continue
            seen_statements.add(normalized_statement)

            findings.append(
                Finding(
                    finding_id=finding_id,
                    statement=statement.strip(),
                    confidence=float(confidence),
                    supporting_evidence=str(raw_finding.get("supporting_evidence", "")),
                    conflicting_evidence=str(raw_finding.get("conflicting_evidence", "")),
                    source=str(raw_finding.get("source", "")),
                )
            )

        if not findings:
            raise ResearchValidationError(
                "All findings were duplicates -- no unique findings remain"
            )

        summary = parsed.get("summary", "")
        if not isinstance(summary, str):
            summary = str(summary)

        rationale = parsed.get("rationale", "")
        if not isinstance(rationale, str):
            rationale = str(rationale)

        return ResearchReport(
            objective=getattr(self, "_current_objective", None),
            findings=findings,
            summary=summary,
            rationale=rationale,
        )