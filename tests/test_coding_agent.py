"""
tests/test_coding_agent.py

Comprehensive unit tests for Module 2.4 (Coding Agent).

Mirrors the fake/mock patterns established in
tests/test_research_agent.py and tests/test_planner_agent.py
(ScriptedLLM/RaisingLLM, FakeMemory satisfying BaseAgent's Protocols
structurally). No real LLM calls, no real execution of generated
code, no filesystem writes anywhere.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from agents.base_agent import BaseAgent
from agents.coding.coding_agent import CodingAgent
from agents.coding.coding_models import (
    CodeFile,
    CodeGenerationResult,
    CodingRequest,
    CodingValidationError,
)


# ==========================================================
# Fakes
# ==========================================================

class ScriptedLLM:
    """Returns a fixed, scripted response regardless of prompt."""

    def __init__(self, response: str) -> None:
        self._response = response

    def generate(self, prompt: str) -> str:
        return self._response


class RaisingLLM:
    """Simulates an LLM call failure (e.g. network/API error)."""

    def generate(self, prompt: str) -> str:
        raise RuntimeError("simulated LLM API failure")


class FakeMemory:
    def get_context(self) -> dict:
        return {}

    def update_context(self, task: Any, result: Any) -> None:
        pass


class RaisingMemory:
    """Simulates a memory backend failure on update_context()."""

    def get_context(self) -> dict:
        return {}

    def update_context(self, task: Any, result: Any) -> None:
        raise RuntimeError("simulated memory backend failure")


def valid_files_json(file_ids: list[str] | None = None) -> str:
    file_ids = file_ids or ["f1"]
    files = [
        {
            "file_id": fid,
            "filename": f"module_{fid}.py",
            "language": "python",
            "content": f"# content for {fid}\ndef {fid}(): pass\n",
            "purpose": f"purpose of {fid}",
        }
        for fid in file_ids
    ]
    return json.dumps({
        "files": files,
        "dependencies": ["requests"],
        "assumptions": ["no external API contract was specified"],
        "explanation": "concise explanation of the implementation",
        "rationale": "concise rationale linking files to the objective",
    })


def make_agent(response: str, memory: Any = None) -> CodingAgent:
    return CodingAgent(
        "Coder", "generates code", ScriptedLLM(response), memory or FakeMemory()
    )


# ==========================================================
# 1. CodingAgent initialization
# ==========================================================

def test_coding_agent_initializes_like_any_base_agent():
    agent = make_agent(valid_files_json())
    assert agent.name == "Coder"
    assert agent.role_description == "generates code"
    assert isinstance(agent, BaseAgent)


# ==========================================================
# 2. Valid coding task -> structured coding result
# ==========================================================

def test_valid_coding_request_produces_structured_result():
    agent = make_agent(valid_files_json(["f1", "f2"]))
    result = agent.run(
        CodingRequest(
            objective="implement a stack data structure",
            context_notes="use Python 3.11, type hints required",
        )
    )

    assert result.success is True
    assert isinstance(result.output, CodeGenerationResult)
    assert result.output.objective == "implement a stack data structure"
    assert len(result.output.files) == 2
    assert result.output.dependencies == ["requests"]
    assert result.output.assumptions == ["no external API contract was specified"]
    assert result.output.explanation == "concise explanation of the implementation"
    assert result.output.rationale == "concise rationale linking files to the objective"


# ==========================================================
# 3. Valid JSON parsing -- individual file fields preserved
# ==========================================================

def test_valid_json_parsing_preserves_file_fields():
    agent = make_agent(valid_files_json(["f1"]))
    result = agent.run(CodingRequest(objective="task"))

    file = result.output.files[0]
    assert isinstance(file, CodeFile)
    assert file.file_id == "f1"
    assert file.filename == "module_f1.py"
    assert file.language == "python"
    assert "def f1" in file.content
    assert file.purpose == "purpose of f1"


# ==========================================================
# 4. LLM interaction (prompt actually reaches the injected LLM)
# ==========================================================

def test_coding_agent_sends_objective_and_context_to_llm():
    captured_prompts: list[str] = []

    class CapturingLLM:
        def generate(self, prompt: str) -> str:
            captured_prompts.append(prompt)
            return valid_files_json()

    agent = CodingAgent("Coder", "generates code", CapturingLLM(), FakeMemory())
    agent.run(CodingRequest(objective="build a binary search function", context_notes="input is sorted"))

    assert len(captured_prompts) == 1
    assert "build a binary search function" in captured_prompts[0]
    assert "input is sorted" in captured_prompts[0]


# ==========================================================
# 5. Malformed LLM response
# ==========================================================

def test_malformed_json_response_fails_gracefully():
    agent = make_agent("this is not JSON at all {{{")
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "valid JSON" in result.error


def test_missing_files_key_fails_gracefully():
    agent = make_agent(json.dumps({"explanation": "no files field"}))
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "files" in result.error.lower()


# ==========================================================
# 6. Wrong data types
# ==========================================================

def test_dependencies_wrong_type_fails_gracefully():
    bad_json = json.dumps({
        "files": [{
            "file_id": "f1", "filename": "a.py", "language": "python", "content": "pass",
        }],
        "dependencies": "requests",  # should be a list
        "assumptions": [],
        "explanation": "e", "rationale": "r",
    })
    agent = make_agent(bad_json)
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "dependencies" in result.error.lower()


def test_assumptions_wrong_type_fails_gracefully():
    bad_json = json.dumps({
        "files": [{
            "file_id": "f1", "filename": "a.py", "language": "python", "content": "pass",
        }],
        "dependencies": [],
        "assumptions": "none",  # should be a list
        "explanation": "e", "rationale": "r",
    })
    agent = make_agent(bad_json)
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "assumptions" in result.error.lower()


def test_unrecognized_language_fails_gracefully():
    bad_json = json.dumps({
        "files": [{
            "file_id": "f1", "filename": "a.cobol", "language": "cobol", "content": "pass",
        }],
        "dependencies": [], "assumptions": [], "explanation": "e", "rationale": "r",
    })
    agent = make_agent(bad_json)
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "language" in result.error.lower()


def test_empty_content_fails_gracefully():
    bad_json = json.dumps({
        "files": [{
            "file_id": "f1", "filename": "a.py", "language": "python", "content": "   ",
        }],
        "dependencies": [], "assumptions": [], "explanation": "e", "rationale": "r",
    })
    agent = make_agent(bad_json)
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "content" in result.error.lower()


# ==========================================================
# 7. Duplicate file identifiers
# ==========================================================

def test_duplicate_file_id_fails_gracefully():
    duplicate_json = json.dumps({
        "files": [
            {"file_id": "f1", "filename": "a.py", "language": "python", "content": "pass"},
            {"file_id": "f1", "filename": "b.py", "language": "python", "content": "pass"},
        ],
        "dependencies": [], "assumptions": [], "explanation": "e", "rationale": "r",
    })
    agent = make_agent(duplicate_json)
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "Duplicate file_id" in result.error


# ==========================================================
# 8. LLM failure
# ==========================================================

def test_llm_failure_is_caught_not_raised():
    agent = CodingAgent("Coder", "generates code", RaisingLLM(), FakeMemory())
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "simulated LLM API failure" in result.error


# ==========================================================
# 9. Memory failure
# ==========================================================

def test_memory_failure_is_caught_not_raised():
    agent = make_agent(valid_files_json(), memory=RaisingMemory())
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "simulated memory backend failure" in result.error


# ==========================================================
# 10. Empty coding request
# ==========================================================

def test_empty_objective_fails_gracefully():
    agent = make_agent(valid_files_json())
    result = agent.run(CodingRequest(objective=""))

    assert result.success is False
    assert "empty objective" in result.error.lower()


def test_empty_files_list_fails_gracefully():
    agent = make_agent(json.dumps({
        "files": [], "dependencies": [], "assumptions": [], "explanation": "e", "rationale": "r",
    }))
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is False
    assert "non-empty" in result.error.lower()


# ==========================================================
# 11. Dependency injection
# ==========================================================

def test_coding_agent_uses_injected_llm_and_memory():
    llm = ScriptedLLM(valid_files_json())
    memory = FakeMemory()
    agent = CodingAgent("Coder", "generates code", llm, memory)

    assert agent.llm_interface is llm
    assert agent.memory is memory


# ==========================================================
# 12. No direct provider dependency
# ==========================================================

def test_coding_agent_module_imports_no_llm_provider_sdk():
    import agents.coding.coding_agent as coding_module
    source = open(coding_module.__file__).read()

    assert "anthropic" not in source.lower()
    assert "openai" not in source.lower()
    assert "api_key" not in source.lower()


# ==========================================================
# 13. CodingAgent does not orchestrate/route other agents
# ==========================================================

def test_coding_agent_module_never_imports_supervisor_or_other_agents():
    import agents.coding.coding_agent as coding_module
    source = open(coding_module.__file__).read()

    import_lines = [
        line for line in source.splitlines()
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    ]
    assert not any("supervisor" in line.lower() for line in import_lines)
    assert not any("planner" in line.lower() for line in import_lines)
    assert not any("research_agent" in line.lower() for line in import_lines)
    assert "def run(" not in source


# ==========================================================
# 14. CodingAgent does not implement retry logic
# ==========================================================

def test_coding_agent_module_has_no_retry_logic():
    import agents.coding.coding_agent as coding_module
    source = open(coding_module.__file__).read()

    import_lines = [
        line for line in source.splitlines()
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    ]
    assert not any("retry" in line.lower() for line in import_lines)
    assert "RetryPolicy" not in source
    assert "while " not in source


# ==========================================================
# 15. CodingAgent does not execute, run, or shell out
# ==========================================================

def test_coding_agent_module_has_no_execution_logic():
    import agents.coding.coding_agent as coding_module
    source = open(coding_module.__file__).read()
    lowered = source.lower()

    for forbidden in ("subprocess", "os.system", "exec(", "eval(", "shutil", "open("):
        assert forbidden not in lowered, f"found forbidden execution/filesystem usage: {forbidden}"


# ==========================================================
# 16. Generated code is returned but never executed or claimed tested
# ==========================================================

def test_generated_code_is_returned_not_executed():
    agent = make_agent(valid_files_json(["f1"]))
    result = agent.run(CodingRequest(objective="task"))

    assert result.success is True
    file = result.output.files[0]
    assert not hasattr(result.output, "executed")
    assert not hasattr(result.output, "tested")
    assert not hasattr(file, "executed")
    assert not hasattr(file, "tested")
    assert "def f1" in file.content


# ==========================================================
# 17. CodingAgent integrates cleanly with existing architecture
# ==========================================================

def test_coding_agent_can_be_registered_with_real_supervisor():
    from agents.supervisor.supervisor_agent import SupervisorAgent
    from memory import MemoryManager

    memory_manager = MemoryManager()
    supervisor = SupervisorAgent(memory_manager=memory_manager)

    agent = make_agent(valid_files_json(["f1"]))
    supervisor.register_agent(agent)

    assert "Coder" in supervisor.list_agents()

    result = supervisor.run(
        CodingRequest(objective="implement a queue"), agent_order=["Coder"]
    )

    assert result.success is True
    assert isinstance(result.outputs["Coder"], CodeGenerationResult)