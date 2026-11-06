"""Public API for the path maximum length validator package.

Only the names below are considered stable. Everything else lives in
``core`` and is an implementation detail.
"""

from .core import (
    DEFAULT_LIMITS,
    PathLengthError,
    PathTooLongError,
    Platform,
    PathLimit,
    limit_for,
    validate_path,
    is_path_valid,
)

__all__ = [
    "DEFAULT_LIMITS",
    "PathLengthError",
    "PathTooLongError",
    "Platform",
    "PathLimit",
    "limit_for",
    "validate_path",
    "is_path_valid",
]
