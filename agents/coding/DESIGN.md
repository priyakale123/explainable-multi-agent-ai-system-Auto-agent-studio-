Unlike `PlannerAgent` (Module 2.2), which needed `PlannerTaskRouter`
to plug into Supervisor's `TaskRouter` extension point, `CodingAgent`
is a plain executable step — it's registered with
`SupervisorAgent.register_agent()` exactly like `ResearchAgent`
(Module 2.3) and produces output for the Supervisor's `outputs` dict.
No adapter class is needed for this module.

## 2. Responsibilities
| Component | Owns | Does NOT own |
|---|---|---|
| `CodingAgent` | building the coding prompt, parsing/validating LLM output into a `CodeGenerationResult`, per-file validation, dependency/assumption tracking | execution scheduling, retries, routing, memory infrastructure, code execution, testing, filesystem writes |
| `coding_models.py` | `CodingRequest`/`CodeFile`/`CodeGenerationResult` data shape, `CodingValidationError`, `ALLOWED_LANGUAGES` | anything execution- or routing-related (that's Supervisor's/Planner's) |
| `prompt_templates.py` | prompt wording only | parsing/validation logic |
| `SupervisorAgent` (unchanged) | execution, retry, trace, memory persistence, final report | knowing anything about `CodeGenerationResult`'s internal shape — it only sees `AgentResult.output` as opaque `Any`, same as for every agent |

## 3. Dependency Injection
`CodingAgent(name, role_description, llm_interface, memory)` — the
identical constructor shape as `BaseAgent`, `PlannerAgent`,
`ResearchAgent`, and every mock agent in the existing test suites. No
internal construction of an LLM client, memory store, or execution
sandbox; all are passed in by the caller (or, for execution, simply
never exist inside this module at all).

## 4. LLM Integration
`CodingAgent` inherits `run()` from `BaseAgent` completely
unmodified — it implements only the two abstract seams
(`_build_prompt`, `_parse_output`) `BaseAgent` already defines. This
gives Coding the exact same reasoning-log capture and fault isolation
as every other agent in the project, with zero duplicated logic.
`_build_prompt()` delegates prompt text to
`prompt_templates.build_coding_prompt()`, keeping wording separable
from validation.

## 5. Execution/Filesystem Boundary
**`CodingAgent` performs no execution and touches no filesystem.**
This is enforced structurally, not just documented: the module has no
`subprocess`, `os.system`, `exec`/`eval`, `shutil`, or `open()` call
anywhere in its source (verified by a dedicated test scanning the
module's own source). `CodeFile.filename` is a *proposed* relative
path only — `CodingAgent` never writes it to disk. Running, testing,
or persisting generated code to a real filesystem location is
explicitly deferred to future modules (a Testing Agent, a Reviewer
Agent, or an eventual `WorkflowExecutor`), none of which this module
imports or depends on.

**How execution would be added later, without breaking this module:**
A future `agents/coding/execution.py` (or a dedicated Testing Agent,
per `PROJECT_GUIDELINES.md`'s pipeline) could define a small
`Protocol`:
```python
class CodeExecutor(Protocol):
    def execute(self, file: CodeFile) -> ExecutionOutcome: ...
```
This would live in a *separate* module/agent entirely — `CodingAgent`
itself would never accept or call it, preserving the hard separation
between "planning and generating code" (this module) and "running
code" (a future, different module). This mirrors how `ResearchAgent`
(Module 2.3) documents a future `RetrievalSource` Protocol as an
addition to *itself*, whereas here the boundary is deliberately kept
between two different agents, not extended within one — because
execution is a materially different trust/risk category than
generation.

## 6. Context Limitation
**No filesystem-access or project-introspection abstraction exists in
this repository** (confirmed during Step 1 inspection — no file-read
capability, no project-indexing/AST-scanning module anywhere).
`CodingRequest.context_notes` is the sole channel for supplying
project context today; the LLM is explicitly instructed (in
`prompt_templates.py`) never to fabricate project files, conventions,
or requirements it was not given.

## 7. Models
- `CodingRequest(objective, context_notes="")` — input only.
- `CodeFile(file_id, filename, language, content, purpose="")` — one
  atomic generated file.
- `CodeGenerationResult(objective, files, dependencies, assumptions,
  explanation, rationale)` — final output, mirrors `AgentResult.output`'s
  role for this agent type.
- `CodingValidationError(Exception)` — the single exception type
  raised for any structural problem with LLM output; caught
  automatically inside `BaseAgent.run()`'s existing `try/except`,
  never a special case.
- `ALLOWED_LANGUAGES` — a small, explicit, defensively-checked set of
  recognized languages for `CodeFile.language`, kept in
  `coding_models.py` (not hardcoded in the parser) so
  `prompt_templates.py` can reference the same source of truth when
  listing allowed languages to the LLM.

No model here duplicates anything from Supervisor
(`AgentExecutionRecord`, `ExecutionTrace`, etc.), Planner (`PlanStep`,
`PlannerExecutionPlan`), or Research (`Finding`, `ResearchReport`).

## 8. Explainability
Two levels, matching the project's "concise rationale, never hidden
chain-of-thought" requirement:
- **Per-file**: `CodeFile.purpose` — one concise sentence stating why
  this file exists within the implementation.
- **Overall**: `CodeGenerationResult.explanation` describes the
  implementation as a whole; `CodeGenerationResult.rationale` explains
  how `explanation` and `files` follow from the objective and context
  — distinct from the explanation itself, mirroring
  `ResearchReport.rationale`'s role relative to `summary`.

`CodeGenerationResult.assumptions` is a third, explicit channel:
anything the LLM had to assume due to missing/ambiguous context is
named directly rather than silently baked into the generated code
with no trace. The prompt explicitly forbids returning internal
deliberation outside the named fields, and the parser only ever
extracts those named fields — there is no code path that could
surface anything else.

## 9. Error Handling
| Failure | Where caught | Outcome |
|---|---|---|
| Empty objective | `CodingAgent._build_prompt()`, raised as `CodingValidationError` | `AgentResult(success=False)` |
| LLM call itself raises | `BaseAgent.run()` (M1.1, unmodified) | `AgentResult(success=False)` |
| Malformed JSON / missing `files` key / empty list | `_parse_output()`, raised as `CodingValidationError` | `AgentResult(success=False)` |
| Missing/invalid `file_id`, `filename`, or `content` | `_parse_output()` | `AgentResult(success=False)` |
| Duplicate `file_id` | `_parse_output()` | `AgentResult(success=False)` — a genuine data-integrity problem, not silently fixed |
| Unrecognized `language` (not in `ALLOWED_LANGUAGES`) | `_parse_output()` | `AgentResult(success=False)` |
| `dependencies` or `assumptions` not a list of strings | `_parse_output()` | `AgentResult(success=False)` |
| Memory backend raises on `update_context()` | `BaseAgent.run()` (M1.1, unmodified) | `AgentResult(success=False)` |

At no point does an exception escape to whatever called
`CodingAgent.run()` — matching Module 1.1's, 2.1's, 2.2's, and 2.3's
established fault-isolation philosophy.

## 10. Why Language Is a Closed Set, Not a Free String
`ResearchAgent`'s `confidence` field is numeric and range-checked;
`CodingAgent`'s `language` field is the analogous defensive check for
this module — an open string would let a malformed or hallucinated
value (e.g. a typo, or a language the rest of the pipeline has no
tooling for) pass through silently. Keeping `ALLOWED_LANGUAGES` in
`coding_models.py` (not `coding_agent.py`) lets `prompt_templates.py`
import the same set to tell the LLM exactly what's acceptable, so the
prompt and the validator can never drift apart.

## 11. Alternative Designs Considered
| Alternative | Why rejected |
|---|---|
| Give `CodingAgent` a code-execution/sandbox capability for self-verification | Explicitly forbidden by the module spec; would blur the boundary between "generates code" and "runs code," which the project's pipeline (Coding → Testing → Reviewer) depends on staying separate |
| Let `CodeFile.language` be an open string | Would let malformed/hallucinated language values pass through unchecked, unlike every other validated field in this module and its siblings |
| Fold `dependencies` and `assumptions` into `explanation` as free text | Loses structure a future Reviewer/Testing Agent would need to parse programmatically (e.g. to check declared dependencies against what's actually imported in `content`) |
| Split implementation-spec and code-generation into two separate agent classes | Rejected per the module spec, which asks for one `CodingAgent` responsible for both planning and generation as a single LLM-driven step, consistent with how `PlannerAgent` and `ResearchAgent` are each one class handling their full responsibility, not split further |

## 12. Limitations
- No live filesystem/project visibility (see Section 6) — generated
  code is only as good as the `context_notes` supplied.
- Generated code is never executed, so correctness is not verified by
  this module at all — by design, that's deferred entirely to a
  future Testing Agent.
- `ALLOWED_LANGUAGES` is a fixed, hand-maintained set — adding a new
  language requires a code change here, not a prompt-only change.

## 13. Future Improvements
- Add a `CodeExecutor` Protocol-based Testing Agent (Section 5) once
  execution is in scope for the project.
- Add per-file syntax validation (e.g. `ast.parse()` for Python) as an
  additional defensive check in `_parse_output()`, without executing
  anything — this would still respect the execution boundary in
  Section 5 since parsing for syntax is not running code.
- Cache `CodeGenerationResult`s per objective via `MemoryManager` to
  avoid redundant LLM calls for repeated coding objectives.