# agents/coding/README.md

# Module 2.4 — Coding Agent

## Purpose
`CodingAgent` analyzes a coding objective using an LLM and produces a
structured `CodeGenerationResult`: a set of generated files (each with
a language, full content, and purpose), declared external
dependencies, explicit assumptions, and a concise high-level
explanation/rationale.

## Responsibilities
- Understand a coding objective (`CodingRequest.objective`)
- Reason over the objective and any supplied requirements/context
  (`CodingRequest.context_notes`)
- Identify what files/components the implementation requires
- Generate a structured implementation specification and the code for
  each file according to that specification
- Explain the implementation at a high level
- Identify assumptions made due to missing or ambiguous context,
  explicitly (never silently)
- Identify external dependencies/import requirements, declared only
- Validate all of the above, failing gracefully (never a crash, never
  a silently-invalid result) on any malformed LLM output

`CodingAgent` does **not** execute generated code, run shell commands,
run tests, modify files on disk, route tasks, orchestrate other
agents, retry failures, or manage Supervisor execution history — those
remain out of scope for this module entirely, either by design (code
execution/testing is a future module's job) or `SupervisorAgent`'s
responsibility (Module 2.1), untouched by this module. Generated code
is always returned, never run — `CodingAgent` never claims code it
produced was executed or tested.

## Inputs / Outputs
```python
CodingRequest(objective: Any, context_notes: str = "")
    -> passed to CodingAgent.run()

CodeGenerationResult(
    objective: Any,
    files: list[CodeFile],
    dependencies: list[str],
    assumptions: list[str],
    explanation: str,
    rationale: str,
)
    -> returned as AgentResult.output on success

CodeFile(
    file_id: str,
    filename: str,
    language: str,
    content: str,
    purpose: str,
)
```

## Integration
`CodingAgent(BaseAgent)` — extends the existing `BaseAgent` (Module
1.1) directly, same as `ResearchAgent` (Module 2.3). Registered with
`SupervisorAgent` exactly like any other worker agent — **no adapter
needed** (unlike Planner, which needed `PlannerTaskRouter` to plug
into Supervisor's routing extension point; Coding is a plain
executable step, not a routing decision):

```python
from agents.coding.coding_agent import CodingAgent
from agents.coding.coding_models import CodingRequest
from agents.supervisor.supervisor_agent import SupervisorAgent
from memory import MemoryManager

memory_manager = MemoryManager()
supervisor = SupervisorAgent(memory_manager=memory_manager)

coder = CodingAgent("Coder", "generates code", llm_interface, memory)
supervisor.register_agent(coder)

result = supervisor.run(
    CodingRequest(objective="implement a stack data structure", context_notes="Python 3.11, type hints required"),
    agent_order=["Coder"],
)
generation_result = result.outputs["Coder"]   # a CodeGenerationResult
```

## Provider Independence
No LLM SDK import anywhere in this module (verified by a dedicated
test scanning the module's own import statements). The LLM is always
injected from outside via the existing `LLMInterface` (Module 1.2),
matching every other agent in the project.

## Execution Boundary
**`CodingAgent` never executes anything.** It has no `subprocess`,
`os.system`, `exec`/`eval`, filesystem-write, or shell dependency of
any kind (verified by a dedicated test scanning the module's own
source). It plans and generates code as data — a `CodeGenerationResult`
— and returns it. Running, testing, or writing that code to disk is
explicitly a future module's responsibility, not this one's.

## Context Limitation
**This repository contains no filesystem-access or project-
introspection abstraction.** `CodingAgent` reasons only over the
objective and whatever `context_notes` (or memory context) it is
given — it has **no live view of the surrounding project** and is
explicitly instructed never to fabricate project files, conventions,
or requirements it was not given. See DESIGN.md for how a
project-context abstraction could be injected later without changing
this class's public interface.

## Files
- `coding_agent.py` — `CodingAgent`
- `coding_models.py` — `CodingRequest`, `CodeFile`,
  `CodeGenerationResult`, `CodingValidationError`, `ALLOWED_LANGUAGES`
- `prompt_templates.py` — `build_coding_prompt()`

## How to Test
```bash
pytest tests/test_coding_agent.py -v   # 22 tests, this module only
pytest tests/ -v                         # full project
```

## Status
Implementation complete. See TESTING.md for current pass/fail counts.