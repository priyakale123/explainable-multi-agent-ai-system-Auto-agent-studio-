"""
Prompt Templates

All CodingAgent LLM prompts live here, kept separate from
coding_agent.py so prompt wording can change without touching
parsing/validation logic (same pattern as
agents/research/prompt_templates.py and
agents/planner/prompt_templates.py).
"""

from __future__ import annotations

from typing import Any

from agents.coding.coding_models import ALLOWED_LANGUAGES


def build_coding_prompt(objective: Any, context_notes: str) -> str:
    """
    Build the prompt asking the LLM to plan and generate code for
    `objective` and return a structured implementation.

    CodingAgent has no filesystem access and no live project
    visibility -- the LLM must reason ONLY over `objective` and
    `context_notes` (whatever requirements/context were supplied),
    never invent project details, files, or conventions it was not
    given. The LLM must also never claim the generated code has been
    executed or tested -- that is explicitly out of scope for this
    agent. Demands strict JSON output and explicitly forbids hidden
    chain-of-thought, matching the project's explainability
    requirement.
    """
    context_block = context_notes.strip() if context_notes.strip() else "(none provided)"
    languages_list = ", ".join(sorted(ALLOWED_LANGUAGES))

    return (
        "You are the coding agent for a multi-agent system.\n\n"
        f"Coding objective: {objective}\n"
        f"Reference context provided: {context_block}\n\n"
        "You do NOT have filesystem access, execution access, or live "
        "visibility into the surrounding project. Base your implementation "
        "ONLY on the coding objective and the reference context provided "
        "above -- never invent project files, conventions, or requirements "
        "you were not given. You do NOT run, execute, or test the code you "
        "generate, and you must never claim that it was run or tested.\n\n"
        "First plan the implementation: identify what files/components are "
        "needed, then generate the code for each. Produce a set of files. "
        "For each file, specify:\n"
        "  - file_id: a unique short identifier (e.g. \"f1\")\n"
        "  - filename: a relative filename/path for the file\n"
        f"  - language: one of: {languages_list}\n"
        "  - content: the full generated code for this file\n"
        "  - purpose: one concise sentence describing this file's role\n\n"
        "Also provide:\n"
        "  - dependencies: a list of external imports/packages the code "
        "requires (empty list if none) -- do not install or verify them, "
        "only declare them\n"
        "  - assumptions: a list of explicit assumptions you made due to "
        "missing or ambiguous context (empty list if none -- do not omit "
        "this field even when there are no assumptions)\n"
        "  - explanation: one concise overall explanation of the "
        "implementation\n"
        "  - rationale: one concise sentence explaining how the "
        "explanation and files follow from the objective and context\n\n"
        "Do NOT include any internal chain-of-thought, deliberation, or "
        "explanation outside the fields above. Respond with ONLY valid "
        "JSON in exactly this shape, no other text:\n"
        '{\n'
        '  "files": [\n'
        '    {\n'
        '      "file_id": "f1",\n'
        '      "filename": "...",\n'
        '      "language": "...",\n'
        '      "content": "...",\n'
        '      "purpose": "..."\n'
        '    }\n'
        '  ],\n'
        '  "dependencies": [],\n'
        '  "assumptions": [],\n'
        '  "explanation": "...",\n'
        '  "rationale": "..."\n'
        '}'
    )