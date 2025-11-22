"""State handler infrastructure.

Provides base classes and utilities for state handling logic.
"""

from .base import DeviceContext, StateHandlerResult
from .content_handler import ContentHandler

__all__ = [
    'DeviceContext',
    'StateHandlerResult',
    'ContentHandler',
]
