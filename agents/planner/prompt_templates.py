"""
Prompt Templates

All PlannerAgent LLM prompts live here, kept separate from
planner_agent.py so prompt wording can change without touching
planning/validation logic.
"""

from __future__ import annotations

from typing import Any


def build_planning_prompt(user_task: Any, available_agents: list[str]) -> str:
    """
    Build the prompt asking the LLM to produce a structured execution
    plan for `user_task`, choosing only from `available_agents`.

    Demands strict JSON output and explicitly forbids hidden
    chain-of-thought -- only a concise rationale per step and overall
    is requested, matching the project's explainability requirement.
    """
    agents_list = ", ".join(available_agents) if available_agents else "(none registered)"

    return (
        "You are the task planner for a multi-agent system.\n\n"
        f"User task: {user_task}\n"
        f"Available agents: {agents_list}\n\n"
        "Produce a step-by-step execution plan using ONLY the available "
        "agents listed above. For each step, specify:\n"
        "  - step_id: a unique short identifier (e.g. \"step_1\")\n"
        "  - agent_name: must exactly match one of the available agents\n"
        "  - instruction: what that agent should do\n"
        "  - depends_on: list of step_ids that must complete first "
        "(empty list if none)\n"
        "  - expected_output: a brief description of what this step "
        "should produce\n"
        "  - rationale: ONE concise sentence explaining why this agent "
        "was chosen for this step\n\n"
        "Also provide one concise overall 'reasoning' sentence for the "
        "plan as a whole.\n\n"
        "Do NOT include any internal chain-of-thought, deliberation, or "
        "explanation outside the fields above. Respond with ONLY valid "
        "JSON in exactly this shape, no other text:\n"
        '{\n'
        '  "steps": [\n'
        '    {\n'
        '      "step_id": "step_1",\n'
        '      "agent_name": "...",\n'
        '      "instruction": "...",\n'
        '      "depends_on": [],\n'
        '      "expected_output": "...",\n'
        '      "rationale": "..."\n'
        '    }\n'
        '  ],\n'
        '  "reasoning": "..."\n'
        '}'
    )