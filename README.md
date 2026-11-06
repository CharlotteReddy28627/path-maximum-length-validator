# path-maximum-length-validator

Validates that file paths do not exceed filesystem-specific maximum path
length limits before attempting operations.

## Usage

```python
from path_maximum_length_validator import (
    PathTooLongError,
    PathLimit,
    Platform,
    is_path_valid,
    validate_path,
)

# Uses the Linux default: 4095 UTF-8 bytes.
validate_path("/var/log/app.log")

# Returns True/False instead of raising.
assert is_path_valid("/var/log/app.log")

# Windows counts UTF-16 code units, not bytes.
try:
    validate_path("C:\\" + "x" * 300, platform=Platform.WINDOWS)
except PathTooLongError as exc:
    print(exc.actual, exc.limit.maximum, exc.limit.unit)

# Custom limits are honoured.
limit = PathLimit(maximum=10, unit="bytes")
try:
    validate_path("too-long-for-this", limit=limit)
except PathTooLongError:
    pass
```

## Why this exists

Filesystems disagree about what "too long" means. Linux and macOS count
UTF-8 bytes; Windows counts UTF-16 code units and applies a default limit of
260 including the terminating NUL. Code that builds paths from user input or
from deep directory trees tends to discover the limit only when an `open`
call fails halfway through a batch job.

The trade-off made here is to measure in bytes by default, because that is
what POSIX system calls actually see, and to make Windows an explicit
platform choice with its own unit. That means a Windows caller must pass
`Platform.WINDOWS` to get Windows semantics; passing nothing gets Linux
semantics. The alternative — guessing the platform from `sys.platform` —
was rejected because it makes tests non-deterministic on CI machines and
because callers who are inspecting a path for another machine need to say
which machine they mean.

## The awkward edge

A path containing characters outside the Basic Multilingual Plane (an emoji,
for example) counts as one character but two UTF-16 code units. Under
`Platform.WINDOWS` it therefore consumes two units of the limit, while under
`Platform.LINUX` it consumes four bytes. `validate_path` returns the measured
length in the limit's unit so you can log exactly which number was used.

Empty paths are rejected with `PathLengthError` rather than treated as
trivially valid, because an empty path is not a path.

## API

- `Platform.LINUX`, `Platform.MACOS`, `Platform.WINDOWS` — enum of supported
  filesystem families.
- `PathLimit(maximum, unit)` — a limit and its unit (`"bytes"` or
  `"utf-16-code-units"`).
- `DEFAULT_LIMITS` — mapping from `Platform` to the default `PathLimit`.
- `limit_for(platform)` — look up a default limit.
- `validate_path(path, platform=Platform.LINUX, limit=None)` — raise
  `PathTooLongError` if the path is too long, otherwise return the measured
  length.
- `is_path_valid(path, platform=Platform.LINUX, limit=None)` — boolean form
  that never raises for invalid input.
- `PathLengthError` — base class for path length failures.
- `PathTooLongError` — subclass raised when a path exceeds its limit; carries
  `.path`, `.limit` and `.actual`.
