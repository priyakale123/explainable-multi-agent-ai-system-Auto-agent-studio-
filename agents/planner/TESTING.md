# Module 2.2 — Planner Agent — Testing Document

## 1. Unit Testing Strategy
All 21 tests use fakes (`ScriptedLLM`, `RaisingLLM`, `FakeMemory`) —
no real LLM calls, matching every prior module's testing philosophy.
`ScriptedLLM` returns a fixed, pre-built JSON string so each test
controls exactly what the "LLM" says, isolating Planner's parsing and
validation logic from actual model behavior.

Three layers are tested:
1. `PlannerAgent` in isolation — prompt building, output parsing, all
   validation failure modes
2. `PlannerExecutionPlan` — dependency ordering, cycle/reference
   detection (exercised indirectly through `PlannerAgent`, since
   `_parse_output` calls `ordered_agent_names()` eagerly)
3. `PlannerTaskRouter` + real `SupervisorAgent` — integration tests
   proving the whole pipeline works with zero Supervisor changes

## 2. Mocked LLMInterface
Two fakes satisfy `BaseAgent`'s `LLMInterface` Protocol structurally
(just `generate(prompt) -> str`, per Module 1.1's actual definition):
- `ScriptedLLM(response)` — always returns the given string
- `RaisingLLM` — always raises `RuntimeError`, simulating an API failure

Neither imports or references `anthropic`/`openai` — confirmed
directly by `test_planner_module_imports_no_llm_provider_sdk`, which
inspects `planner_agent.py`'s own source text for those strings.

## 3. Planner Tests (Core Logic)
| # | Test | Covers required case |
|---|---|---|
| 1 | `test_planner_agent_initializes_like_any_base_agent` | 1. Planner initialization |
| 2 | `test_valid_task_produces_valid_plan` | 2. Valid task produces a valid plan |
| 3 | `test_correct_agent_selection` | 3. Correct agent selection |
| 4 | `test_correct_execution_order_from_dependencies` | 4. Correct execution order |
| 5 | `test_dependency_handling_reorders_when_declared_out_of_order` | 5. Dependency handling |
| 6 | `test_expected_output_and_rationale_are_preserved` | 6+7. Expected outputs, concise rationale |
| 7 | `test_empty_task_fails_gracefully` | 8. Empty task |
| 8 | `test_llm_failure_is_caught_not_raised` | 9. LLM failure |
| 9 | `test_malformed_json_response_fails_gracefully` | 10. Malformed LLM response |
| 10 | `test_missing_steps_key_fails_gracefully` | 10. Malformed LLM response (variant) |
| 11 | `test_router_falls_back_when_planner_chooses_unregistered_agent` | 11. Unknown agent |
| 12 | `test_duplicate_step_id_fails_gracefully` | 12. Duplicate step ID |
| 13 | `test_invalid_dependency_reference_fails_gracefully` | 13. Invalid dependency |
| 14 | `test_circular_dependency_fails_gracefully` | 14. Circular dependency |
| 15 | `test_empty_steps_list_fails_gracefully` | 15. Empty plan |
| 16 | `test_planner_never_calls_any_agent_run_method` | 16. Planner does not execute agents |
| 17 | `test_planner_uses_injected_llm_interface_via_base_agent` | 17. Planner uses existing LLMInterface |
| 18 | `test_planner_module_imports_no_llm_provider_sdk` | 18. No provider-specific clients |
| 19 | `test_planner_task_router_is_a_real_task_router_subclass` | 19. PlannerTaskRouter compatible with TaskRouter |
| 20 | `test_planner_task_router_drives_real_unmodified_supervisor_agent` | 20. Integrates with SupervisorAgent, unmodified |
| 21 | `test_planner_task_router_fallback_still_lets_supervisor_run` | Fallback path keeps Supervisor unblocked (additive) |

## 4. Validation Tests
Tests 9, 10, 12, 13, 14, 15 above specifically exercise
`PlanValidationError` / `DependencyError` paths:
- malformed JSON syntax
- missing required top-level key (`steps`)
- duplicate `step_id` across steps
- `depends_on` referencing a nonexistent step
- circular dependency chain (A depends on B, B depends on A)
- empty `steps` list

Each asserts `result.success is False` and inspects `result.error` for
a relevant substring — never a raised/uncaught exception.

## 5. Integration Testing With Supervisor
Two tests instantiate a **real, unmodified** `SupervisorAgent`:

- `test_planner_task_router_drives_real_unmodified_supervisor_agent` —
  registers two `RecordingAgent` mocks, injects `PlannerTaskRouter` as
  Supervisor's `task_router`, calls `supervisor.run()`, and confirms:
  both agents were actually invoked, in the Planner-decided order,
  and `router.get_last_plan()` exposes the Planner's reasoning.
- `test_planner_task_router_fallback_still_lets_supervisor_run` —
  forces the Planner to fail completely (`RaisingLLM`) and confirms
  Supervisor still completes successfully via the fallback router.

Together these prove the integration claim: Planner plugs into
Supervisor's existing `TaskRouter` extension point with **zero**
changes to `supervisor_agent.py` — verified by an md5 checksum
comparison before/after this module's implementation (unchanged).

## 6. How to Run Tests
```bash
# Planner module only
pytest tests/test_planner_agent.py -v

# full project (regression check)
pytest tests/ -v
```

## 7. Results
```
tests/test_planner_agent.py .....................  [21 passed]
tests/ (full project) ................................  [68 passed]
```
Zero failures, zero regressions in Module 1.1 (12 tests), Module 1.2
(11 tests), or Module 2.1 (24 tests).

## 8. Common Errors and Solutions
| Error | Likely cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'agents.planner'` | Missing `agents/planner/__init__.py`, or not running from project root | Confirm the file exists; run pytest from the project root |
| `PlanValidationError: Planner LLM did not return valid JSON` in a test that expected success | `ScriptedLLM`'s canned response has a JSON syntax error | Validate the JSON string with `json.loads()` manually before using it in a test fixture |
| `DependencyError: Circular dependency detected` appearing unexpectedly | Two steps' `depends_on` lists reference each other, even indirectly through a longer chain | Trace the `depends_on` chain by hand; the DFS reports the step it was revisiting when the cycle was detected |
| `test_planner_module_imports_no_llm_provider_sdk` fails after an edit | A docstring or comment in `planner_agent.py` mentions "anthropic" or "openai" in passing | Reword the docstring/comment — the test scans raw source text, not just imports |

## 9. Status
✅ 21/21 Planner tests passing. 68/68 project-wide. All 20 required
test cases from the spec covered (case 10 split into two focused
tests for clarity: JSON-syntax-invalid and structurally-invalid).
`agents/supervisor/supervisor_agent.py` confirmed byte-for-byte
unmodified (md5 checksum matched pre/post implementation).