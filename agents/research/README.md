# Module 2.3 — Research Agent

## Purpose
`ResearchAgent` analyzes a research objective using an LLM and
produces a structured `ResearchReport`: deduplicated findings, each
with a confidence score, supporting/conflicting evidence, and an
optional source, plus a concise overall summary and synthesis
rationale.

## Responsibilities
- Understand a research objective (`ResearchRequest.objective`)
- Reason over the objective and any supplied reference context
  (`ResearchRequest.context_notes`)
- Produce individual findings with confidence, evidence, and source
- Detect and merge duplicate findings (same statement reported twice)
- Surface conflicting evidence explicitly rather than hiding it
- Synthesize a concise overall summary and rationale
- Validate all of the above, failing gracefully (never a crash, never
  a silently-invalid report) on any malformed LLM output

`ResearchAgent` does **not** execute other agents, route tasks,
register agents, or implement retry logic — those remain
`SupervisorAgent`'s responsibility (Module 2.1), untouched by this
module.

## Inputs / Outputs
```python
ResearchRequest(objective: Any, context_notes: str = "")
    -> passed to ResearchAgent.run()

ResearchReport(
    objective: Any,
    findings: list[Finding],
    summary: str,
    rationale: str,
)
    -> returned as AgentResult.output on success
```

## Integration
`ResearchAgent(BaseAgent)` — extends the existing `BaseAgent` (Module
1.1) directly, same as `PlannerAgent` (Module 2.2). Registered with
`SupervisorAgent` exactly like any other worker agent — **no adapter
needed** (unlike Planner, which needed `PlannerTaskRouter` to plug
into Supervisor's routing extension point; Research is a plain
executable step, not a routing decision):

```python
from agents.research import ResearchAgent, ResearchRequest
from agents.supervisor.supervisor_agent import SupervisorAgent
from memory import MemoryManager

memory_manager = MemoryManager()
supervisor = SupervisorAgent(memory_manager=memory_manager)

researcher = ResearchAgent("Researcher", "researches topics", llm_interface, memory)
supervisor.register_agent(researcher)

result = supervisor.run(
    ResearchRequest(objective="EV adoption trends", context_notes="EV sales grew 40% in 2025"),
    agent_order=["Researcher"],
)
report = result.outputs["Researcher"]   # a ResearchReport
```

## Provider Independence
No LLM SDK import anywhere in this module (verified by a dedicated
test scanning the module's own import statements). The LLM is always
injected from outside via the existing `LLMInterface` (Module 1.2),
matching every other agent in the project.

## Source/Retrieval Limitation
**This repository contains no web/search retrieval capability.**
`ResearchAgent` reasons only over the objective and whatever
`context_notes` (or memory context) it is given — it has **no live
web access** and is explicitly instructed never to fabricate a
source. See DESIGN.md for how a retrieval abstraction could be
injected later without changing this class's public interface.

## Files
- `research_agent.py` — `ResearchAgent`
- `research_models.py` — `ResearchRequest`, `Finding`,
  `ResearchReport`, `ResearchValidationError`
- `prompt_templates.py` — `build_research_prompt()`

## How to Test
```bash
pytest tests/test_research_agent.py -v   # this module only
pytest tests/ -v                           # full project
```

## Status
Implementation complete. See TESTING.md for current pass/fail counts.