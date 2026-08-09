# Module 2.3 — Research Agent — Design Document

## 1. Architecture
```
SupervisorAgent (M2.1, UNMODIFIED)
    -> registers agents directly, no adapter for worker agents
        -> ResearchAgent (NEW, extends BaseAgent from M1.1, UNMODIFIED)
            -> LLMInterface (M1.2, injected, UNMODIFIED)
            -> AgentMemory (M1.1 Protocol, injected, UNMODIFIED)
```
Unlike `PlannerAgent` (Module 2.2), which needed `PlannerTaskRouter`
to plug into Supervisor's `TaskRouter` extension point, `ResearchAgent`
is a plain executable step — it's registered with
`SupervisorAgent.register_agent()` exactly like any other worker agent
and produces output for the Supervisor's `outputs` dict. No adapter
class is needed for this module.

## 2. Responsibilities
| Component | Owns | Does NOT own |
|---|---|---|
| `ResearchAgent` | building the research prompt, parsing/validating LLM output into a `ResearchReport`, deduplication, conflict preservation | execution scheduling, retries, routing, memory infrastructure |
| `research_models.py` | `ResearchRequest`/`Finding`/`ResearchReport` data shape, `ResearchValidationError` | anything execution- or routing-related (that's Supervisor's/Planner's) |
| `prompt_templates.py` | prompt wording only | parsing/validation logic |
| `SupervisorAgent` (unchanged) | execution, retry, trace, memory persistence, final report | knowing anything about `ResearchReport`'s internal shape — it only sees `AgentResult.output` as opaque `Any`, same as for every agent |

## 3. Dependency Injection
`ResearchAgent(name, role_description, llm_interface, memory)` — the
identical constructor shape as `BaseAgent`, `PlannerAgent`, and every
mock agent in the existing test suites. No internal construction of
an LLM client or memory store; both are passed in by the caller.

## 4. LLM Integration
`ResearchAgent` inherits `run()` from `BaseAgent` completely
unmodified — it implements only the two abstract seams
(`_build_prompt`, `_parse_output`) `BaseAgent` already defines. This
gives Research the exact same reasoning-log capture and fault
isolation as every other agent in the project, with zero duplicated
logic. `_build_prompt()` delegates prompt text to
`prompt_templates.build_research_prompt()`, keeping wording separable
from validation.

## 5. Source/Retrieval Abstraction
**No retrieval capability exists in this repository** (confirmed
during Step 1 inspection — no web/search/API client anywhere). Rather
than inventing a fake implementation, `ResearchRequest.context_notes`
is the sole channel for supplying reference information today; the
LLM is explicitly instructed (in `prompt_templates.py`) never to
fabricate a source beyond what it was given.

**How retrieval would be added later, without breaking this module:**
A future `agents/research/retrieval.py` could define a small
`Protocol`:
```python
class RetrievalSource(Protocol):
    def search(self, query: str) -> list[dict]: ...
```
`ResearchAgent` would accept an optional `retrieval_source:
RetrievalSource | None = None` constructor parameter (default `None`,
preserving today's behavior exactly). When provided,
`_build_prompt()` would call it to fetch reference material and fold
the results into the prompt in place of (or alongside)
`context_notes`. This is additive — no existing method signature or
test would need to change, matching the extensibility pattern already
established for `TaskRouter`/`ExecutionStrategy` in Module 2.1's
DESIGN.md.

## 6. Models
- `ResearchRequest(objective, context_notes="")` — input only.
- `Finding(finding_id, statement, confidence, supporting_evidence="",
  conflicting_evidence="", source="")` — one atomic research result.
- `ResearchReport(objective, findings, summary, rationale)` — final
  output, mirrors `AgentResult.output`'s role for this agent type.
- `ResearchValidationError(Exception)` — the single exception type
  raised for any structural problem with LLM output; caught
  automatically inside `BaseAgent.run()`'s existing `try/except`,
  never a special case.

No model here duplicates anything from Supervisor (`AgentExecutionRecord`,
`ExecutionTrace`, etc.) or Planner (`PlanStep`, `PlannerExecutionPlan`).

## 7. Explainability
Two levels, matching the project's "concise rationale, never hidden
chain-of-thought" requirement:
- **Per-finding**: `Finding.supporting_evidence` and
  `Finding.conflicting_evidence` — both concise, both explicit (an
  empty string means "none provided," never a silent omission).
- **Overall**: `ResearchReport.rationale` explains how `summary`
  follows from `findings`, distinct from the summary itself.

The prompt (`prompt_templates.py`) explicitly forbids returning
internal deliberation outside these named fields, and the parser only
ever extracts those named fields — there is no code path that could
surface anything else.

## 8. Error Handling
| Failure | Where caught | Outcome |
|---|---|---|
| Empty objective | `ResearchAgent._build_prompt()`, raised as `ResearchValidationError` | `AgentResult(success=False)` |
| LLM call itself raises | `BaseAgent.run()` (M1.1, unmodified) | `AgentResult(success=False)` |
| Malformed JSON / missing `findings` key / empty list | `_parse_output()`, raised as `ResearchValidationError` | `AgentResult(success=False)` |
| Missing/invalid `finding_id` or `statement` | `_parse_output()` | `AgentResult(success=False)` |
| Duplicate `finding_id` | `_parse_output()` | `AgentResult(success=False)` — a genuine data-integrity problem, not silently fixed |
| Duplicate `statement` (same fact, different id) | `_parse_output()` | Silently merged (later duplicate skipped) — a defensive backstop, not an error, since the LLM was already asked not to repeat findings |
| `confidence` out of `[0.0, 1.0]` or non-numeric | `_parse_output()` | `AgentResult(success=False)` |
| All findings turn out to be duplicates | `_parse_output()` | `AgentResult(success=False)` — never returns an empty-but-"successful" report |

At no point does an exception escape to whatever called
`ResearchAgent.run()` — matching Module 1.1's, 2.1's, and 2.2's
established fault-isolation philosophy.

## 9. Why Duplicate-Statement Merging Is Silent But Duplicate-ID Is Not
A repeated `finding_id` signals the LLM's JSON structure itself is
inconsistent (a genuine data-integrity problem worth surfacing as a
failure). A repeated *statement* under two different ids is far more
likely — the LLM restating the same fact twice, which the prompt
explicitly discourages but cannot fully prevent. Treating the second
as a silent merge (rather than a hard failure) keeps the agent
resilient to a common, low-severity LLM slip without hiding a genuine
structural problem elsewhere.

## 10. Alternative Designs Considered
| Alternative | Why rejected |
|---|---|
| Give `ResearchAgent` a fake/simulated web search | Explicitly forbidden by the module spec; would create a false impression of live retrieval capability that doesn't exist |
| Fail the whole report on any duplicate statement | Too brittle — the LLM restating a fact in different words is common and recoverable; failing the entire report for it would make the agent unusable in practice |
| Put deduplication logic in a separate method (`filter_duplicate_information()`) | Considered per the spec's optional method list, but the dedup logic is a single normalize-and-check-in-a-set operation inline in the parsing loop — a separate method would add an indirection without adding clarity, so it stays inline (keeping the design simple, per the spec's own instruction) |
| Reuse `Finding` for both input and output | `ResearchRequest` (input) and `Finding`/`ResearchReport` (output) have genuinely different shapes and purposes; conflating them would blur what the caller supplies vs. what the agent produces |

## 11. Limitations
- No live web/search retrieval (see Section 5) — findings are only as
  good as the `context_notes` supplied or the LLM's own training data.
- Confidence scores are self-reported by the LLM, not independently
  verified against any ground truth.
- Duplicate-statement detection is exact-match after normalization
  (lowercase, whitespace-collapsed) — semantically identical findings
  phrased very differently would not be caught.

## 12. Future Improvements
- Add the `RetrievalSource` protocol described in Section 5 once a
  real retrieval capability is available.
- Add semantic (embedding-based) duplicate detection instead of
  normalized-string matching, once a suitable capability exists in
  the project.
- Cache `ResearchReport`s per objective via `MemoryManager` to avoid
  redundant LLM calls for repeated research objectives.