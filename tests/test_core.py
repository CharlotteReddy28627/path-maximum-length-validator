"""Tests for path_maximum_length_validator.core.

Every test here exercises behaviour that ``core`` actually implements.
Nothing is asserted about wall-clock time or about floating point values.
"""

import os
import unittest

from path_maximum_length_validator import (
    DEFAULT_LIMITS,
    PathLengthError,
    PathLimit,
    PathTooLongError,
    Platform,
    is_path_valid,
    limit_for,
    validate_path,
)


class PlatformLimitTests(unittest.TestCase):
    def test_default_limits_cover_every_platform(self) -> None:
        for platform in Platform:
            self.assertIn(platform, DEFAULT_LIMITS)

    def test_limit_for_returns_expected_units(self) -> None:
        self.assertEqual(limit_for(Platform.LINUX).unit, "bytes")
        self.assertEqual(limit_for(Platform.MACOS).unit, "bytes")
        self.assertEqual(limit_for(Platform.WINDOWS).unit, "utf-16-code-units")

    def test_limit_for_rejects_unknown_platform(self) -> None:
        with self.assertRaises(ValueError):
            limit_for("linux")  # type: ignore[arg-type]


class PathLimitTests(unittest.TestCase):
    def test_rejects_non_positive_maximum(self) -> None:
        with self.assertRaises(ValueError):
            PathLimit(maximum=0, unit="bytes")
        with self.assertRaises(ValueError):
            PathLimit(maximum=-1, unit="bytes")

    def test_rejects_unknown_unit(self) -> None:
        with self.assertRaises(ValueError):
            PathLimit(maximum=10, unit="characters")


class ValidatePathTests(unittest.TestCase):
    def test_short_path_returns_measured_length(self) -> None:
        # The measurement is in the limit's unit, so a 5-character ASCII path
        # is 5 bytes.
        self.assertEqual(validate_path("hello"), 5)

    def test_exact_limit_is_allowed(self) -> None:
        limit = PathLimit(maximum=5, unit="bytes")
        self.assertEqual(validate_path("abcde", limit=limit), 5)

    def test_one_over_limit_raises(self) -> None:
        limit = PathLimit(maximum=5, unit="bytes")
        with self.assertRaises(PathTooLongError) as ctx:
            validate_path("abcdef", limit=limit)
        self.assertEqual(ctx.exception.actual, 6)
        self.assertEqual(ctx.exception.limit, limit)
        self.assertEqual(ctx.exception.path, "abcdef")

    def test_multibyte_characters_are_counted_as_bytes(self) -> None:
        # "é" is two bytes in UTF-8.  A three-character path is therefore
        # five bytes, which is the point of measuring bytes rather than
        # characters.
        limit = PathLimit(maximum=4, unit="bytes")
        with self.assertRaises(PathTooLongError) as ctx:
            validate_path("aéé", limit=limit)
        self.assertEqual(ctx.exception.actual, 5)

    def test_windows_limit_counts_utf16_code_units(self) -> None:
        # U+1F600 is a single character but two UTF-16 code units.  Under the
        # Windows limit it must count as two, not one and not four.
        limit = PathLimit(maximum=2, unit="utf-16-code-units")
        self.assertEqual(validate_path("\U0001F600", limit=limit), 2)
        with self.assertRaises(PathTooLongError) as ctx:
            validate_path("\U0001F600\U0001F600", limit=limit)
        self.assertEqual(ctx.exception.actual, 4)

    def test_empty_path_raises_path_length_error(self) -> None:
        with self.assertRaises(PathLengthError):
            validate_path("")

    def test_bytes_path_is_decoded_and_measured(self) -> None:
        self.assertEqual(validate_path(b"hello"), 5)

    def test_pathlike_is_accepted(self) -> None:
        class FakePath:
            def __fspath__(self) -> str:
                return "hello"

        self.assertEqual(validate_path(FakePath()), 5)

    def test_unsupported_type_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            validate_path(123)  # type: ignore[arg-type]

    def test_explicit_limit_overrides_platform(self) -> None:
        # The platform default for Windows is 259 UTF-16 code units, but an
        # explicit limit must win.
        limit = PathLimit(maximum=3, unit="bytes")
        with self.assertRaises(PathTooLongError):
            validate_path("abcd", platform=Platform.WINDOWS, limit=limit)


class IsPathValidTests(unittest.TestCase):
    def test_returns_true_for_short_path(self) -> None:
        self.assertTrue(is_path_valid("hello"))

    def test_returns_false_for_long_path(self) -> None:
        limit = PathLimit(maximum=3, unit="bytes")
        self.assertFalse(is_path_valid("abcd", limit=limit))

    def test_returns_false_for_empty_path(self) -> None:
        self.assertFalse(is_path_valid(""))

    def test_returns_false_for_unsupported_type(self) -> None:
        self.assertFalse(is_path_valid(object()))  # type: ignore[arg-type]

    def test_agrees_with_validate_path_on_boundary(self) -> None:
        limit = PathLimit(maximum=4, unit="bytes")
        self.assertTrue(is_path_valid("abcd", limit=limit))
        self.assertFalse(is_path_valid("abcde", limit=limit))


if __name__ == "__main__":
    unittest.main()
