"""Validate that a path will fit inside the filesystem's length limit.

The problem this module solves is narrow and concrete: many filesystems and
APIs reject paths that are too long, but they reject them at different
lengths and measure length in different ways.  A path that is fine on Linux
ext4 (4096 bytes) is not fine on Windows (260 UTF-16 code units by default)
and a path that is fine on Windows may still be rejected by a tool that
counts bytes rather than characters.

The design decision made here is deliberate: length is measured in *bytes*
of the UTF-8 encoding of the path, not in characters and not in code units.
Bytes are what the kernel and most system calls actually see, and UTF-8 is
the encoding used on Linux and macOS.  Windows is the awkward case, so
``Platform.WINDOWS`` is treated as a special limit expressed in UTF-16 code
units and the caller is expected to pass ``Platform.WINDOWS`` when they
care about that behaviour.  This keeps one consistent rule (bytes) for the
common case and one explicit exception for the platform that genuinely
differs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from os import PathLike
from typing import Union


class Platform(Enum):
    """Filesystem families with distinct path length semantics."""

    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"


@dataclass(frozen=True)
class PathLimit:
    """A maximum path length and the unit used to measure it.

    ``unit`` is ``"bytes"`` for UTF-8 byte counting and ``"utf-16-code-units"``
    for the Windows convention.  Keeping the unit next to the number makes it
    impossible to compare a Windows limit against a byte count by accident.
    """

    maximum: int
    unit: str

    def __post_init__(self) -> None:
        if self.maximum <= 0:
            raise ValueError("maximum must be positive")
        if self.unit not in ("bytes", "utf-16-code-units"):
            raise ValueError("unit must be 'bytes' or 'utf-16-code-units'")


# Conservative, well-known defaults.  Linux PATH_MAX is 4096 bytes including
# the terminating NUL, so the usable path is 4095 bytes.  macOS PATH_MAX is
# also 1024 bytes for the array form; 1024 is used here because that is the
# limit that bites in practice.  Windows MAX_PATH is 260 UTF-16 code units
# including the terminating NUL, so 259 usable units.
DEFAULT_LIMITS: dict[Platform, PathLimit] = {
    Platform.LINUX: PathLimit(maximum=4095, unit="bytes"),
    Platform.MACOS: PathLimit(maximum=1024, unit="bytes"),
    Platform.WINDOWS: PathLimit(maximum=259, unit="utf-16-code-units"),
}


class PathLengthError(ValueError):
    """Base class for all path length failures raised by this package."""


class PathTooLongError(PathLengthError):
    """Raised when a path exceeds the configured maximum length."""

    def __init__(self, path: str, limit: PathLimit, actual: int) -> None:
        self.path = path
        self.limit = limit
        self.actual = actual
        super().__init__(
            f"path is {actual} {limit.unit} long, "
            f"which exceeds the {limit.maximum} {limit.unit} limit"
        )


PathInput = Union[str, bytes, PathLike]


def _coerce_path(path: PathInput) -> str:
    """Return the path as a ``str``.

    ``os.PathLike`` objects are converted with ``os.fspath``.  ``bytes``
    paths are decoded with ``os.fsdecode`` so that the filesystem encoding
    (surrogateescape on POSIX) is respected.  Anything else is rejected
    rather than silently stringified, because ``str(None)`` would produce a
    path that obviously does not exist.
    """
    import os

    if isinstance(path, str):
        return path
    if isinstance(path, (bytes, bytearray)):
        return os.fsdecode(bytes(path))
    if hasattr(path, "__fspath__"):
        return os.fsdecode(path.__fspath__())
    raise TypeError(f"path must be str, bytes or os.PathLike, not {type(path).__name__}")


def _measure(path: str, unit: str) -> int:
    """Measure ``path`` in the requested unit.

    UTF-8 byte length is computed with ``surrogatepass`` because POSIX
    ``os.fsdecode`` can produce lone surrogates for undecodable bytes; those
    still occupy bytes when they go back to the kernel and must be counted.
    UTF-16 code units are counted by encoding to UTF-16 little-endian and
    dividing by two, which is exactly how Windows counts them.
    """
    if unit == "bytes":
        return len(path.encode("utf-8", "surrogatepass"))
    if unit == "utf-16-code-units":
        return len(path.encode("utf-16-le", "surrogatepass")) // 2
    raise ValueError(f"unknown unit: {unit!r}")


def limit_for(platform: Platform) -> PathLimit:
    """Return the default :class:`PathLimit` for ``platform``."""
    try:
        return DEFAULT_LIMITS[platform]
    except KeyError as exc:
        raise ValueError(f"unknown platform: {platform!r}") from exc


def validate_path(
    path: PathInput,
    platform: Platform = Platform.LINUX,
    limit: PathLimit | None = None,
) -> int:
    """Validate ``path`` against ``limit`` (or the platform default).

    Returns the measured length in the limit's unit on success and raises
    :class:`PathTooLongError` on failure.  Returning the length is useful
    because callers frequently want to log it, and recomputing it would be
    wasteful.
    """
    if limit is None:
        limit = limit_for(platform)
    text = _coerce_path(path)
    if text == "":
        raise PathLengthError("path must not be empty")
    actual = _measure(text, limit.unit)
    if actual > limit.maximum:
        raise PathTooLongError(text, limit, actual)
    return actual


def is_path_valid(
    path: PathInput,
    platform: Platform = Platform.LINUX,
    limit: PathLimit | None = None,
) -> bool:
    """Return ``True`` when ``path`` fits, ``False`` when it does not.

    Empty paths and unencodable objects are treated as invalid rather than
    raising, so this is safe to call in a filter.  Use :func:`validate_path`
    when the reason for failure matters.
    """
    try:
        validate_path(path, platform=platform, limit=limit)
    except PathLengthError:
        return False
    except TypeError:
        return False
    return True
