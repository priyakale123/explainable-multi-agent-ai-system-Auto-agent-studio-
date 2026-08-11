# agents/coding/TESTING.md

# Module 2.4 — Coding Agent — Testing Document

## 1. Test Strategy
All 22 tests use fakes (`ScriptedLLM`, `RaisingLLM`, `FakeMemory`,
`RaisingMemory`, plus a `CapturingLLM` for one prompt-content check) —
no real LLM calls, no real code execution, no filesystem writes
anywhere, matching every prior module's testing philosophy.
`ScriptedLLM` returns a fixed, pre-built JSON string so each test
controls exactly what the "LLM" says, isolating Coding's
parsing/validation logic from actual model behavior.

Three layers are tested:
1. `CodingAgent` in isolation — prompt building, output parsing, all
   validation failure modes, per-file field preservation
2. Provider-independence and architectural-boundary checks — Coding
   never imports an LLM SDK, never imports Supervisor/Planner/Research,
   never implements retry logic, and never performs execution or
   filesystem I/O
3. Integration — `CodingAgent` registered with a real, unmodified
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
- `RaisingMemory` — satisfies the same Protocol but raises
  `RuntimeError` from `update_context()`, simulating a memory backend
  failure (new relative to Research's mock set, per the spec's
  explicit "memory failure" test requirement).

## 3. Unit Tests
| # | Test | Covers required case |
|---|---|---|
| 1 | `test_coding_agent_initializes_like_any_base_agent` | CodingAgent initialization |
| 2 | `test_valid_coding_request_produces_structured_result` | Successful coding request |
| 3 | `test_valid_json_parsing_preserves_file_fields` | Valid JSON parsing |
| 4 | `test_coding_agent_sends_objective_and_context_to_llm` | LLM interaction |
| 5 | `test_malformed_json_response_fails_gracefully` | Malformed JSON |
| 6 | `test_missing_files_key_fails_gracefully` | Missing keys |
| 7 | `test_dependencies_wrong_type_fails_gracefully` | Wrong data types |
| 8 | `test_assumptions_wrong_type_fails_gracefully` | Wrong data types (variant) |
| 9 | `test_unrecognized_language_fails_gracefully` | Wrong data types (invalid language) |
| 10 | `test_empty_content_fails_gracefully` | Valid code content check |
| 11 | `test_duplicate_file_id_fails_gracefully` | Duplicate file identifiers |
| 12 | `test_llm_failure_is_caught_not_raised` | LLM failure |
| 13 | `test_memory_failure_is_caught_not_raised` | Memory failure |
| 14 | `test_empty_objective_fails_gracefully` | Empty coding request |
| 15 | `test_empty_files_list_fails_gracefully` | Empty coding request (empty result case) |
| 16 | `test_coding_agent_uses_injected_llm_and_memory` | Dependency injection |
| 17 | `test_coding_agent_module_imports_no_llm_provider_sdk` | No external LLM SDK import |
| 18 | `test_coding_agent_module_never_imports_supervisor_or_other_agents` | No Supervisor/Planner/Research imports |
| 19 | `test_coding_agent_module_has_no_retry_logic` | No retry logic |
| 20 | `test_coding_agent_module_has_no_execution_logic` | No execution logic |
| 21 | `test_generated_code_is_returned_not_executed` | Generated code returned but not executed |
| 22 | `test_coding_agent_can_be_registered_with_real_supervisor` | Integrates cleanly with existing architecture |

## 4. Architectural-Boundary Tests (Detail)
Tests 17-20 inspect `coding_agent.py`'s own source text rather than
runtime behavior, matching the pattern established in
`test_research_agent.py`/`test_planner_agent.py`:
- Test 17 checks for `"anthropic"`/`"openai"`/`"api_key"` anywhere in
  the source.
