import time

from memory import (
    ConversationMemory,
    MemoryManager,
)


def test_store_entry():
    memory = ConversationMemory()

    entry = memory.store(
        task="Hello",
        result="World",
    )

    assert entry.task == "Hello"
    assert entry.result == "World"
    assert len(memory.entries) == 1


def test_retrieve_all():
    memory = ConversationMemory()

    memory.store("A", "1")
    memory.store("B", "2")

    results = memory.retrieve()

    assert len(results) == 2


def test_retrieve_query():
    memory = ConversationMemory()

    memory.store("Python", "Programming")
    memory.store("Java", "Language")

    results = memory.retrieve("python")

    assert len(results) == 1
    assert results[0].task == "Python"


def test_clear():
    memory = ConversationMemory()

    memory.store("A", "B")
    memory.clear()

    assert len(memory.entries) == 0


def test_recent():
    memory = ConversationMemory()

    memory.store("1", "one")
    memory.store("2", "two")
    memory.store("3", "three")

    recent = memory.get_recent(2)

    assert len(recent) == 2
    assert recent[0].task == "3"


def test_statistics():
    memory = ConversationMemory()

    memory.store("A", "1")
    time.sleep(0.01)
    memory.store("B", "2")

    stats = memory.get_statistics()

    assert stats.total_entries == 2
    assert stats.oldest_timestamp is not None
    assert stats.newest_timestamp is not None


def test_empty_statistics():
    memory = ConversationMemory()

    stats = memory.get_statistics()

    assert stats.total_entries == 0


def test_fifo_eviction():
    memory = ConversationMemory(max_entries=2)

    memory.store("1", "A")
    memory.store("2", "B")
    memory.store("3", "C")

    assert len(memory.entries) == 2
    assert memory.entries[0].task == "2"


def test_context():
    memory = ConversationMemory()

    memory.store("Task", "Result")

    context = memory.get_context()

    assert "history" in context
    assert len(context["history"]) == 1


def test_update_context():
    memory = ConversationMemory()

    memory.update_context(
        "Task",
        "Done",
    )

    assert len(memory.entries) == 1


def test_manager_store():
    manager = MemoryManager()

    manager.store(
        "default",
        "Hello",
        "World",
    )

    results = manager.retrieve("default")

    assert len(results) == 1


def test_manager_clear():
    manager = MemoryManager()

    manager.store(
        "default",
        "A",
        "B",
    )

    manager.clear("default")

    assert manager.retrieve("default") == []


def test_manager_recent():
    manager = MemoryManager()

    manager.store("default", "1", "A")
    manager.store("default", "2", "B")

    recent = manager.get_recent(
        "default",
        1,
    )

    assert recent[0].task == "2"


def test_manager_statistics():
    manager = MemoryManager()

    manager.store(
        "default",
        "A",
        "B",
    )

    stats = manager.get_statistics("default")

    assert stats.total_entries == 1


def test_list_stores():
    manager = MemoryManager()

    manager.get_memory("chat")
    manager.get_memory("planner")

    stores = manager.list_stores()

    assert "chat" in stores
    assert "planner" in stores


def test_clear_all():
    manager = MemoryManager()

    manager.store("chat", "A", "1")
    manager.store("planner", "B", "2")

    manager.clear_all()

    assert manager.retrieve("chat") == []
    assert manager.retrieve("planner") == []


def test_limit():
    memory = ConversationMemory()

    for i in range(5):
        memory.store(str(i), str(i))

    results = memory.retrieve(limit=2)

    assert len(results) == 2
    assert results[0].task == "3"


def test_case_insensitive_search():
    memory = ConversationMemory()

    memory.store("Python", "AI")

    results = memory.retrieve("PYTHON")

    assert len(results) == 1