"""
Prompt Templates

All ResearchAgent LLM prompts live here, kept separate from
research_agent.py so prompt wording can change without touching
parsing/validation logic (same pattern as
agents/planner/prompt_templates.py).
"""

from __future__ import annotations

from typing import Any


def build_research_prompt(objective: Any, context_notes: str) -> str:
    """
    Build the prompt asking the LLM to research `objective` and
    return structured findings.

    ResearchAgent has no live web/search capability -- the LLM must
    reason over `objective` and `context_notes` only (whatever
    reference information was supplied), never invent an external
    source it wasn't given. Demands strict JSON output and explicitly
    forbids hidden chain-of-thought, matching the project's
    explainability requirement.
    """
    context_block = context_notes.strip() if context_notes.strip() else "(none provided)"

    return (
        "You are the research agent for a multi-agent system.\n\n"
        f"Research objective: {objective}\n"
        f"Reference context provided: {context_block}\n\n"
        "You do NOT have live web or search access. Base your findings "
        "ONLY on the research objective and the reference context "
        "provided above -- never invent a source you were not given.\n\n"
        "Produce a set of findings. For each finding, specify:\n"
        "  - finding_id: a unique short identifier (e.g. \"f1\")\n"
        "  - statement: the finding, stated concisely\n"
        "  - confidence: a number from 0.0 to 1.0\n"
        "  - supporting_evidence: concise evidence in favor (empty "
        "string if none)\n"
        "  - conflicting_evidence: concise evidence against, or note "
        "of a conflicting finding (empty string if none)\n"
        "  - source: a reference string ONLY if one was given in the "
        "context above; otherwise an empty string\n\n"
        "If two findings would restate the same underlying fact, "
        "merge them into a single finding rather than repeating it.\n\n"
        "Also provide one concise overall 'summary' synthesizing all "
        "findings, and one concise overall 'rationale' explaining how "
        "the summary follows from the findings.\n\n"
        "Do NOT include any internal chain-of-thought, deliberation, or "
        "explanation outside the fields above. Respond with ONLY valid "
        "JSON in exactly this shape, no other text:\n"
        '{\n'
        '  "findings": [\n'
        '    {\n'
        '      "finding_id": "f1",\n'
        '      "statement": "...",\n'
        '      "confidence": 0.8,\n'
        '      "supporting_evidence": "...",\n'
        '      "conflicting_evidence": "",\n'
        '      "source": ""\n'
        '    }\n'
        '  ],\n'
        '  "summary": "...",\n'
        '  "rationale": "..."\n'
        '}'
    )