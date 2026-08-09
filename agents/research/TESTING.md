# Module 2.3 — Research Agent — Testing Document

## 1. Test Strategy
All 21 tests use fakes (`ScriptedLLM`, `RaisingLLM`, `FakeMemory`,
plus a `CapturingLLM` for one prompt-content check) — no real LLM
calls, no real web/API calls anywhere, matching every prior module's
testing philosophy. `ScriptedLLM` returns a fixed, pre-built JSON
string so each test controls exactly what the "LLM" says, isolating
Research's parsing/validation logic from actual model behavior.

Three layers are tested:
1. `ResearchAgent` in isolation — prompt building, output parsing,
   all validation failure modes, deduplication, conflict preservation
2. Provider-independence and architectural-boundary checks — Research
   never imports an LLM SDK, never imports Supervisor/Planner, never
   implements retry logic
3. Integration — `ResearchAgent` registered with a real, unmodified
   `SupervisorAgent` and run end-to-end

## 2. Mocks
- `ScriptedLLM(response)` — always returns the given string; satisfies
  `BaseAgent`'s `LLMInterface` Protocol (`generate(prompt) -> str`)
  structurally.
- `RaisingLLM` — always raises `RuntimeError`, simulating an API failure.
- `CapturingLLM` — records every prompt it receives, used only to
  verify the objective/context actually reach the LLM call.
- `FakeMemory` — satisfies the `AgentMemory` Protocol
  (`get_context()`, `update_context()`) with no-op behavior.

## 3. Unit Tests
| # | Test | Covers required case |
|---|---|---|
| 1 | `test_research_agent_initializes_like_any_base_agent` | 1. ResearchAgent initialization |
| 2 | `test_valid_research_task_produces_structured_report` | 2+3. Valid research task, structured research result |
| 3 | `test_research_agent_sends_objective_and_context_to_llm` | 4. LLM interaction |
| 4 | `test_malformed_json_response_fails_gracefully` | 5. Malformed LLM response |
| 5 | `test_missing_findings_key_fails_gracefully` | 5. Malformed LLM response (variant) |
| 6 | `test_llm_failure_is_caught_not_raised` | 6. LLM failure |
| 7 | `test_duplicate_finding_id_fails_gracefully` | 7. Duplicate finding handling |
| 8 | `test_duplicate_statement_is_silently_merged_not_repeated` | 7. Duplicate finding handling (content-level) |
| 9 | `test_all_findings_duplicate_fails_gracefully` | 7. Duplicate finding handling (guard regression check) |
| 10 | `test_conflicting_evidence_is_preserved_not_dropped` | 8. Conflicting information handling |
| 11 | `test_source_is_preserved_when_provided` | 9. Source handling |
| 12 | `test_source_defaults_to_empty_string_when_absent` | 9. Source handling (absent case) |
| 13 | `test_confidence_out_of_range_fails_gracefully` | 10. Confidence handling |
| 14 | `test_confidence_non_numeric_fails_gracefully` | 10. Confidence handling (type case) |
| 15 | `test_empty_objective_fails_gracefully` | 11. Empty task handling |
| 16 | `test_empty_findings_list_fails_gracefully` | 11. Empty task handling (empty result case) |
| 17 | `test_research_agent_uses_injected_llm_and_memory` | 12. Dependency injection |
| 18 | `test_research_agent_module_imports_no_llm_provider_sdk` | 13. No direct provider dependency |
| 19 | `test_research_agent_module_never_imports_supervisor_or_other_agents` | 14. Does not execute other agents |
| 20 | `test_research_agent_module_has_no_retry_logic` | 15. Does not implement retry logic |
| 21 | `test_research_agent_can_be_registered_with_real_supervisor` | 16. Integrates cleanly with existing architecture |

## 4. Architectural-Boundary Tests (Detail)
Tests 18-20 inspect `research_agent.py`'s own source text rather than
runtime behavior, matching the pattern already established in
`test_planner_agent.py`:
- Test 18 checks for `"anthropic"`/`"openai"`/`"api_key"` anywhere in
  the source.
- Tests 19-20 check only the file's actual `import`/`from` lines for
  `"supervisor"`/`"planner"`/`"retry"` — **not** the full source text,
  since this module's own docstrings legitimately describe what it
  does *not* do (e.g. "does not implement retry logic"), which would
  otherwise cause a false-positive failure. This distinction was
  discovered and fixed during initial test runs (see Section 7).

## 5. Integration Test (Detail)
`test_research_agent_can_be_registered_with_real_supervisor`:
1. Creates a real `MemoryManager` (Module 1.3) and real
   `SupervisorAgent` (Module 2.1) — neither mocked.
2. Registers a `ResearchAgent` instance built with `ScriptedLLM`.
3. Calls `supervisor.run(ResearchRequest(...), agent_order=["Researcher"])`.
4. Confirms `result.success is True` and
   `result.outputs["Researcher"]` is a genuine `ResearchReport`.

This proves `ResearchAgent` requires **zero** changes to
`SupervisorAgent` to function as a registered worker agent — it's
just another `BaseAgent` subclass from Supervisor's point of view.

## 6. How to Run Tests
```bash
# Research module only
pytest tests/test_research_agent.py -v

# full project (regression check)
pytest tests/ -v
```

## 7. Results & Notes From Development
Initial test run: 19/21 passed, 2 failed —
`test_research_agent_module_never_imports_supervisor_or_other_agents`
and `test_research_agent_module_has_no_retry_logic` both failed
because they scanned the **entire** module source (including its own
docstrings, which legitimately mention "SupervisorAgent" and "retry"
in prose explaining what the module does *not* do). Fixed by scanning
only actual `import`/`from` statement lines instead of full source
text. Re-run: **21/21 passed.**

Full project re-run after the fix: all prior modules' tests
unaffected (Module 1.1: 12, Module 1.2: 11, Module 2.1: 24,
Module 2.2: 21, Module 2.3: 21 — see final verification report for
the authoritative combined count).

## 8. Common Errors and Solutions
| Error | Likely cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'agents.research'` | Missing `agents/research/__init__.py`, or not running from project root | Confirm the file exists; run pytest from the project root |
| A source-scan test fails after editing a docstring/comment | New docstring text happens to contain a scanned keyword | If the mention is legitimate prose (not an actual import), the test should scan only import lines, not full source — follow the pattern in Section 4 |
| `ResearchValidationError: Finding ... confidence must be between 0.0 and 1.0` in a test that expected success | `ScriptedLLM`'s canned response has a confidence value outside range | Fix the fixture JSON, not the agent — this is the agent correctly rejecting invalid input |
| `result.output.objective` is `None` unexpectedly | `_build_prompt()` was never called before `_parse_output()` in a hand-rolled test bypassing `run()` | Always exercise the agent through `.run()`, not by calling `_build_prompt`/`_parse_output` directly — `objective` is captured as a side effect of `_build_prompt` during a normal `run()` call |

## 9. Status
✅ 21/21 Research tests passing. All 16 required test cases from the
spec covered. `agents/supervisor/supervisor_agent.py` and
`agents/planner/*` unmodified. See the final verification report
(Step 10) for the authoritative full-project test count.