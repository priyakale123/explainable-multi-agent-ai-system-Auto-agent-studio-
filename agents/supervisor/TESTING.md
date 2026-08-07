# Module 2.1 — Supervisor Agent — Testing Document

## 1. Testing Strategy
`SupervisorAgent` is tested entirely with **mock agents** — simple
`BaseAgent` subclasses with scripted behavior (`AlwaysSucceedsAgent`,
`AlwaysFailsAgent`, `SucceedsOnSecondAttemptAgent`). No real
Planner/Research/Coding/etc. agent exists yet, and none is needed to
fully exercise Supervisor's orchestration logic — that's the point of
depending only on the `BaseAgent` abstraction.

Four layers are tested:
1. `AgentRegistry` in isolation (registration bookkeeping)
2. `SequentialTaskRouter` in isolation (routing decisions)
3. `SequentialExecutionStrategy` in isolation (execution + retry)
4. `SupervisorAgent` end-to-end (orchestration, memory integration,
   reasoning trace, final report)

## 2. Test Cases

| # | Test name | What it verifies |
|---|---|---|
| 1 | `test_agent_registry_register_and_get` | Basic registration and lookup |
| 2 | `test_agent_registry_get_missing_returns_none` | Missing lookups return `None`, don't raise |
| 3 | `test_agent_registry_unregister` | Unregistration removes an agent |
| 4 | `test_agent_registry_register_overwrites` | Re-registering the same name replaces, doesn't duplicate |
| 5 | `test_sequential_task_router_default_returns_all_in_order` | No explicit order → all agents, registration order |
| 6 | `test_sequential_task_router_explicit_order_filters_unavailable` | Explicit order filters out unregistered names, preserves given sequence |
| 7 | `test_supervisor_register_and_list_agents` | `SupervisorAgent.register_agent()` + `list_agents()` |
| 8 | `test_supervisor_unregister_agent` | `SupervisorAgent.unregister_agent()` |
| 9 | `test_supervisor_run_success_single_agent` | Full happy path, single agent |
| 10 | `test_supervisor_run_success_multiple_agents_sequential_order` | Multiple agents run in registration order |
| 11 | `test_supervisor_run_respects_explicit_agent_order` | `agent_order` param overrides the router |
| 12 | `test_supervisor_run_records_agent_failure` | A failing agent is recorded as `FAILED`, doesn't crash the run |
| 13 | `test_supervisor_run_missing_agent_is_skipped_not_crashed` | Requesting an unregistered agent name → `SKIPPED`, not an exception |
| 14 | `test_supervisor_run_no_agents_registered` | Empty registry → `success=False`, empty records, no crash |
| 15 | `test_supervisor_retries_and_recovers` | An agent that fails once then succeeds is retried and recorded as `SUCCESS` with `attempts=2` |
| 16 | `test_supervisor_no_retry_when_disabled` | `retry_on_failure=False` → exactly 1 attempt even on failure |
| 17 | `test_supervisor_exhausts_max_retries_on_permanent_failure` | `max_retries=2` on an always-failing agent → exactly 3 attempts, final status `FAILED` |
| 18 | `test_supervisor_reasoning_log_has_expected_steps` | Supervisor's own reasoning trace has the 5 expected steps in order |
| 19 | `test_supervisor_agent_execution_record_carries_agent_reasoning_log` | Each agent's own `reasoning_log` (from Module 1.1) is preserved inside its `AgentExecutionRecord` |
| 20 | `test_get_last_execution_trace_returns_most_recent_run` | `get_last_execution_trace()` returns `None` before any run, and the latest trace after |
| 21 | `test_supervisor_stores_result_in_memory_manager` | `MemoryManager.store()` is called with the correct name, report, and metadata |
| 22 | `test_supervisor_multiple_runs_accumulate_in_memory` | Two `run()` calls produce two memory entries, not one overwritten entry |
| 23 | `test_final_report_contains_agent_names_and_status` | Human-readable report mentions every agent and its outcome |
| 24 | `test_execution_strategy_runs_agents_in_given_order` | `SequentialExecutionStrategy.run()` tested directly, without `SupervisorAgent` |

## 3. Expected Outputs

**Test 15 — retry and recovery:**
```
result.success == True
result.execution_trace.records[0].attempts == 2
result.execution_trace.records[0].status == AgentExecutionStatus.SUCCESS
```

**Test 17 — retries exhausted:**
```
result.success == False
result.execution_trace.records[0].attempts == 3   # 1 initial + 2 retries
result.execution_trace.records[0].status == AgentExecutionStatus.FAILED
```

