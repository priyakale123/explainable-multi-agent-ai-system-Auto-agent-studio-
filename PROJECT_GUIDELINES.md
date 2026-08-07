# AutoAgent Studio - Project Guidelines

## Project Vision

AutoAgent Studio is an industry-level Explainable Multi-Agent AI Platform.

The project must be modular, extensible, production-ready, and follow software engineering best practices.

---

## Completed Modules (LOCKED)

Module 1.1 - Base Agent
Status: Completed

Module 1.2 - LLM Interface
Status: Completed

Module 1.3 - Memory Layer
Status: Completed

These modules are LOCKED.

Never modify existing public APIs.

Never rename classes.

Never change folder structure.

Only extend using new modules.

---

## Technology Stack

Python 3.11

Django (UI)

SQLite (Current)

FAISS (Future)

Anthropic Claude

OpenAI GPT

Pytest

Git

GitHub

---

## Architecture

User

↓

Django Dashboard

↓

Supervisor

↓

Planner

↓

Research

↓

Coding

↓

Testing

↓

Reviewer

↓

Documentation

↓

Report

↓

LLM Interface

↓

Claude / GPT

↓

SQLite + FAISS (Future)

---

## Coding Standards

Use SOLID Principles.

Use Dependency Injection.

Use Abstract Base Classes.

Use Type Hints.

Use Dataclasses.

Write comprehensive docstrings.

Never hardcode providers.

Always write pytest tests.

Always write README.md.

Always write DESIGN.md.

Always write TESTING.md.

---

## Git Workflow

pytest

↓

git add .

↓

git commit

↓

git push

---

## Future Features

Decision Auditor Agent

AI Judge Agent

Agent Discussion

Why Not Analysis

Confidence Score

Workflow Optimizer

Knowledge Graph

Security Agent

Self-Healing Agent

Observability Dashboard

These are future modules.

Do NOT implement them unless explicitly requested.

Design the architecture so they can be added later without breaking existing code.