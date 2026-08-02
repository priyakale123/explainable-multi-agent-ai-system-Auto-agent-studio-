# Module 1.1 — Agent Core — Testing Document

## 1. Testing Strategy

`BaseAgent` is abstract, so it cannot be tested directly — it's tested
through a minimal concrete subclass built purely for testing purposes
(`EchoAgent`), combined with fake implementations of `LLMInterface` and
`AgentMemory`. This is the standard approach for testing template-method
base classes: exercise the shared skeleton (`run()`) through the simplest
possible subclass, so any failure is clearly attributable to `BaseAgent`
itself and not to a specific agent's business logic.

Two layers of testing apply here:
1. **Unit tests** — test `BaseAgent.run()` in isolation using fakes for
   the LLM and memory dependencies (no real network calls).
2. **Contract tests** — confirm that any object satisfying the
   `LLMInterface` / `AgentMemory` Protocol shape works correctly, without
   needing explicit inheritance (validates the structural typing design
   decision from DESIGN.md).

No real LLM calls are made in this module's tests — that would make tests
slow, flaky, and dependent on API keys. Real-LLM integration testing
belongs to Module 1.2, once `ClaudeLLMInterface`/`OpenAILLMInterface`
exist.

## 2. Test Cases

| # | Test name | What it verifies |
|---|---|---|
| 1 | `test_run_success` | Full happy path: task in → `AgentResult` out, `success=True`, `output` correctly transformed, 4 reasoning steps recorded in order |
| 2 | `test_run_failure_llm_error` | LLM raises an exception → `run()` catches it, returns `success=False`, `error` populated, no unhandled exception escapes |
| 3 | `test_reasoning_log_reset_between_runs` | Calling `run()` twice on the same agent instance does not leak reasoning entries from the first run into the second |
| 4 | `test_reasoning_log_step_order` | Reasoning steps appear in the exact order: `received_task` → `built_prompt` → `llm_output` → `final_result` |
| 5 | `test_memory_context_used_in_prompt` | `_build_prompt` actually receives the context returned by `memory.get_context()` (dependency injection wired correctly) |
| 6 | `test_memory_updated_after_run` | `memory.update_context(task, result)` is called exactly once, with the correct task/result, after a successful run |
| 7 | `test_cannot_instantiate_base_agent_directly` | Instantiating `BaseAgent(...)` directly raises `TypeError` (proves abstract methods are enforced) |
| 8 | `test_subclass_missing_abstract_method_fails` | A subclass that implements only one of the two abstract methods still cannot be instantiated |
| 9 | `test_parse_output_error_is_caught` | If `_parse_output` itself raises, `run()` still returns a structured failure, not a crash |
| 10 | `test_agent_result_is_dataclass_equality` | Two `AgentResult` instances with identical field values compare equal (`==`) — confirms dataclass behavior isn't broken by future edits |

## 3. Expected Outputs

**Test 1 — `test_run_success`**
```
result.success == True
result.agent_name == "Echo"
result.output == "FAKE RESPONSE TO: TASK: HELLO"
result.error is None
len(result.reasoning_log) == 4
[step["step"] for step in result.reasoning_log] == [
    "received_task", "built_prompt", "llm_output", "final_result"
]
```

**Test 2 — `test_run_failure_llm_error`**
```
result.success == False
result.output is None
result.error == "API down"
result.reasoning_log[-1]["step"] == "error"
result.reasoning_log[-1]["content"] == "API down"
```

**Test 7 — `test_cannot_instantiate_base_agent_directly`**
```
pytest.raises(TypeError, match="abstract")
```

## 4. Edge Cases

- **Empty task** (`agent.run("")` or `agent.run(None)`) — should not crash;
  `_build_prompt` receives it as-is and it's the subclass's responsibility
  to handle empty input meaningfully. `BaseAgent` itself makes no
  assumption about task content or type.
- **Memory returns empty context** (`{}`) — `run()` must proceed normally;
  an empty dict is valid, not an error condition.
- **LLM returns an empty string** — `_parse_output("")` is called as
  normal; whether that's an error is subclass-specific, not BaseAgent's
  concern.
