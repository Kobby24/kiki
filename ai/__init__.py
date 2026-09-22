"""
Sikapa AI/ML Communication Engine.

This package provides the conversational AI subsystem for Sikapa,
including ASR, NLU, and code-mixed audio synthesis services.
"""

from ai.ai_router import ai_router  # noqa: F401 – re-exported for app mounting

__all__ = ["ai_router"]
