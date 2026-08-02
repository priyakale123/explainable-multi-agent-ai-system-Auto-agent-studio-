# Module 1.1 — Agent Core — Design Document

## 1. Purpose

`agents/base_agent.py` defines the foundational abstraction that every agent
in the Auto-Built Multi-Agent System inherits from. It exists to guarantee
that no matter how many specialized agents this project eventually has
(ResearchAgent, CoderAgent, CriticAgent, ...), they all:

- Expose the exact same interface to the Supervisor (`run(task) -> AgentResult`)
- Produce a step-by-step reasoning trace automatically, with zero extra
  effort from whoever writes the subclass
- Fail safely, returning a structured failure instead of raising an
  exception that could crash the Supervisor's control loop

This file is the single point of truth for "what does it mean to be an
agent in this system."

## 2. Design Goals

| Goal | How it's achieved |
|---|---|
| **Uniform interface for the Supervisor** | `run()` is defined once, concretely, in `BaseAgent` — never reimplemented per agent |
| **Mandatory reasoning capture** | `_record_reasoning()` is called from inside `run()` itself, not left to subclass discipline |
| **Extensibility** | New agent types only need to implement 2 small abstract methods, not the whole pipeline |
| **Fault isolation** | One agent's failure must never propagate as an unhandled exception to the Supervisor |
| **Decoupling from unfinished modules** | `BaseAgent` depends on `LLMInterface` / `AgentMemory` *Protocols*, not concrete classes — Modules 1.2 and 1.3 can be built independently, in any order, without touching this file |
| **Testability** | Dependency injection (LLM + memory passed into constructor) means we can test `BaseAgent` today using fakes, without waiting for real modules |

## 3. Design Pattern Used

**Primary pattern: Template Method**
`run()` defines the fixed skeleton of "how any agent processes a task."
The variable parts — turning a task into a prompt, and turning raw LLM
text into structured output — are deferred to abstract methods
(`_build_prompt`, `_parse_output`) that subclasses must implement.

**Supporting pattern: Structural typing via Protocol (duck-typing contract)**
`LLMInterface` and `AgentMemory` are `typing.Protocol` classes, not ABCs.
This means Module 1.2's future `ClaudeLLMInterface` doesn't need to
explicitly inherit from `LLMInterface` — it just needs a matching
`generate()` method. This is Python's structural equivalent of
programming to an interface, and it keeps modules loosely coupled.

**Supporting pattern: Dependency Injection**
`llm_interface` and `memory` are passed into `__init__`, not constructed
inside `BaseAgent`. This is what makes the class independently testable
and swappable (e.g. swap Claude for OpenAI without touching agent logic).

## 4. Class Diagram (ASCII)

```
                         <<Protocol>>
                         LLMInterface
                    +----------------------+
                    | + generate(prompt)   |
                    +----------------------+
                              ^
                              | (structural — no inheritance needed)
                              |
                         <<Protocol>>
                         AgentMemory
                    +----------------------------+
                    | + get_context()            |
                    | + update_context(task,res) |
                    +----------------------------+
                              ^
                              | used by
                              |
        +---------------------------------------------+
        |            <<abstract>> BaseAgent            |
        +-----------------------------------------------+
        | - name: str                                    |
        | - role_description: str                        |
        | - llm_interface: LLMInterface                   |
        | - memory: AgentMemory                           |
        | - reasoning_log: list[dict]                     |
        +-----------------------------------------------+
        | + __init__(name, role_desc, llm, memory)        |
        | + run(task) -> AgentResult                       |
        | # _build_prompt(task, context) -> str  [abstract]|
        | # _parse_output(raw_output) -> Any     [abstract]|
        | - _record_reasoning(step_label, content)         |
        +-----------------------------------------------+
                              ^
                              | inherits
                +-------------+--------------+
                |                            |
      +-------------------+       +-----------------------+
      |   ResearchAgent   |  ...  |     CoderAgent         |
      |  (Milestone 2+)   |       |    (Milestone 2+)      |
      +-------------------+       +-----------------------+


                    +-------------------------+
                    |      AgentResult        |   <<dataclass>>
                    +-------------------------+
                    | agent_name: str          |
                    | output: Any              |
                    | reasoning_log: list[dict]|
                    | success: bool            |
                    | error: str | None        |
                    +-------------------------+
                    returned by BaseAgent.run()
```

## 5. Sequence Diagram (ASCII)