**Test 18 — reasoning log steps, in order:**
```
["received_task", "agents_selected", "execution_complete", "report_built", "stored_to_memory"]
```

## 4. Edge Cases
- **Empty registry** (`run()` with zero registered agents) — must not
  crash; returns `success=False` with an empty `records` list.
- **`agent_order` referencing a name that was never registered** —
  must be recorded as `SKIPPED`, not raise `KeyError`.
- **`max_retries=0`** — exactly one attempt, no retry loop entered.
- **Re-registering an agent under an existing name** — must overwrite
  silently (with a logged warning), not duplicate or raise.
- **`retry_on_failure=False` combined with a high `max_retries`** —
  `max_retries` must be ignored; exactly one attempt.
- **Multiple `run()` calls on the same `SupervisorAgent` instance** —
  each call must produce its own independent `ExecutionTrace`, and
  `MemoryManager` must accumulate entries rather than overwrite.

## 5. Failure Scenarios

| Scenario | Where it's handled | Resulting behavior |
|---|---|---|
| An agent's `_parse_output` raises | Inside `BaseAgent.run()` (Module 1.1) — already returns `AgentResult(success=False)` | `SequentialExecutionStrategy` sees `success=False`, retries per policy, then records `FAILED` |
| Requested agent name not registered | `SupervisorAgent.run()`, before calling `ExecutionStrategy` | Recorded as `SKIPPED` with an explanatory error message; execution continues for other agents |
| Zero agents selected (empty registry, or router returns `[]`) | `SupervisorAgent.run()` | `success=False`, empty `records`, no exception |
| `MemoryManager.store()` itself raises (e.g. a future backend failure) | **Not currently caught** — see Limitations in DESIGN.md | Would propagate as an exception out of `run()`; flagged as a known gap, not yet handled |

## 6. How to Run Tests
```bash
# from project root
pytest tests/test_supervisor.py -v

# run the whole project together
pytest tests/ -v

# run a single test
pytest tests/test_supervisor.py::test_supervisor_retries_and_recovers -v
```

## 7. Debugging Guide
1. **Start with `result.execution_trace.supervisor_reasoning`** — this
   is the Supervisor's own step-by-step log; it tells you exactly
   where in the pipeline something diverged from expectation.
2. **Then check `result.execution_trace.records`** — per-agent status,
   attempts, and error message. This is usually where the real
   failure detail lives (e.g. `AlwaysFailsAgent` failures show up here
   with `error="simulated permanent failure"`).
3. **For retry-related test failures**, print `record.attempts`
   directly — a mismatch here usually means `RetryPolicy.max_retries`
   or `retry_on_failure` was set differently than the test assumed.
4. **For memory-related test failures**, call
   `memory_manager.get_statistics(supervisor.name)` to confirm how
   many entries actually landed, and under which name.

## 8. Common Errors and Solutions

| Error | Likely cause | Solution |
|---|---|---|
| `TypeError: Can't instantiate abstract class BaseAgent...` in a mock agent | Mock agent subclass didn't implement both `_build_prompt` and `_parse_output` | Implement both abstract methods, matching Module 1.1's contract |
| `AssertionError` on `attempts` count | Off-by-one confusion between "retries" and "total attempts" | Remember: `max_retries=N` means `N+1` total attempts when `retry_on_failure=True` |
| Agent recorded as `SKIPPED` unexpectedly | Agent name in `agent_order` doesn't exactly match the name passed to `make_agent()` / the agent's `.name` | Names are case-sensitive exact matches — verify spelling |
| `memory_manager.get_recent(name, ...)` returns empty | Wrong `name` used — remember `SupervisorAgent.run()` stores under `self.name` (the *Supervisor's* name), not an agent's name | Query with the Supervisor's `name` (defaults to `"Supervisor"`) |
| Two `run()` calls seem to overwrite each other in memory | Using `ConversationMemory` without a `max_entries` cap should never truncate at 2 entries — check you're calling `get_statistics()`, not `get_recent(name, n=1)`, which only shows the latest one by design | Use `get_statistics()` to see the true total count |

## 9. Status
✅ 24/24 tests passing. All Supervisor responsibilities from the
project brief (registration, routing, sequential execution, retry,
error handling, memory integration, reasoning log, final report) are
covered. Planner/Research/Coding/etc. agents, parallel/async
execution, and human approval workflows are explicitly out of scope
for this module's tests, per project instructions.