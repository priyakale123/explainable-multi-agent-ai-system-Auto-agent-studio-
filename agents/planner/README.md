# Module 2.2 — Planner Agent

## What It Does
`PlannerAgent` analyzes a user task with an LLM and produces a
structured, step-by-step execution plan: which registered agents are
needed, in what order (via dependencies), what each should do, and a
concise rationale per step. `PlannerTaskRouter` adapts that plan into
the exact `list[str]` shape `SupervisorAgent` (Module 2.1) already
expects from any `TaskRouter`.

## Why Planner Is Separate From Supervisor
Single Responsibility: Supervisor's job is *orchestration* (execute,
retry, trace, persist) — it has no opinion on *which* agents a task
needs. Planning is a distinct concern with its own failure modes
(malformed LLM output, invalid dependencies) that must never be able
to crash or block orchestration. Keeping them separate means either
can change without touching the other — proven here: this entire
module was added with **zero changes to `supervisor_agent.py`**.

## How It Uses LLMInterface
`PlannerAgent` extends the existing `BaseAgent` (Module 1.1) directly.
It receives its LLM via the exact same constructor dependency
injection every other agent uses:
```python
PlannerAgent(name, role_description, llm_interface, memory)
```
It never imports `anthropic`, `openai`, or constructs an API client —
whatever `LLMInterface` implementation the caller injects (Module 1.2's
`AnthropicLLM`, `OpenAILLM`, or a test fake) is what it uses.

## How It Integrates With TaskRouter
```python
class TaskRouter(ABC):                                    # existing, Module 2.1
    def decide_agents(self, task, available_agents) -> list[str]: ...

class PlannerTaskRouter(TaskRouter):                       # new, Module 2.2
    def decide_agents(self, task, available_agents) -> list[str]:
        ...  # runs PlannerAgent, validates & orders the plan, returns names
```
`PlannerTaskRouter` is injected into `SupervisorAgent` exactly like
`SequentialTaskRouter`:
```python
from agents.planner import PlannerAgent, PlannerTaskRouter
from agents.supervisor.supervisor_agent import SupervisorAgent

planner = PlannerAgent("Planner", "plans task execution", llm_interface, memory)
router = PlannerTaskRouter(planner)

supervisor = SupervisorAgent(memory_manager=memory_manager, task_router=router)
supervisor.register_agent(writer_agent)
supervisor.register_agent(critic_agent)

result = supervisor.run("Write and review a paragraph on renewable energy")
```

## How It Produces a Plan
1. `PlannerAgent._build_prompt()` calls `build_planning_prompt()`
   (`prompt_templates.py`) with the task and the list of currently
   available agent names.
2. The LLM must respond with strict JSON: a list of steps (`step_id`,
   `agent_name`, `instruction`, `depends_on`, `expected_output`,
   `rationale`) plus one overall `reasoning` string.
3. `PlannerAgent._parse_output()` validates and converts this into a
   `PlannerExecutionPlan` (`planner_models.py`), raising
   `PlanValidationError` / `DependencyError` on anything malformed —
   caught automatically by `BaseAgent.run()` (Module 1.1), never a crash.
4. `PlannerExecutionPlan.ordered_agent_names()` topologically sorts
   steps by `depends_on` into a flat `list[str]`.
5. `PlannerTaskRouter` filters that list to agents actually registered
   with Supervisor, and falls back to `SequentialTaskRouter` if
   planning failed or produced nothing usable.

## Remaining Provider-Independent
No LLM SDK import anywhere in this module (verified by a dedicated
test scanning the module source). The LLM is always injected from
outside via `LLMInterface`, matching Module 1.1/1.2's existing pattern.

## Files
- `planner_agent.py` — `PlannerAgent`, `PlannerTaskRouter`
- `planner_models.py` — `PlannerRequest`, `PlanStep`,
  `PlannerExecutionPlan`, `PlanValidationError`, `DependencyError`
- `prompt_templates.py` — `build_planning_prompt()`

## How to Test
```bash
pytest tests/test_planner_agent.py -v   # 21 tests, this module only
pytest tests/ -v                          # 68 tests, full project
```

## Status
✅ Complete — 21/21 Planner tests passing, 68/68 project-wide, zero
regressions, `agents/supervisor/supervisor_agent.py` unmodified.