- **Very large `reasoning_log`** (e.g. a task that somehow triggers many
  internal steps) — not currently bounded; see Limitations in DESIGN.md.
- **Calling `run()` concurrently on the same agent instance from two
  threads** — currently unsafe, since `reasoning_log` is reset and
  mutated on `self`. Not a supported use case yet (documented in
  DESIGN.md's Limitations; async-safe execution is a Milestone 4 concern).

## 5. Failure Scenarios

| Scenario | Where it's caught | Resulting behavior |
|---|---|---|
| LLM call raises (timeout, rate limit, network error) | `run()`'s `try/except` around the whole pipeline | Returns `AgentResult(success=False, error=<message>)` |
| `_parse_output` raises (malformed LLM output) | Same `try/except` | Same — failure returned, not raised |
| `memory.get_context()` raises | Same `try/except` | Same — failure returned, not raised |
| Subclass forgets to implement `_build_prompt` or `_parse_output` | Python's `ABC` machinery, at instantiation time | `TypeError` raised immediately when the subclass is instantiated — fails fast, before `run()` is ever called |
| `memory.update_context()` raises after a successful LLM call | Same `try/except` | Failure returned — note that in this case `_parse_output` already succeeded, but the overall run is still marked failed since context wasn't persisted; worth discussing as a design tradeoff in your report |

## 6. How to Run Tests

```bash
# from project root
pip install pytest --break-system-packages

# run all tests for this module
pytest agents/test_base_agent.py -v

# run a single test case
pytest agents/test_base_agent.py::test_run_success -v

# run with print/log output visible
pytest agents/test_base_agent.py -v -s
```

## 7. Debugging Guide

**If a test fails, check in this order:**

1. **Read the assertion message first** — pytest shows exactly which
   value didn't match expectations.
2. **Check `result.reasoning_log`** — printing this dict list usually
   tells you exactly which pipeline step behaved unexpectedly, since
   every step is recorded with a label and content.
3. **Isolate the failing dependency** — since `LLMInterface`/`AgentMemory`
   are fakes in tests, a failure is almost always in `BaseAgent.run()`'s
   logic itself, not in "the LLM" (there is no real LLM in these tests).
4. **Add a temporary print in `_record_reasoning`** if the log order
   seems wrong — this is the single choke point all trace entries pass
   through.
5. **Check for state leakage between tests** — if two tests use the same
   `EchoAgent` instance instead of creating a fresh one, reasoning logs
   from a previous `run()` may bleed into an unrelated assertion. Always
   instantiate a new agent per test.

## 8. Common Errors and Solutions

| Error | Likely cause | Solution |
|---|---|---|
| `TypeError: Can't instantiate abstract class ... with abstract methods _build_prompt, _parse_output` | Your test subclass didn't implement both abstract methods | Implement both `_build_prompt` and `_parse_output` in your test subclass |
| `AttributeError: 'FakeMemory' object has no attribute 'get_context'` | Fake class doesn't match the `AgentMemory` Protocol shape | Ensure your fake has both `get_context(self)` and `update_context(self, task, result)` methods, spelled exactly as in `base_agent.py` |
| `AssertionError` on `reasoning_log` length | Reusing one agent instance across multiple `run()` calls without accounting for the reset | Confirm you're checking the log immediately after the specific `run()` call under test |
| Test hangs / never completes | A fake `LLMInterface.generate()` accidentally makes a real network call instead of returning a canned string | Double-check your fake doesn't import/call a real SDK — it should be pure Python, no I/O |
| `result.success == True` when you expected `False` | Exception was swallowed somewhere *before* reaching `run()`'s `try/except` (e.g. inside your fake's constructor) | Make sure the exception is raised inside `generate()` / `_parse_output()` / `get_context()` / `update_context()` — i.e. inside the pipeline `run()` actually wraps |
| `ModuleNotFoundError: No module named 'agents'` | Running pytest from the wrong directory, or missing `__init__.py` | Run pytest from the project root (`multiagent_project/`), and confirm `agents/__init__.py` exists |

## 9. Status

✅ Test strategy defined — `test_base_agent.py` (10 test cases above) to
be written and executed before Module 1.2 begins, per project rule:
"Do not skip testing."