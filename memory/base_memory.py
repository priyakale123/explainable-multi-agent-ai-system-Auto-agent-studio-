"""
Base Memory Interface

Defines the abstract interface that all memory implementations
must follow.

Author: Priyanka Kale
Project: Explainable Multi-Agent AI System
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import time
import uuid


# ==========================================================
# Data Classes
# ==========================================================

@dataclass(slots=True)
class MemoryEntry:
    """
    Represents a single memory record.
    """

    entry_id: str
    task: Any
    result: Any
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        task: Any,
        result: Any,
        metadata: dict[str, Any] | None = None,
    ) -> "MemoryEntry":
        """
        Factory method to create a memory entry.
        """

        return cls(
            entry_id=str(uuid.uuid4()),
            task=task,
            result=result,
            timestamp=time.time(),
            metadata=metadata or {},
        )


@dataclass(slots=True)
class MemoryStatistics:
    """
    Statistics describing the current memory state.
    """

    memory_type: str
    total_entries: int
    oldest_timestamp: float | None
    newest_timestamp: float | None


# ==========================================================
# Abstract Base Memory
# ==========================================================

class BaseMemory(ABC):
    """
    Abstract base class for every memory implementation.

    Any future memory backend (RAM, SQLite, FAISS, Redis)
    must inherit from this class.
    """

    @abstractmethod
    def store(
        self,
        task: Any,
        result: Any,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """
        Store a new memory entry.
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve(
        self,
        query: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryEntry]:
        """
        Retrieve matching entries.
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """
        Remove all stored memories.
        """
        raise NotImplementedError

    @abstractmethod
    def get_recent(self, n: int = 5) -> list[MemoryEntry]:
        """
        Return the newest memory entries.
        """
        raise NotImplementedError

    @abstractmethod
    def get_statistics(self) -> MemoryStatistics:
        """
        Return memory statistics.
        """
        raise NotImplementedError

    # ------------------------------------------------------

    @abstractmethod
    def get_context(self) -> dict[str, Any]:
        """
        Return agent context for prompting.
        """
        raise NotImplementedError

    @abstractmethod
    def update_context(
        self,
        task: Any,
        result: Any,
    ) -> None:
        """
        Update memory context.
        """
        raise NotImplementedError