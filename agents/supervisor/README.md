# Module 2.1 — Supervisor Agent

## Purpose
`SupervisorAgent` is the central orchestrator of the multi-agent system.
It receives a task, decides which registered agents handle it, executes
them (with retry on failure), collects outputs, builds a structured
final report, and persists the run via `MemoryManager` (Module 1.3).

## Files
- `supervisor_agent.py` — `SupervisorAgent`, `AgentRegistry`,
  `TaskRouter` / `SequentialTaskRouter`, `ExecutionStrategy` /
  `SequentialExecutionStrategy`, `RetryPolicy`, `AgentExecutionRecord`,
  `AgentExecutionStatus`, `ExecutionTrace`, `SupervisorResult`

## Dependencies
- `agents.base_agent.BaseAgent` (Module 1.1) — every registered agent
  must be a `BaseAgent` subclass.
- `agents.memory.MemoryManager` (Module 1.3) — used to persist each
  run's outcome, keyed by the Supervisor's `name`.
- **No LLM provider, no concrete agent, no FAISS import anywhere** —
  Supervisor is provider-independent by construction.

## Usage Example
```python
from agents.memory import MemoryManager
from agents.supervisor.supervisor_agent import SupervisorAgent

memory_manager = MemoryManager()
supervisor = SupervisorAgent(memory_manager=memory_manager)

supervisor.register_agent(writer_agent)   # any BaseAgent subclass
supervisor.register_agent(critic_agent)

result = supervisor.run("Write and review a paragraph on renewable energy")

print(result.success)
print(result.final_report)
print(result.outputs)              # {"WriterAgent": ..., "CriticAgent": ...}
print(result.execution_trace)      # full explainability trace
```

## Key Responsibilities
1. **Dynamic agent registration** — agents register/unregister at
   runtime via `register_agent()` / `unregister_agent()`; Supervisor
   has zero compile-time knowledge of which agents exist.
2. **Task routing** — `TaskRouter` decides which registered agents run
   and in what order. Module 2.1 ships only `SequentialTaskRouter`
   (registration order, or an explicit order); a future LLM-driven
   Planner Agent would implement the same interface.
3. **Execution** — `ExecutionStrategy` decides *how* agents run.
   Module 2.1 ships only `SequentialExecutionStrategy`; parallel/async
   strategies are a drop-in future addition (see DESIGN.md).
4. **Retry on failure** — configurable via `RetryPolicy`
   (`max_retries`, `retry_on_failure`).
5. **Execution trace** — every run produces an `ExecutionTrace`
   containing the Supervisor's own reasoning steps *and* every agent's
   individual `reasoning_log` (from `BaseAgent`, Module 1.1) —
   supports the project's Explainability goal end to end.
6. **Memory integration** — every run's final report and metadata is
   stored via `MemoryManager.store(name=self.name, ...)`.

## How to Test
```bash
pytest tests/test_supervisor.py -v
```
All 24 tests use mock `BaseAgent` subclasses — no real LLM calls, no
real Planner/Research/Coding agents (those are out of scope for this
module).

## Status
✅ Complete — 24/24 tests passing. Not implemented (by design, per
project scope): Planner/Research/Coding/etc. agents, parallel/async
execution, human approval workflows. See DESIGN.md for how each of
these will plug in later without breaking this module. 