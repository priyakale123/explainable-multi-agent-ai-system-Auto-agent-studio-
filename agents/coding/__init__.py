"""
Coding Layer

LLM-driven code-generation planning and generation: analyzes a
coding objective and produces a structured CodeGenerationResult
(generated files, declared dependencies, explicit assumptions, and
a high-level explanation/rationale), via CodingAgent. Registered
directly with SupervisorAgent (Module 2.1) as an ordinary worker
agent -- no adapter needed, unlike Planner (Module 2.2), since
CodingAgent doesn't plug into Supervisor's TaskRouter extension
point (same as Research, Module 2.3).
"""

from .coding_agent import CodingAgent
from .coding_models import (
    ALLOWED_LANGUAGES,
    CodeFile,
    CodeGenerationResult,
    CodingRequest,
    CodingValidationError,
)

__all__ = [
    "CodingAgent",
    "CodingRequest",
    "CodeFile",
    "CodeGenerationResult",
    "CodingValidationError",
    "ALLOWED_LANGUAGES",
]