```
Supervisor        BaseAgent           LLMInterface        AgentMemory        ReasoningLog
    |                 |                     |                   |                 |
    |--run(task)----->|                     |                   |                 |
    |                 |--record("received_task")---------------------------------->|
    |                 |                     |                   |                 |
    |                 |--get_context()------------------------->|                 |
    |                 |<--context------------------------------ |                 |
    |                 |                     |                   |                 |
    |                 |--_build_prompt(task, context)            |                 |
    |                 |--record("built_prompt")------------------------------------>|
    |                 |                     |                   |                 |
    |                 |--generate(prompt)-->|                   |                 |
    |                 |<--raw_output--------|                   |                 |
    |                 |--record("llm_output")----------------------------------->  |
    |                 |                     |                   |                 |
    |                 |--_parse_output(raw_output)               |                 |
    |                 |--update_context(task, result)---------->|                 |
    |                 |--record("final_result")-------------------------------->   |
    |                 |                     |                   |                 |
    |<--AgentResult---|                     |                   |                 |
    |  (success=True, output, reasoning_log)|                   |                 |

  --- failure path (any step above raises an exception) ---
    |                 |--record("error", str(exc))------------------------------->|
    |<--AgentResult---|                     |                   |                 |
    |  (success=False, output=None, error=...)                  |                 |
```

## 6. Component Interaction

- **Supervisor → BaseAgent**: one call, `run(task)`. Supervisor never touches
  `_build_prompt` / `_parse_output` / `_record_reasoning` directly — those
  are internal to the agent.
- **BaseAgent → LLMInterface**: exactly one call per run, `generate(prompt)`.
  BaseAgent doesn't know or care if this is Claude, OpenAI, or a mock —
  only that it returns a string.
- **BaseAgent → AgentMemory**: two calls per run — read context before
  building the prompt, write the result back after parsing. Memory is
  agent-scoped context, not a global blackboard (that's a future
  Communication Bus concern, Milestone 4).
- **BaseAgent → reasoning_log**: internal, in-memory list. Nothing external
  writes to it directly — only `_record_reasoning()` does, guaranteeing a
  consistent format every time.

## 7. Why This Architecture Was Chosen

The central requirement of your project is the **Internal Reasoning
Summary** — meaning reasoning capture cannot be optional or
inconsistently implemented per agent. Baking `_record_reasoning()` calls
directly into the concrete `run()` method (rather than trusting each
subclass to remember to log) makes reasoning capture a **structural
guarantee**, not a convention. This is the single most important
architectural decision in this module and it flows from your project's
own differentiator.

The Protocol-based dependency contracts (`LLMInterface`, `AgentMemory`)
let us build Milestone 1 modules in parallel/independently — 1.1 doesn't
block on 1.2 or 1.3 being finished, and none of them block on knowing the
final LLM provider choice (relevant since you chose "provider-agnostic").

## 8. Alternative Designs Considered

| Alternative | Why rejected |
|---|---|
| **No base class — each agent fully independent** | Would let reasoning-log calls be forgotten in some agents; no compile-time/instantiation-time enforcement of a shared interface; Supervisor would need per-agent-type handling logic |
| **Reasoning logging left to subclasses (call `self.log()` manually wherever they want)** | Inconsistent trace granularity across agents; defeats the goal of a uniform, comparable reasoning summary across the whole system |
| **Concrete base classes for LLM/Memory instead of Protocols** | Would force Module 1.1 to depend on Modules 1.2/1.3 existing first, blocking parallel development, and would hard-couple BaseAgent to one LLM provider — conflicts with your "provider-agnostic" decision |
| **Let exceptions propagate up instead of catching in `run()`** | One malfunctioning agent could crash the entire Supervisor loop — unacceptable in a multi-agent system where partial failure should be recoverable |

## 9. Advantages

- New agent types are cheap to add — implement 2 methods, get logging,
  error handling, and a uniform interface for free.
- Reasoning trace format is guaranteed consistent across every agent,
  which directly supports Milestone 3.
- Fully testable in isolation today, without Modules 1.2/1.3 existing.
- Failure of one agent is contained and reported, not fatal.

## 10. Limitations

- `run()` is synchronous — a slow LLM call blocks the whole thread. Fine
  for now (single-agent testing), but Milestone 4 (Execution Runtime)
  will need an async version for real concurrent multi-agent execution.
- `reasoning_log` lives only in memory per run — nothing persists it yet.
  That's intentionally Module 3.3's job (Reasoning Log Store).
- No retry logic on LLM failures — a transient rate-limit error currently
  ends the run as a failure rather than retrying.
- `memory.get_context()` currently has no way to request *only* relevant
  context — it returns whatever the memory implementation decides to
  return. May need filtering parameters once Module 1.3 is built.

## 11. Future Improvements

- Convert `run()` to `async def run()` when building Module 4.2, so the
  Supervisor can run multiple agents concurrently with `asyncio.gather`.
- Add configurable retry/backoff for `llm_interface.generate()` calls.
- Add a `max_reasoning_log_size` guard so extremely long-running agents
  don't grow an unbounded in-memory list.
- Consider a `Enum` for `step_label` in `_record_reasoning` instead of
  free-form strings, once Module 3.1 needs to parse/categorize steps
  reliably.