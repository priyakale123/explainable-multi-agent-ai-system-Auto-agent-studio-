# Memory Module

## Overview

The Memory Module provides an abstraction layer for storing, retrieving,
and managing conversation history within the Explainable Multi-Agent AI
System.

This module is designed to be provider-independent and future-ready,
allowing advanced memory backends such as FAISS, SQLite, or Redis to be
integrated without changing agent logic.

---

## Features

- Store task-result pairs
- Retrieve previous conversations
- Search memory
- Get recent interactions
- Memory statistics
- Context generation
- FIFO memory eviction
- Memory manager for multiple stores
- Extensible architecture

---

## Components

### BaseMemory

Abstract interface defining the memory contract.

### ConversationMemory

Stores conversations in RAM.

### MemoryManager

Central controller responsible for managing multiple memory instances.

---

## Project Structure

memory/

├── __init__.py

├── base_memory.py

├── conversation_memory.py

├── memory_manager.py

├── README.md

├── DESIGN.md

└── TESTING.md

---

## Future Enhancements

- FAISS Vector Memory
- SQLite Memory
- Redis Memory
- Semantic Search
- Long-Term Memory

---

## Example

```python
from memory import MemoryManager

manager = MemoryManager()

manager.store(
    "default",
    "Write Login Page",
    "Completed"
)

history = manager.retrieve("default")
print(history)
```

---

## Dependencies

- Python 3.11+
- Dataclasses
- Typing
- UUID
- Time

---

## Author

Group project 

Final Year B.E. Computer Engineering

Explainable Multi-Agent AI System 