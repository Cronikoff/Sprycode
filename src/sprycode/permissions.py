"""
SpryCode Permission System

Enforces the security model: all sensitive operations require explicit permission grants.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field


class PermissionError(Exception):
    """Raised when a program attempts an operation without declared permission."""


@dataclass
class Permission:
    """A single permission grant or denial."""
    kind: str          # e.g. "filesystem.read", "network.request", "secret.read"
    argument: str | None = None  # e.g. a path or URL pattern
    granted: bool = True


class PermissionSet:
    """
    Tracks the current set of allowed and denied operations.

    Permissions are evaluated in declaration order; the last matching rule wins.
    """

    def __init__(self) -> None:
        self._rules: list[Permission] = []
        self._secure_mode: bool = False

    def add_allow(self, kind: str, argument: str | None = None) -> None:
        self._rules.append(Permission(kind=kind, argument=argument, granted=True))

    def add_deny(self, kind: str, argument: str | None = None) -> None:
        self._rules.append(Permission(kind=kind, argument=argument, granted=False))

    def enable_secure_mode(self) -> None:
        self._secure_mode = True

    def check(self, kind: str, argument: str | None = None) -> None:
        """
        Raise PermissionError if the given operation is not permitted.
        In non-secure mode, all operations are allowed by default unless explicitly denied.
        In secure mode, operations must be explicitly allowed.
        """
        matched_grant: bool | None = None

        for rule in reversed(self._rules):
            if self._matches_kind(rule.kind, kind):
                if rule.argument is None or self._matches_arg(rule.argument, argument or ""):
                    matched_grant = rule.granted
                    break

        if self._secure_mode:
            if matched_grant is not True:
                arg_str = f" {argument!r}" if argument else ""
                raise PermissionError(
                    f"Permission denied: {kind}{arg_str}. "
                    f"Add 'allow {kind}{arg_str}' to your program."
                )
        else:
            if matched_grant is False:
                arg_str = f" {argument!r}" if argument else ""
                raise PermissionError(
                    f"Permission explicitly denied: {kind}{arg_str}."
                )

    def is_allowed(self, kind: str, argument: str | None = None) -> bool:
        """Return True if allowed, False if not (no exception)."""
        try:
            self.check(kind, argument)
            return True
        except PermissionError:
            return False

    def _matches_kind(self, pattern: str, kind: str) -> bool:
        """Match permission kinds, supporting wildcards."""
        if pattern == kind:
            return True
        if pattern.endswith(".all"):
            prefix = pattern[:-4]
            return kind.startswith(prefix)
        return fnmatch.fnmatch(kind, pattern)

    def _matches_arg(self, pattern: str, argument: str) -> bool:
        """Match argument using glob-style matching."""
        if pattern == argument:
            return True
        # Normalize path separators
        pattern = pattern.replace("\\", "/")
        argument = argument.replace("\\", "/")
        return fnmatch.fnmatch(argument, pattern) or argument.startswith(pattern.rstrip("*"))

    def clone(self) -> "PermissionSet":
        """Create a copy for use in nested scopes."""
        new = PermissionSet()
        new._rules = list(self._rules)
        new._secure_mode = self._secure_mode
        return new
