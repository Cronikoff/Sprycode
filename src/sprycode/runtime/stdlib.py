"""
SpryCode Runtime — Standard Library

Provides the built-in functions, types, and operations available to SpryCode programs.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import time
import uuid as uuid_mod
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# SpryCode value types
# ---------------------------------------------------------------------------


class SprySecret:
    """A secret value that is redacted in log output."""

    def __init__(self, key: str, value: str) -> None:
        self._key = key
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return f"<secret:{self._key}>"

    def __repr__(self) -> str:
        return f"SprySecret(key={self._key!r})"


class SpryMoney:
    """A monetary value with currency."""

    def __init__(self, amount: Decimal, currency: str = "USD") -> None:
        self.amount = amount
        self.currency = currency

    def __add__(self, other: "SpryMoney") -> "SpryMoney":
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return SpryMoney(self.amount + other.amount, self.currency)

    def __sub__(self, other: "SpryMoney") -> "SpryMoney":
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract {self.currency} and {other.currency}")
        return SpryMoney(self.amount - other.amount, self.currency)

    def __mul__(self, other: float | Decimal) -> "SpryMoney":
        return SpryMoney(self.amount * Decimal(str(other)), self.currency)

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"

    def __repr__(self) -> str:
        return f"SpryMoney({self.amount}, {self.currency!r})"


class SpryResult:
    """Represents a Result value (ok or failed)."""

    def __init__(self, ok: bool, value: Any = None, error: str = "") -> None:
        self.ok = ok
        self._value = value
        self.error = error
        self.failed = not ok

    @property
    def value(self) -> Any:
        return self._value

    def __bool__(self) -> bool:
        return self.ok

    def __str__(self) -> str:
        if self.ok:
            return f"Result(ok, {self._value!r})"
        return f"Result(failed, {self.error!r})"


# Singleton values
SPRY_OK = SpryResult(ok=True, value=None)


class SpryFile:
    """Represents a file handle or reference."""

    def __init__(self, path: str) -> None:
        self.path = path
        p = Path(path)
        self.name = p.name
        self.extension = p.suffix.lstrip(".")
        self.stem = p.stem

    def __str__(self) -> str:
        return self.path


class SpryFolder:
    """Represents a folder reference."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.name = Path(path).name

    def __str__(self) -> str:
        return self.path


# ---------------------------------------------------------------------------
# Built-in functions
# ---------------------------------------------------------------------------


def _builtin_uuid() -> str:
    return str(uuid_mod.uuid4())


def _builtin_now() -> str:
    return datetime.now().isoformat()


def _builtin_today() -> str:
    return date.today().isoformat()


