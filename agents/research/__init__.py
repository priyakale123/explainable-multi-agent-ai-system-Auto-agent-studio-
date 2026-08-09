"""
Research Layer

LLM-driven research: analyzes a research objective and produces a
structured, deduplicated ResearchReport with confidence, evidence,
and conflict information, via ResearchAgent. Registered directly
with SupervisorAgent (Module 2.1) as an ordinary worker agent -- no
adapter needed, unlike Planner (Module 2.2), since ResearchAgent
doesn't plug into Supervisor's TaskRouter extension point.
"""

from .research_agent import ResearchAgent
from .research_models import (
    Finding,
    ResearchReport,
    ResearchRequest,
    ResearchValidationError,
)

__all__ = [
    "ResearchAgent",
    "ResearchRequest",
    "Finding",
    "ResearchReport",
    "ResearchValidationError",
]