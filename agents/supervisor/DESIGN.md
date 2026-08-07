# Module 2.1 — Supervisor Agent — Design Document

## 1. Purpose
`SupervisorAgent` is the orchestration layer between the user-facing
system (future Django Dashboard) and the pool of specialized agents
(Planner, Research, Coding, Testing, Reviewer, Documentation, Report —
none of which exist yet). It must coordinate agents it knows nothing
about at compile time, survive individual agent failures, and produce
both a usable result and a full explanation of how that result was
reached.

## 2. Design Goals
| Goal | How it's achieved |
|---|---|
| Provider independence | Supervisor imports only `BaseAgent` and `MemoryManager` — never an LLM SDK, never a concrete agent |
| Dynamic extensibility | New agents register at runtime; Supervisor has no hardcoded agent list |
| Fault isolation | One agent's failure never crashes the run — captured as a `FAILED`/`SKIPPED` record |
| Explainability | Every run yields an `ExecutionTrace` combining Supervisor-level and agent-level reasoning |
| Future-proof for scale | Routing and execution are both pluggable abstractions, not hardcoded logic |

## 3. Design Pattern Used

**Strategy Pattern (×2)** — `TaskRouter` and `ExecutionStrategy` are
each swappable strategies. `SupervisorAgent` depends on the
abstraction, never the concrete implementation. This is the single
most important decision for meeting the "100+ agents, parallel,
async, human approval" future requirements without rewriting
`SupervisorAgent` itself.

**Registry Pattern** — `AgentRegistry` centralizes agent lookup by
name, decoupled from orchestration logic (Single Responsibility).

**Dependency Injection** — `memory_manager`, `task_router`,
`execution_strategy`, and `retry_policy` are all constructor
parameters with sensible defaults, never constructed internally.
This is what makes `SupervisorAgent` testable with mocks and
reconfigurable without touching its source.

