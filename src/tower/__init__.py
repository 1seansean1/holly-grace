"""Control Tower: durable workflow execution with HITL approval gates.

Provides:
- Durable runs backed by LangGraph PostgresSaver checkpointing
- Structured HITL tickets (approval interrupts) with context packs
- Exactly-once side effects via two-phase prepare/commit
- Run lifecycle management (start, interrupt, resume, complete)
"""

from __future__ import annotations