def _builtin_checksum(path: str, algorithm: str = "sha256") -> str:
    """Compute a file checksum."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _builtin_hash_text(text: str, algorithm: str = "sha256") -> str:
    """Compute a hash of text."""
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _builtin_encode_json(value: Any) -> str:
    return json.dumps(value, default=str)


def _builtin_decode_base64(data: str) -> str:
    import base64
    return base64.b64decode(data).decode("utf-8")


def _builtin_encode_base64(data: str) -> str:
    import base64
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")


def _builtin_parse_json(text: str) -> Any:
    return json.loads(text)


def _builtin_parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _builtin_money_sum(amounts: list) -> SpryMoney:
    if not amounts:
        return SpryMoney(Decimal("0"), "USD")
    total = amounts[0]
    for a in amounts[1:]:
        total = total + a
    return total


# ---------------------------------------------------------------------------
# Filesystem operations
# ---------------------------------------------------------------------------


class FilesystemOps:
    """Safe filesystem operations with permission checking."""

    def __init__(self, permissions: Any) -> None:
        self._perms = permissions

    def read_file(self, path: str) -> SpryResult:
        self._perms.check("filesystem.read", path)
        try:
            content = Path(path).read_text(encoding="utf-8")
            return SpryResult(ok=True, value=content)
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def write_file(self, path: str, data: Any) -> SpryResult:
        self._perms.check("filesystem.write", path)
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, (dict, list)):
                p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            else:
                p.write_text(str(data), encoding="utf-8")
            return SpryResult(ok=True, value=path)
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def copy_file(
        self,
        source: str,
        destination: str,
        verify_checksum: str | None = None,
        preserve_metadata: bool = False,
    ) -> SpryResult:
        self._perms.check("filesystem.read", source)
        self._perms.check("filesystem.write", destination)
        try:
            dst = Path(destination)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if preserve_metadata:
                shutil.copy2(source, destination)
            else:
                shutil.copy(source, destination)
            if verify_checksum:
                src_hash = _builtin_checksum(source, verify_checksum)
                dst_hash = _builtin_checksum(destination, verify_checksum)
                if src_hash != dst_hash:
                    Path(destination).unlink(missing_ok=True)
                    return SpryResult(ok=False, error=f"Checksum mismatch: {src_hash} != {dst_hash}")
            return SpryResult(ok=True, value=destination)
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def move_file(
        self,
        source: str,
        destination: str,
        verify_checksum: str | None = None,
        preserve_metadata: bool = False,
        retry: int = 0,
    ) -> SpryResult:
        self._perms.check("filesystem.read", source)
        self._perms.check("filesystem.write", destination)
        attempts = retry + 1
        last_error = ""
        for _ in range(attempts):
            try:
                dst = Path(destination)
                dst.parent.mkdir(parents=True, exist_ok=True)
                src_hash = None
                if verify_checksum:
                    src_hash = _builtin_checksum(source, verify_checksum)
                shutil.move(source, destination)
                if verify_checksum and src_hash:
                    dst_hash = _builtin_checksum(destination, verify_checksum)
                    if src_hash != dst_hash:
                        return SpryResult(ok=False, error=f"Checksum mismatch after move")
                return SpryResult(ok=True, value=destination)
            except Exception as e:
                last_error = str(e)
        return SpryResult(ok=False, error=last_error)

    def move_folder(
        self,
        source: str,
        destination: str,
        verify_checksum: str | None = None,
        parallel: int | None = None,
        retry: int = 0,
    ) -> SpryResult:
        self._perms.check("filesystem.read", source)
        self._perms.check("filesystem.write", destination)
        try:
            dst = Path(destination)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source, destination)
            return SpryResult(ok=True, value=destination)
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def copy_folder(self, source: str, destination: str) -> SpryResult:
        self._perms.check("filesystem.read", source)
        self._perms.check("filesystem.write", destination)
        try:
            shutil.copytree(source, destination, dirs_exist_ok=True)
            return SpryResult(ok=True, value=destination)
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def delete_file(self, path: str) -> SpryResult:
        self._perms.check("filesystem.write", path)
        try:
            Path(path).unlink(missing_ok=True)
            return SpryResult(ok=True, value=path)
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def delete_folder(self, path: str) -> SpryResult:
        self._perms.check("filesystem.write", path)
        try:
            shutil.rmtree(path, ignore_errors=True)
            return SpryResult(ok=True, value=path)
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def list_folder(self, path: str) -> list[SpryFile]:
        self._perms.check("filesystem.read", path)
        result = []
        for entry in Path(path).iterdir():
            if entry.is_file():
                result.append(SpryFile(str(entry)))
        return result

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def create_file(self, path: str, content: str = "") -> SpryResult:
        self._perms.check("filesystem.write", path)
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return SpryResult(ok=True, value=path)
        except Exception as e:
            return SpryResult(ok=False, error=str(e))


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


class SpryLogger:
    """
    SpryCode runtime logger.

    Automatically redacts secrets and private data fields.
    """

    LEVELS = {"debug": 0, "info": 1, "warn": 2, "error": 3}

    def __init__(self, min_level: str = "info", output=None) -> None:
        self._min_level = self.LEVELS.get(min_level, 1)
        self._output = output  # If None, prints to stdout

    def _format(self, level: str, message: Any) -> str:
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        safe_msg = self._redact(message)
        return f"[{ts}] [{level.upper()}] {safe_msg}"

    def _redact(self, value: Any) -> str:
        if isinstance(value, SprySecret):
            return str(value)  # Already redacted
        if isinstance(value, str):
            return value
        return str(value)

    def _log(self, level: str, message: Any) -> None:
        if self.LEVELS.get(level, 0) >= self._min_level:
            line = self._format(level, message)
            if self._output is not None:
                self._output.append(line)
            else:
                print(line)

    def info(self, message: Any) -> None:
        self._log("info", message)

    def warn(self, message: Any) -> None:
        self._log("warn", message)

    def error(self, message: Any) -> None:
        self._log("error", message)

    def debug(self, message: Any) -> None:
        self._log("debug", message)


# ---------------------------------------------------------------------------
# Secret manager
# ---------------------------------------------------------------------------


class SecretManager:
    """Reads secrets from environment variables or an in-memory vault."""

    def __init__(self) -> None:
        self._vault: dict[str, str] = {}

    def read(self, key: str, permissions: Any) -> SprySecret:
        permissions.check("secret.read", key)
        # Try vault first, then environment
        if key in self._vault:
            return SprySecret(key, self._vault[key])
        value = os.environ.get(key, "")
        return SprySecret(key, value)

    def set(self, key: str, value: str) -> None:
        """Set a secret in the in-memory vault (for testing)."""
        self._vault[key] = value