**Fault-Isolation via Structured Results** (carried over from
Module 1.1's `BaseAgent`) — `SupervisorAgent.run()` never raises for
agent-level failures; it returns a `SupervisorResult` with
`success=False` and per-agent failure detail instead.

## 4. Class Diagram (ASCII)

```
                    <<abstract>> TaskRouter
                    +--------------------------+
                    | decide_agents(task, avail)|
                    +--------------------------+
                              ^
                              | implements
                    SequentialTaskRouter


                    <<abstract>> ExecutionStrategy
                    +------------------------------------+
                    | run(agents, task, retry_policy)     |
                    +------------------------------------+
                              ^
                              | implements
                    SequentialExecutionStrategy
                    +------------------------------------+
                    | - _execute_with_retry(agent, task,  |
                    |     retry_policy)                    |
                    +------------------------------------+


        AgentRegistry                    RetryPolicy <<dataclass>>
   +----------------------+          +---------------------------+
   | register(agent)       |          | max_retries: int = 1       |
   | unregister(name)       |          | retry_on_failure: bool     |
   | get(name)               |          +---------------------------+
   | list_names()             |
   +----------------------+


                      SupervisorAgent
        +--------------------------------------------+
        | - name: str                                  |
        | - _memory_manager: MemoryManager              |
        | - _registry: AgentRegistry                     |
        | - _task_router: TaskRouter                      |
        | - _execution_strategy: ExecutionStrategy         |
        | - _retry_policy: RetryPolicy                      |
        | - _last_trace: ExecutionTrace | None                |
        +--------------------------------------------+
        | + register_agent(agent)                            |
        | + unregister_agent(name)                              |
        | + list_agents()                                         |
        | + run(task, agent_order=None) -> SupervisorResult         |
        | + get_last_execution_trace()                                |
        | - _build_final_report(trace, success)                         |
        +--------------------------------------------+


   AgentExecutionRecord <<dataclass>>       ExecutionTrace <<dataclass>>
   +---------------------------+            +--------------------------+
   | agent_name, status,        |            | task                     |
   | attempts, output, error,    |            | records: list[...]       |
   | started_at, ended_at,        |            | supervisor_reasoning:[..]|
   | reasoning_log                 |            +--------------------------+
   +---------------------------+

                    SupervisorResult <<dataclass>>
                    +--------------------------------+
                    | success, task, outputs,          |
                    | execution_trace, final_report     |
                    +--------------------------------+
```

## 5. Sequence Diagram (ASCII)

```
Caller          SupervisorAgent        TaskRouter      ExecutionStrategy      Agent (x N)      MemoryManager
  |                    |                    |                    |                  |                |
  |--run(task)-------->|                    |                    |                  |                |
  |                    |--log("received_task")                   |                  |                |
  |                    |--decide_agents()--->|                    |                  |                |
  |                    |<--[agent names]------|                    |                  |                |
  |                    |--log("agents_selected")                  |                  |                |
  |                    |                    |                    |                  |                |
  |                    |--run(agents, task, retry_policy)-------->|                  |                |
  |                    |                    |                    |--run(task)------>|                |
  |                    |                    |                    |<--AgentResult-----|                |
  |                    |                    |                    | (retry if failed) |                |
  |                    |<--[AgentExecutionRecord, ...]-------------|                  |                |
  |                    |--log("execution_complete")               |                  |                |
  |                    |--_build_final_report()                    |                  |                |
  |                    |--log("report_built")                       |                  |                |
  |                    |--store(name, task, report, metadata)------------------------------------------>|
  |                    |<-----------------------------------------------------------------MemoryEntry---|
  |                    |--log("stored_to_memory")                   |                  |                |
  |<--SupervisorResult-|                    |                    |                  |                |
```

## 6. Component Interaction
- **SupervisorAgent → TaskRouter**: exactly one call per run,
  `decide_agents()`. Supervisor never inspects task content itself.
- **SupervisorAgent → ExecutionStrategy**: exactly one call per run,
  `run()`, receiving already-resolved `BaseAgent` instances (missing
  names are filtered out and recorded as `SKIPPED` before this call).
- **ExecutionStrategy → BaseAgent**: one or more `.run(task)` calls
  per agent, governed by `RetryPolicy`.
- **SupervisorAgent → MemoryManager**: exactly one `store()` call per
  run, under the Supervisor's own `name` — keeps each Supervisor's
  history separate if multiple Supervisors exist later.

## 7. Why This Architecture Was Chosen
The project brief explicitly demands the Supervisor survive future
requirements (100+ agents, parallel/async execution, human approval,
Decision Auditor, AI Judge, Agent Discussion, Why-Not Analysis,
Workflow Optimizer) **without breaking existing code**. The only way
to guarantee that is to ensure `SupervisorAgent` itself contains no
logic that would need to change — all the logic that *would* change
(how agents are chosen, how they execute) is isolated behind
`TaskRouter` and `ExecutionStrategy`. Adding a `ParallelExecutionStrategy`
or an `LLMPlannerTaskRouter` later means writing a new class, not
editing `SupervisorAgent`.

## 8. Alternative Designs Considered

| Alternative | Why rejected |
|---|---|
| Hardcode a fixed agent execution order inside `SupervisorAgent.run()` | Fails the "100+ agents" and "dynamic registration" requirements immediately; every new agent would require editing Supervisor code |
| Let `SupervisorAgent.run()` raise on any agent failure | Violates the fault-isolation philosophy established in Module 1.1; one bad agent would take down the whole run |
| Put retry logic inside `BaseAgent` itself instead of the Supervisor layer | Retry is an orchestration concern (how many times to re-invoke), not an agent concern (what the agent does) — keeping it in `ExecutionStrategy` matches Single Responsibility and lets different Supervisors apply different retry policies to the same agent |
| Single `Executor` class combining routing + execution + retry | Violates Single Responsibility; would need to change for parallel execution AND for smarter routing simultaneously, increasing risk of breaking one while changing the other |
| Async/parallel execution implemented now | Explicitly out of scope per project brief; premature complexity without Planner/Research agents yet existing to actually parallelize |

## 9. How Future Requirements Plug In (Without Breaking This Module)

| Future requirement | Extension point |
|---|---|
| 100+ agents | `AgentRegistry` is a plain dict lookup — no structural limit; a `DistributedAgentRegistry` could replace it behind the same 4-method interface |
| Parallel execution | New `ParallelExecutionStrategy(ExecutionStrategy)` — implements the same `run()` signature using a thread/process pool |
| Async execution | New `AsyncExecutionStrategy` — `SupervisorAgent.run()` would gain an `async def arun()` twin calling it; existing sync `run()` untouched |
| Human approval workflows | New `HumanApprovalExecutionStrategy` wraps any other strategy, pausing between agents pending approval |
| Decision Auditor / AI Judge | Registered as ordinary `BaseAgent` subclasses, added to the routing order like any other agent — no Supervisor change needed |
| Agent Discussion | New `ExecutionStrategy` that runs a sub-loop of agents referencing each other's outputs before finalizing |
| Why-Not Analysis | Reads `ExecutionTrace.records` for agents that were `SKIPPED` or considered-but-not-selected (would require `TaskRouter` to optionally report rejected candidates — additive change, not breaking) |
| Workflow Optimizer | New `TaskRouter` implementation that uses historical `MemoryManager` data to choose agent order — routing logic only, no Supervisor change |
| LLM-driven Planner Agent | New `TaskRouter` implementation calling an LLM via `LLMInterface` (Module 1.2) to decide agents dynamically |

## 10. Advantages
- Zero-change extensibility for routing and execution strategy swaps.
- Full explainability trace by default — every run is auditable.
- Provider-independent and agent-implementation-independent by
  construction, not just by convention.
- Testable in complete isolation using mock agents (proven by 24
  passing tests with zero real LLM calls).

## 11. Limitations
- `SequentialTaskRouter` performs no actual task analysis — it's a
  placeholder until a real Planner Agent or LLM-driven router exists.
- Execution is strictly synchronous/sequential in this module; a
  slow agent blocks all agents after it.
- Retry policy is uniform across all agents in a run — no per-agent
  override yet (would be a natural next addition: a
  `dict[str, RetryPolicy]` keyed by agent name).
- No timeout mechanism — a hung agent's `.run()` call would block
  the Supervisor indefinitely. Worth flagging as a follow-up.
- `ExecutionTrace` and `SupervisorResult` are held only in memory for
  the caller and in `MemoryManager` as a text report + metadata dict —
  not queryable as structured data from memory yet (would need
  `MemoryManager` to store richer objects, or a dedicated trace store).

## 12. Future Improvements
- Add `AsyncExecutionStrategy` and `ParallelExecutionStrategy` once
  real agents exist to benefit from concurrency.
- Add per-agent timeout handling in `SequentialExecutionStrategy`.
- Add per-agent `RetryPolicy` overrides.
- Persist structured `ExecutionTrace` objects (not just text reports)
  once a richer storage backend (SQLite/FAISS metadata) is available.
- Add a `WorkflowOptimizerTaskRouter` that learns agent ordering from
  `MemoryManager` history.