- Tests 18-19 check only the file's actual `import`/`from` lines for
  `"supervisor"`/`"planner"`/`"research_agent"`/`"retry"` — **not**
  the full source text, since this module's own docstrings
  legitimately describe what it does *not* do (e.g. "does not
  implement retry logic"), which would otherwise cause a
  false-positive failure (the exact pitfall documented in Research's
  TESTING.md Section 7, avoided here from the start).
- Test 20 is new for this module: it scans the **full** lowercased
  source for `subprocess`, `os.system`, `exec(`, `eval(`, `shutil`,
  and `open(` — a direct check of the module spec's "no execution,
  no filesystem access" constraint. Full-source scanning is safe
  here specifically because none of those tokens legitimately appear
  in this module's own prose (unlike `"retry"` or `"supervisor"`,
  which do appear in explanatory docstrings).

## 5. Integration Test (Detail)
`test_coding_agent_can_be_registered_with_real_supervisor`:
1. Creates a real `MemoryManager` (Module 1.3) and real
   `SupervisorAgent` (Module 2.1) — neither mocked.
2. Registers a `CodingAgent` instance built with `ScriptedLLM`.
3. Calls `supervisor.run(CodingRequest(...), agent_order=["Coder"])`.
4. Confirms `result.success is True` and `result.outputs["Coder"]` is
   a genuine `CodeGenerationResult`.

This proves `CodingAgent` requires **zero** changes to
`SupervisorAgent` to function as a registered worker agent — it's
just another `BaseAgent` subclass from Supervisor's point of view,
exactly as `ResearchAgent` (Module 2.3) already proved.

## 6. How to Run Tests
```bash
# Coding module only
pytest tests/test_coding_agent.py -v

# full project (regression check)
pytest tests/ -v
```

## 7. Results & Notes From Development
Applying the source-scan lesson already documented in Research's
TESTING.md (Section 7) from the start, tests 18-19 were written to
scan only `import`/`from` lines rather than full source text, so no
false positives occurred during initial development.

Test run: **22/22 passed** on first execution.

Full project re-run after adding this module: all prior modules'
tests unaffected (Module 1.1: 11, Module 1.2: 12 — see
`PROJECT_JOURNAL.md`'s per-module counts for the locked foundation
modules — Module 2.1: 24, Module 2.2: 21, Module 2.3: 21,
Module 2.4: 22) — **129/129 passed project-wide, zero regressions.**

## 8. Common Errors and Solutions
| Error | Likely cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'agents.coding'` | Missing `agents/coding/__init__.py`, or not running from project root | Confirm the file exists; run pytest from the project root |
| A source-scan test fails after editing a docstring/comment | New docstring text happens to contain a scanned keyword | If the mention is legitimate prose (not an actual import or execution call), scan only import lines (Section 4) rather than full source, following the pattern already established for the supervisor/planner/retry checks |
| `CodingValidationError: File ... has unrecognized language` in a test that expected success | `ScriptedLLM`'s canned response uses a language not in `ALLOWED_LANGUAGES` | Fix the fixture JSON, not the agent — this is the agent correctly rejecting invalid input |
| `result.output.objective` is `None` unexpectedly | `_build_prompt()` was never called before `_parse_output()` in a hand-rolled test bypassing `run()` | Always exercise the agent through `.run()`, not by calling `_build_prompt`/`_parse_output` directly — `objective` is captured as a side effect of `_build_prompt` during a normal `run()` call |

## 9. Status
✅ 22/22 Coding tests passing. All 16 required test-case categories
from the spec covered (successful request, valid JSON parsing,
malformed JSON, missing keys, wrong data types, duplicate file
identifiers, empty coding request, LLM failure, memory failure, no
external LLM SDK import, no Supervisor/Planner/Research imports, no
execution logic, no retry logic, generated code returned but not
executed). `agents/supervisor/supervisor_agent.py`, `agents/planner/*`,
and `agents/research/*` unmodified. **129/129 tests passing
project-wide.**