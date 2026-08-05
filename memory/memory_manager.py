from __future__ import annotations

from typing import Any

from .conversation_memory import ConversationMemory
from .base_memory import BaseMemory, MemoryEntry, MemoryStatistics


class MemoryManager:
    """
    Central manager for all memory stores.

    Responsible for:
    - Registering memory implementations
    - Creating default memory stores
    - Routing requests to the correct memory
    """

    def __init__(self):
        self.stores: dict[str, BaseMemory] = {}
        self.default_factory = ConversationMemory

    # ---------------------------------------------------------
    # Memory Registration
    # ---------------------------------------------------------

    def register_memory(
        self,
        name: str,
        memory: BaseMemory,
    ) -> None:
        self.stores[name] = memory

    def get_memory(self, name: str = "default") -> BaseMemory:
        if name not in self.stores:
            self.stores[name] = self.default_factory()

        return self.stores[name]

    # ---------------------------------------------------------
    # Store Operations
    # ---------------------------------------------------------

    def store(
        self,
        name: str,
        task: Any,
        result: Any,
        metadata: dict | None = None,
    ) -> MemoryEntry:

        return self.get_memory(name).store(
            task,
            result,
            metadata,
        )

    def retrieve(
        self,
        name: str,
        query: str | None = None,
        limit: int | None = None,
    ):

        return self.get_memory(name).retrieve(
            query=query,
            limit=limit,
        )

    def clear(self, name: str) -> None:
        self.get_memory(name).clear()

    def get_recent(
        self,
        name: str,
        n: int = 5,
    ):

        return self.get_memory(name).get_recent(n)

    def get_statistics(
        self,
        name: str,
    ) -> MemoryStatistics:

        return self.get_memory(name).get_statistics()

    # ---------------------------------------------------------
    # Utility
    # ---------------------------------------------------------

    def clear_all(self) -> None:
        for memory in self.stores.values():
            memory.clear()

    def list_stores(self) -> list[str]:
        return list(self.stores.keys())