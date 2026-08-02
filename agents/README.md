# Module 1.1 — Agent Core

## Purpose
Defines `BaseAgent`, the abstract base class every specialized agent in the
system inherits from. Implements the Template Method design pattern: the
`run()` pipeline is fixed and shared, while `_build_prompt()` and
`_parse_output()` are customized per agent type.

## Files
- `base_agent.py` — `BaseAgent` (ABC), `AgentResult` (dataclass),
  `LLMInterface` / `AgentMemory` (Protocol placeholders for Modules 1.2/1.3)

## Key Responsibilities
1. Provide a consistent `run(task) -> AgentResult` interface for the
   Supervisor to call, regardless of agent type.
2. Automatically capture a step-by-step reasoning trace on every run
   (feeds Milestone 3 — Internal Reasoning Summary Engine).
3. Fail gracefully — errors are caught and returned as a failed
   `AgentResult` instead of crashing the caller.

## Dependencies
- None yet (stdlib only: `abc`, `dataclasses`, `typing`, `logging`, `time`)
- Will depend on Module 1.2 (LLM Interface) and Module 1.3 (Agent Memory)
  once those are built — `BaseAgent` currently accepts anything matching
  the `LLMInterface` / `AgentMemory` Protocols.

## How to Test
See `test_base_agent.py` example in module documentation. Run:
```
pytest test_base_agent.py -v
```

## Status
✅ Complete — awaiting approval before Module 1.2 (LLM Interface).