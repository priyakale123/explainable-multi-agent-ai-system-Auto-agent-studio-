from __future__ import annotations

from typing import Any

from .base_memory import BaseMemory, MemoryEntry, MemoryStatistics


class ConversationMemory(BaseMemory):
    """
    In-memory conversation storage.

    Stores task/result pairs in RAM.
    Can later be replaced by FAISSMemory without changing agents.
    """

    def __init__(self, max_entries: int | None = None):
        self.entries: list[MemoryEntry] = []
        self.max_entries = max_entries

    def store(
        self,
        task: Any,
        result: Any,
        metadata: dict | None = None,
    ) -> MemoryEntry:

        entry = MemoryEntry.create(
            task=task,
            result=result,
            metadata=metadata or {},
        )

        self.entries.append(entry)

        # FIFO eviction
        if self.max_entries is not None:
            while len(self.entries) > self.max_entries:
                self.entries.pop(0)

        return entry

    def retrieve(
        self,
        query: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryEntry]:

        if query is None:
            results = self.entries.copy()
        else:
            query = query.lower()

            results = [
                entry
                for entry in self.entries
                if query in str(entry.task).lower()
                or query in str(entry.result).lower()
            ]

        if limit is not None:
            results = results[-limit:]

        return results

    def clear(self) -> None:
        self.entries.clear()

    def get_recent(self, n: int = 5) -> list[MemoryEntry]:
        return list(reversed(self.entries[-n:]))

    def get_statistics(self) -> MemoryStatistics:

        if not self.entries:
            return MemoryStatistics(
                memory_type="ConversationMemory",
                total_entries=0,
                oldest_timestamp=None,
                newest_timestamp=None,
            )

        return MemoryStatistics(
            memory_type="ConversationMemory",
            total_entries=len(self.entries),
            oldest_timestamp=self.entries[0].timestamp,
            newest_timestamp=self.entries[-1].timestamp,
        )

    # ------------------------------------------------------------------
    # AgentMemory compatibility
    # ------------------------------------------------------------------

    def get_context(self) -> dict:

        history = [
            {
                "task": entry.task,
                "result": entry.result,
            }
            for entry in self.entries[-5:]
        ]

        return {"history": history}

    def update_context(
        self,
        task: Any,
        result: Any,
    ) -> None:

        self.store(task, result)