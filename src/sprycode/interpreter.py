"""
SpryCode Interpreter

Tree-walking interpreter for SpryCode AST nodes.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from decimal import Decimal
from typing import Any

_SENTINEL = object()  # Used as a default "not provided" sentinel
_MAX_FLAT_DEPTH = 10_000  # Effective limit for array.flat(Infinity)

from .ast_nodes import (
    AdapterDeclaration,
    AllowStatement,
    AppDeclaration,
    ArrayLiteral,
    AssertStatement,
    Assignment,
    AtomicStatement,
    BinaryExpression,
    Block,
    DeclarationList,
    BoolLiteral,
    BreakStatement,
    CallExpression,
    ClassDeclaration,
    ClassExpression,
    CompensateStatement,
    CompoundAssignment,
    CompoundMemberAssignment,
    CompressStatement,
    ConnectorDeclaration,
    ContinueStatement,
    CopyStatement,
    CreateStatement,
    CreditStatement,
    DebitStatement,
    DeleteStatement,
    DenyStatement,
    DoWhileStatement,
    EnumDeclaration,
    ExportStatement,
    ExpectStatement,
    ExtractStatement,
    ForStatement,
    ForCStyleStatement,
    FraudCheckStatement,
    FStringExpression,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    ImportStatement,
    IndexAssignment,
    InExpression,
    IndexExpression,
    InstanceofExpression,
    InterfaceDeclaration,
    LabeledStatement,
    LambdaExpression,
    LetDeclaration,
    ListComprehension,
    DictComprehension,
    ListDestructure,
    ListDestructureAssignment,
    LogStatement,
    MatchArm,
    MatchStatement,
    MemberAssignment,
    MemberExpression,
    MoveStatement,
    MultiParamLambda,
    Node,
    NullCoalesceExpression,
    NullLiteral,
    NumberLiteral,
    ObjectDestructure,
    ObjectLiteral,
    OptionalMemberExpression,
    OptionalIndexExpression,
    ParseStatement,
    PipelineExpression,
    PostfixExpression,
    PrivateDataDeclaration,
    Program,
    ReadStatement,
    RedactStatement,
    RegexLiteral,
    RepeatUntilStatement,
    ReturnStatement,
    ScheduleStatement,
    SecretLiteral,
    SensitiveDataDeclaration,
    SleepStatement,
    SpawnStatement,
    SpreadElement,
    StopStatement,
    StreamStatement,
    StringLiteral,
    StructDeclaration,
    SwitchStatement,
    AnonymousFunctionExpression,
    SyncStatement,
    TaskDeclaration,
    TernaryExpression,
    TestBlock,
    ThrowStatement,
    TransactionStatement,
    TryCatchStatement,
    TypeCastExpression,
    TypeofExpression,
    ResultLiteral,
    UnaryExpression,
    UseStatement,
    ValidateStatement,
    VarDeclaration,
    WatchStatement,
    WebSocketStatement,
    WhileStatement,
    WithStatement,
    WriteStatement,
    YieldStatement,
    SuperExpression,
    GetterDeclaration,
    SetterDeclaration,
    TaggedTemplateExpression,
    AwaitExpression,
    OptionalCallExpression,
    ComputedMethodDeclaration,
    SequenceExpression,
    NewTargetExpression,
    UsingDeclaration,
    ComputedFieldDeclaration,
    NewExpression,
    DebuggerStatement,
    LoopStatement,
    RetryStatement,
)
from .permissions import PermissionSet
from .runtime.stdlib import (
    SPRY_OK,
    AuditLogger,
    FilesystemOps,
    SecretManager,
    SpryFile,
    SpryFolder,
    SpryLogger,
    SpryMoney,
    SpryResult,
    SprySecret,
    SqlAdapter,
    _builtin_checksum,
    _builtin_decode_base64,
    _builtin_encode_base64,
    _builtin_encode_json,
    _builtin_hash_text,
    _builtin_now,
    _builtin_parse_csv,
    _builtin_parse_json,
    _builtin_parse_yaml,
    _builtin_encode_yaml,
    _builtin_today,
    _builtin_uuid,
)


# ---------------------------------------------------------------------------
# Runtime control exceptions (used as signals, not errors)
# ---------------------------------------------------------------------------


class _SpryUndefinedType:
    """Singleton sentinel for the JS ``undefined`` value.

    Distinct from ``None`` (which represents ``null``) so that
    ``String(undefined)`` → ``'undefined'`` and ``typeof undefined`` → ``'undefined'``
    work correctly when the caller explicitly passes the ``undefined`` global.

    JS loose equality: ``undefined == null`` is ``True``.
    JS strict equality: ``undefined === null`` is ``False``.
    """

    _instance: "_SpryUndefinedType | None" = None

    def __new__(cls) -> "_SpryUndefinedType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __eq__(self, other: object) -> bool:
        # JS: undefined == null → True, undefined == undefined → True
        if isinstance(other, _SpryUndefinedType):
            return True
        if other is None:
            return True
        return False

    def __hash__(self) -> int:
        return hash(None)

    def __repr__(self) -> str:
        return "undefined"

    def __bool__(self) -> bool:
        return False


#: The singleton ``undefined`` value used throughout the SpryCode runtime.
SPRY_UNDEFINED = _SpryUndefinedType()
# Module-level sets tracking frozen/sealed object ids for non-polluting O.freeze/O.seal
_SPRY_FROZEN_IDS: set = set()
_SPRY_SEALED_IDS: set = set()


def _make_sequence_iter(items: list) -> Any:
    """Return a callable that creates a fresh iterator dict over *items*.

    Each call to the returned factory produces an independent iterator with
    a ``next()`` method following the ``{value, done}`` protocol.
    """
    def _factory(_items: list = items) -> dict:
        state: dict = {"i": 0}

        def _next() -> dict:
            if state["i"] < len(_items):
                v = _items[state["i"]]
                state["i"] += 1
                return {"value": v, "done": False}
            return {"value": SPRY_UNDEFINED, "done": True}

        return {"next": _next}

    return _factory


def _dict_has_ics(d: dict) -> bool:
    """Return True if *d* has Symbol.isConcatSpreadable set to True."""
    _ics_str = "Symbol('isConcatSpreadable')"
    if d.get(_ics_str) is True:
        return True
    for k, v in d.items():
        if isinstance(k, SprySymbol) and k.description == "isConcatSpreadable" and v is True:
            return True
    return False


def _inst_has_ics(inst: Any) -> bool:
    """Return True if *inst* (SpryInstance) has Symbol.isConcatSpreadable set to True."""
    _ics_str = "Symbol('isConcatSpreadable')"
    if inst.fields.get(_ics_str) is True:
        return True
    for k, v in inst.fields.items():
        if isinstance(k, SprySymbol) and k.description == "isConcatSpreadable" and v is True:
            return True
    return False


def _owns_prop(obj: Any, key: str) -> bool:
    """Return True if *obj* (dict or SpryInstance) has *key* as an own property."""
    if isinstance(obj, dict):
        return key in obj
    # SpryInstance — check fields but exclude internal double-underscore keys
    fields = getattr(obj, "fields", None)
    if fields is not None:
        return key in fields and not key.startswith("__")
    return False


def _strict_eq(left: Any, right: Any) -> bool:
    """Strict equality (===): same type AND same value; objects compared by identity."""
    if type(left) is not type(right):
        # Allow numeric interop between int and float (but not bool)
        if (isinstance(left, (int, float)) and not isinstance(left, bool) and
                isinstance(right, (int, float)) and not isinstance(right, bool)):
            return left == right
        return False
    if isinstance(left, (dict, list)) or isinstance(left, SpryInstance):
        return left is right
    return left == right


def _abstract_eq(left: Any, right: Any) -> bool:
    """Abstract (loose) equality (==): JS-style type coercion rules."""
    # Same type — use strict equality
    if type(left) is type(right):
        if isinstance(left, (dict, list)) or isinstance(left, SpryInstance):
            return left is right
        return left == right
    # null == undefined (and vice versa), but nothing else
    if left is None and isinstance(right, _SpryUndefinedType):
        return True
    if isinstance(left, _SpryUndefinedType) and right is None:
        return True
    if (left is None or isinstance(left, _SpryUndefinedType)) and (right is None or isinstance(right, _SpryUndefinedType)):
        return True
    if left is None or isinstance(left, _SpryUndefinedType):
        return False
    if right is None or isinstance(right, _SpryUndefinedType):
        return False
    # bool → number
    if isinstance(left, bool):
        left = 1 if left else 0
        return _abstract_eq(left, right)
    if isinstance(right, bool):
        right = 1 if right else 0
        return _abstract_eq(left, right)
    # string + number → coerce string to number
    if isinstance(left, str) and isinstance(right, (int, float)):
        try:
            s = left.strip()
            lv: float | int = int(s) if s else 0
        except ValueError:
            try:
                lv = float(s)
            except ValueError:
                lv = float("nan")
        return lv == right
    if isinstance(right, str) and isinstance(left, (int, float)):
        try:
            s = right.strip()
            rv: float | int = int(s) if s else 0
        except ValueError:
            try:
                rv = float(s)
            except ValueError:
                rv = float("nan")
        return left == rv
    # numeric interop int/float
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return left == right


class ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class StopSignal(Exception):
    pass


class BreakSignal(Exception):
    def __init__(self, label: str | None = None) -> None:
        self.label = label


class ContinueSignal(Exception):
    def __init__(self, label: str | None = None) -> None:
        self.label = label


class YieldSignal(Exception):
    """Raised by a `yield` statement inside a generator function."""
    def __init__(self, value: Any) -> None:
        self.value = value


class SpryUserError(Exception):
    """User-raised error from a `throw` statement."""
    def __init__(self, value: Any) -> None:
        self.value = value
        # Extract message for str() compatibility
        if isinstance(value, dict):
            msg = str(value.get("message", value))
        else:
            msg = str(value)
        super().__init__(msg)
        self.message = msg


class SpryRuntimeError(Exception):
    def __init__(self, message: str, node: Node | None = None) -> None:
        loc = ""
        if node is not None:
            loc = f" at line {node.line}, column {node.column}"
        super().__init__(f"Runtime error{loc}: {message}")
        self.node = node


# ---------------------------------------------------------------------------
# Environment (scope)
# ---------------------------------------------------------------------------


class Environment:
    """Variable scope with support for nested environments."""

    def __init__(self, parent: "Environment | None" = None) -> None:
        self._vars: dict[str, Any] = {}
        self._mutables: set[str] = set()
        self.parent = parent

    def define(self, name: str, value: Any, mutable: bool = False) -> None:
        self._vars[name] = value
        if mutable:
            self._mutables.add(name)

    def get(self, name: str) -> Any:
        if name in self._vars:
            return self._vars[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise SpryRuntimeError(f"Undefined variable: {name!r}")

    def set(self, name: str, value: Any) -> None:
        if name in self._vars:
            if name not in self._mutables:
                raise SpryRuntimeError(
                    f"Cannot assign to immutable variable {name!r}. Use 'var' to declare a mutable variable."
                )
            self._vars[name] = value
            return
        if self.parent is not None:
            self.parent.set(name, value)
            return
        raise SpryRuntimeError(f"Undefined variable: {name!r}")

    def has(self, name: str) -> bool:
        if name in self._vars:
            return True
        if self.parent is not None:
            return self.parent.has(name)
        return False

    def __getitem__(self, name: str) -> Any:
        return self.get(name)

    def child(self) -> "Environment":
        return Environment(parent=self)


# ---------------------------------------------------------------------------
# SpryCode function (user-defined)
# ---------------------------------------------------------------------------


class SpryFunction:
    def __init__(
        self,
        name: str,
        params: list[tuple[str, str | None]],
        body: "Block",
        closure: Environment,
        defaults: "dict | None" = None,
        rest_param: "str | None" = None,
        is_generator: bool = False,
        is_async: bool = False,
    ) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.defaults: dict = defaults or {}
        self.rest_param: str | None = rest_param
        self.is_generator: bool = is_generator
        self.is_async: bool = is_async
        self._prototype: "dict | None" = None  # for use as constructor via new Fn()

    def __repr__(self) -> str:
        return f"<fn{'*' if self.is_generator else ''} {self.name}>"


class SpryTask:
    def __init__(self, name: str, body: "Block", closure: Environment) -> None:
        self.name = name
        self.body = body
        self.closure = closure

    def __repr__(self) -> str:
        return f"<task {self.name}>"


class SpryLambda:
    """An anonymous single-param lambda with a captured closure environment."""

    def __init__(self, param: str, body: Any, closure: Environment) -> None:
        self.param = param
        self.body = body
        self.closure = closure
        self.name: str = ""
        self.operation: str | None = None  # used by pipeline stages

    def __repr__(self) -> str:
        return f"<lambda {self.param}>"


class SpryMultiLambda:
    """An anonymous multi-param lambda with a captured closure environment."""

    def __init__(self, params: list[str], body: Any, closure: Environment) -> None:
        self.params = params
        self.body = body
        self.closure = closure
        self.name: str = ""
        self.operation: str | None = None  # used by pipeline stages
        self.init: Any = None  # used by reduce_with_init

    def __repr__(self) -> str:
        return f"<lambda ({', '.join(self.params)})>"


class SpryEnum:
    """Runtime representation of an enum type."""

    def __init__(self, name: str, variants: list[str]) -> None:
        self.name = name
        self.variants = variants
        # Each variant is stored as a dict: {__enum__: name, __variant__: "Red"}
        for v in variants:
            setattr(self, v, {"__enum__": name, "__variant__": v})

    def __repr__(self) -> str:
        return f"<enum {self.name}>"


class SpryClass:
    """Runtime representation of a class definition."""

    def __init__(
        self,
        name: str,
        body: "Block",
        closure: Environment,
        superclass: "SpryClass | None" = None,
    ) -> None:
        self.name = name
        self.body = body
        self.closure = closure
        self.superclass = superclass
        self._static_fields: dict = {}  # mutable static field storage
        self._prototype: "SpryClassPrototype | None" = None  # lazily created

    @property
    def prototype(self) -> "SpryClassPrototype":
        if self._prototype is None:
            self._prototype = SpryClassPrototype(self)
        return self._prototype

    def __repr__(self) -> str:
        return f"<class {self.name}>"

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.name == other
        return self is other

    def __hash__(self) -> int:
        return id(self)


class SpryClassPrototype:
    """Represents `SomeClass.prototype` — used for identity comparisons with Object.getPrototypeOf."""

    def __init__(self, cls: SpryClass) -> None:
        self.cls = cls
        self._extra_fields: dict = {}  # methods/fields added via Object.assign(Cls.prototype, ...)

    def toString(self) -> str:
        return f"[object {self.cls.name}]"

    def __repr__(self) -> str:
        return f"{self.cls.name}.prototype"


class SpryInstance:
    """Runtime representation of a class instance."""

    def __init__(self, cls: SpryClass, fields: dict[str, Any]) -> None:
        self.cls = cls
        self.fields = fields  # mutable instance fields

    def get(self, name: str) -> Any:
        if name in self.fields:
            return self.fields[name]
        raise KeyError(name)

    def set(self, name: str, value: Any) -> None:
        self.fields[name] = value

    def __getitem__(self, key: Any) -> Any:
        """Support p["fieldName"] indexing on instances."""
        k = str(key)
        if k in self.fields:
            return self.fields[k]
        raise KeyError(k)

    def __setitem__(self, key: Any, value: Any) -> None:
        """Support p["fieldName"] = value on instances."""
        self.fields[str(key)] = value

    def __repr__(self) -> str:
        return f"<{self.cls.name} {self.fields!r}>"


class SpryStruct:
    """Runtime representation of a struct type (constructor factory)."""

    def __init__(self, name: str, fields: list[tuple[str, str | None]]) -> None:
        self.name = name
        self.field_names = [f for f, _ in fields]

    def __repr__(self) -> str:
        return f"<struct {self.name}>"

    def create(self, args: list[Any]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for i, fname in enumerate(self.field_names):
            obj[fname] = args[i] if i < len(args) else None
        obj["__struct__"] = self.name
        return obj


class BoundMethod:
    """A SpryCode method bound to an instance (provides implicit self).

    When a SpryCode class method is accessed through an instance (e.g. ``obj.greet``),
    we wrap it in a ``BoundMethod`` so that ``self`` is automatically bound during
    invocation via ``_call_bound_method``.  This is analogous to Python's bound
    method objects.
    """

    def __init__(self, instance: "SpryInstance", fn: "SpryFunction") -> None:
        self.instance = instance
        self.fn = fn

    def __repr__(self) -> str:
        return f"<bound method {self.fn.name}>"


class DictBoundMethod:
    """A SpryCode function/lambda bound to a plain dict object.

    When a ``SpryFunction`` is accessed as a property of a dict (plain object literal),
    we wrap it so ``this`` is automatically bound to the dict when the method is called.
    This gives object-literal methods the same ``this`` binding behaviour as class methods.
    """

    def __init__(self, obj: dict, fn: Any) -> None:
        self.obj = obj
        self.fn = fn

    def __repr__(self) -> str:
        name = getattr(self.fn, "name", "<anonymous>")
        return f"<dict method {name}>"


class SpryRegex:
    """Runtime representation of a regex literal (compiled re pattern)."""

    def __init__(self, pattern: "re.Pattern[str]", global_flag: bool = False,
                 flags_str: str = "") -> None:
        self.pattern = pattern
        self.global_flag = global_flag
        self.flags_str = flags_str  # original JS flag string e.g. "gi"
        self.lastIndex = 0  # for global/sticky exec iteration

    def test(self, text: str) -> bool:
        return bool(self.pattern.search(text))

    def match(self, text: str) -> Any:
        m = self.pattern.search(text)
        if m is None:
            return None
        groups = [m.group(0)] + list(m.groups())
        return SpryRegexMatch(groups, m.start(), text, named_groups=m.groupdict() or {})

    def exec(self, text: str) -> Any:
        if self.global_flag and self.lastIndex > 0:
            m = self.pattern.search(text, self.lastIndex)
        else:
            m = self.pattern.search(text)
        if m is None:
            self.lastIndex = 0
            return None
        if self.global_flag:
            self.lastIndex = m.end()
        groups = [m.group(0)] + list(m.groups())
        return SpryRegexMatch(groups, m.start(), text, named_groups=m.groupdict() or {})

    def replace(self, text: str, replacement: str, count: int = 1) -> str:
        actual_count = 0 if self.global_flag else count
        return self.pattern.sub(replacement, text, count=actual_count)

    def split(self, text: str) -> list[str]:
        return self.pattern.split(text)

    def findAll(self, text: str) -> list[str]:
        return self.pattern.findall(text)

    def __repr__(self) -> str:
        return f"<regex /{self.pattern.pattern}/>"


class _RegExpNamespace:
    """RegExp global constructor — RegExp(pattern, flags) or new RegExp(pattern, flags)."""

    def __call__(self, pattern: Any = "", flags: Any = "") -> "SpryRegex":
        return self._create(pattern, flags)

    def new(self, pattern: Any = "", flags: Any = "") -> "SpryRegex":
        return self._create(pattern, flags)

    def _create(self, pattern: Any, flags: Any) -> "SpryRegex":
        import re as _re
        if isinstance(pattern, SpryRegex):
            return pattern  # pass-through
        pat_str = str(pattern)
        flags_str = str(flags) if flags else ""
        py_flags = 0
        is_global = False
        for f in flags_str:
            if f == "i":
                py_flags |= _re.IGNORECASE
            elif f == "m":
                py_flags |= _re.MULTILINE
            elif f == "s":
                py_flags |= _re.DOTALL
            elif f == "g":
                is_global = True
        try:
            compiled = _re.compile(pat_str, py_flags)
        except _re.error:
            compiled = _re.compile(_re.escape(pat_str), py_flags)
        return SpryRegex(compiled, global_flag=is_global, flags_str=flags_str)

    def __repr__(self) -> str:
        return "RegExp"


class SpryTaggedStringList(list):
    """Array-like strings argument for tagged template literals.
    Behaves like a list, but also has a `.raw` property containing
    the raw (unescaped) string parts."""
    def __init__(self, cooked: list, raw: list) -> None:
        super().__init__(cooked)
        self.raw = raw


class SpryRegexMatch(list):
    """Array-like regex match result: [full, group1, group2, ...] with .index, .input, .groups."""
    def __init__(self, groups: list, index: int, input_str: str,
                 named_groups: "dict | None" = None) -> None:
        super().__init__(groups)
        self.index = index
        self.input = input_str
        self.groups = named_groups or {}

    def __repr__(self) -> str:
        return f"RegexMatch({list(self)!r}, index={self.index})"


class SpryWebSocket:
    """Runtime representation of a WebSocket connection (stub)."""

    def __init__(self, url: str, interpreter: "Interpreter") -> None:
        self.url = url
        self._interp = interpreter
        self._handlers: list[Any] = []
        self.connected = True

    def send(self, message: Any) -> None:
        self._interp.logger.info(f"[WebSocket] send → {self.url!r}: {message!r}")

    def close(self) -> None:
        self.connected = False
        self._interp.logger.info(f"[WebSocket] closed {self.url!r}")

    def onMessage(self, handler: Any) -> None:
        """Register a message handler (stored but not called at runtime)."""
        self._handlers.append(handler)

    def __repr__(self) -> str:
        return f"<WebSocket {self.url!r} connected={self.connected}>"


class _Missing:
    """Sentinel for missing optional arguments (e.g. reduce initial value)."""
    def __repr__(self) -> str:
        return "<missing>"


_MISSING = _Missing()


class _CallableList(list):
    """A list that is also callable — used for properties like `.flat` that work both
    as `list.flat` (returns default result) and `list.flat(depth)` (parameterised)."""

    def __init__(self, items: list, fn: Any) -> None:
        super().__init__(items)
        self._fn = fn

    def __call__(self, *args: Any) -> Any:
        return self._fn(*args)


class SpryIterator:
    """JS-compatible iterator with .next() → {value, done} dict interface.

    Also compares equal to the underlying list for backward compatibility
    with existing tests that use `assert result == [...]`.

    Supports TC39 Iterator Helpers (filter, map, take, drop, flatMap, toArray)
    with a call_fn hook so SpryCode lambdas can be used as predicates/mappers.
    """

    def __init__(self, items: list, call_fn: "Any | None" = None) -> None:
        self._items = list(items)
        self._index = 0
        self._call_fn = call_fn  # Interpreter._call_function partial for lambdas

    def _call(self, fn: Any, args: list) -> Any:
        if self._call_fn is not None:
            return self._call_fn(fn, args, None)
        if callable(fn):
            return fn(*args)
        return fn

    def next(self) -> dict:
        if self._index < len(self._items):
            val = self._items[self._index]
            self._index += 1
            return {"value": val, "done": False}
        return {"value": None, "done": True}

    def toArray(self) -> list:
        """Return remaining items as a plain list (alias for toList)."""
        return list(self._items[self._index:])

    def toList(self) -> list:
        return list(self._items[self._index:])

    def filter(self, fn: Any) -> "SpryIterator":
        """Return a new SpryIterator keeping only items where fn(item) is truthy."""
        result = []
        for item in self._items[self._index:]:
            if self._call(fn, [item]):
                result.append(item)
        return SpryIterator(result, self._call_fn)

    def map(self, fn: Any) -> "SpryIterator":
        """Return a new SpryIterator with fn applied to each item."""
        result = [self._call(fn, [item]) for item in self._items[self._index:]]
        return SpryIterator(result, self._call_fn)

    def take(self, n: Any) -> "SpryIterator":
        """Return a new SpryIterator with at most n items."""
        return SpryIterator(self._items[self._index:self._index + int(n)], self._call_fn)

    def drop(self, n: Any) -> "SpryIterator":
        """Return a new SpryIterator skipping the first n items."""
        return SpryIterator(self._items[self._index + int(n):], self._call_fn)

    def flatMap(self, fn: Any) -> "SpryIterator":
        """Return a new SpryIterator with fn applied and results flattened one level."""
        result: list = []
        for item in self._items[self._index:]:
            val = self._call(fn, [item])
            if isinstance(val, (list, SpryIterator)):
                result.extend(val)
            else:
                result.append(val)
        return SpryIterator(result, self._call_fn)

    def forEach(self, fn: Any) -> None:
        """Call fn(item) for each remaining item."""
        for item in self._items[self._index:]:
            self._call(fn, [item])

    def reduce(self, fn: Any, initial: Any = _MISSING) -> Any:
        """Reduce remaining items with fn(acc, item)."""
        items = self._items[self._index:]
        if not items:
            if initial is _MISSING:
                raise TypeError("reduce of empty iterator with no initial value")
            return initial
        acc = initial if initial is not _MISSING else items[0]
        start = 0 if initial is not _MISSING else 1
        for item in items[start:]:
            acc = self._call(fn, [acc, item])
        return acc

    def some(self, fn: Any) -> bool:
        """Return True if fn(item) is truthy for any remaining item."""
        for item in self._items[self._index:]:
            if self._call(fn, [item]):
                return True
        return False

    def every(self, fn: Any) -> bool:
        """Return True if fn(item) is truthy for all remaining items."""
        for item in self._items[self._index:]:
            if not self._call(fn, [item]):
                return False
        return True

    def find(self, fn: Any) -> Any:
        """Return first item where fn(item) is truthy, or None."""
        for item in self._items[self._index:]:
            if self._call(fn, [item]):
                return item
        return None

    def __iter__(self):
        return iter(self._items)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SpryIterator):
            return self._items == other._items
        if isinstance(other, list):
            return self._items == other
        return NotImplemented

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: Any) -> Any:
        return self._items[index]

    def __repr__(self) -> str:
        return f"Iterator({self._items!r})"


class _GeneratorThrowSentinel:
    """Sentinel sent via the generator's send queue to inject an error."""
    def __init__(self, error: Any) -> None:
        self.error = error


class _GeneratorReturnSentinel:
    """Sentinel sent via the generator's send queue to force-return."""
    def __init__(self, value: Any) -> None:
        self.value = value


class SpryGenerator:
    """Runtime generator object produced by calling a generator function (fn*).

    Lazily executes the function body, pausing at each ``yield`` and resuming
    on the next ``next()`` / iteration call.

    Supports the send protocol: ``next(value)`` passes a value back into the
    generator which becomes the result of the ``yield`` expression.
    """

    def __init__(self, fn: "SpryFunction", args: list[Any], interp: "Interpreter") -> None:
        import threading
        import queue as _q

        self._fn = fn
        self._args = args
        self._interp = interp
        self._done = False
        self._is_async = getattr(fn, "is_async", False)

        # Coroutine protocol using threads + queues
        self._yield_q: "_q.Queue[tuple[str, Any]]" = _q.Queue()
        self._send_q: "_q.Queue[Any]" = _q.Queue()
        self._thread: "threading.Thread | None" = None
        self._started = False
        # Cache for list()-like materialisation (for-in iteration)
        self._collected: list[Any] | None = None

    def _start_thread(self) -> None:
        """Start the generator thread on first next() call."""
        import threading
        self._started = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        """Body of the generator thread — runs in a dedicated thread."""
        yield_q = self._yield_q
        send_q = self._send_q
        interp = self._interp

        def _yield_hook(value: Any) -> Any:
            yield_q.put(("yield", value))
            sent = send_q.get()
            if isinstance(sent, _GeneratorThrowSentinel):
                # Wrap in SpryUserError so the generator's try/catch can handle it
                raise SpryUserError(sent.error)
            if isinstance(sent, _GeneratorReturnSentinel):
                # Force-return: raise a special ReturnSignal so finally blocks run
                raise ReturnSignal(sent.value)
            return sent  # becomes the result of the yield expression

        # Install thread-local hook so _eval intercepts yield in THIS thread only
        interp._tl.yield_hook = _yield_hook  # type: ignore[attr-defined]

        env = self._fn.closure.child()
        normal_params = [p for p in self._fn.params if not p[0].startswith("__destruct__:")]
        for i, (pname, _) in enumerate(normal_params):
            if i < len(self._args):
                arg_val = self._args[i]
            elif pname in self._fn.defaults:
                arg_val = interp._eval(self._fn.defaults[pname], env)
            else:
                arg_val = None
            env.define(pname, arg_val, mutable=True)

        try:
            try:
                interp._exec_block(self._fn.body, env)
            except ReturnSignal as rs:
                yield_q.put(("return", rs.value))
                return
        except Exception as exc:
            yield_q.put(("error", exc))
            return
        finally:
            interp._tl.yield_hook = None  # type: ignore[attr-defined]
        yield_q.put(("done", None))

    def next(self, send_val: Any = None) -> Any:
        """JS-style iterator: returns {value, done}."""
        if self._done:
            return {"value": None, "done": True}

        if not self._started:
            self._start_thread()
            # First call: wait for first yield without sending a value
        else:
            self._send_q.put(send_val)

        try:
            kind, val = self._yield_q.get(timeout=10)
        except Exception:
            self._done = True
            return {"value": None, "done": True}

        if kind == "yield":
            return {"value": val, "done": False}
        if kind in ("done", "return"):
            self._done = True
            return {"value": val if kind == "return" else None, "done": True}
        if kind == "error":
            self._done = True
            raise val
        self._done = True
        return {"value": None, "done": True}

    def _materialise(self) -> list[Any]:
        """Materialise all yielded values for for-in iteration."""
        if self._collected is not None:
            return self._collected
        result: list[Any] = []
        while True:
            item = self.next()
            if not isinstance(item, dict) or item.get("done", False):
                break
            result.append(item["value"])
        self._collected = result
        return result

    def __iter__(self) -> "Any":
        return iter(self._materialise())

    def spry_return(self, val: Any = None) -> Any:
        """Force-complete the generator, running any finally blocks."""
        if self._done:
            return {"value": val, "done": True}
        if not self._started:
            # Generator never started — just mark done
            self._done = True
            return {"value": val, "done": True}
        # Send a return sentinel so the generator thread runs finally blocks
        self._send_q.put(_GeneratorReturnSentinel(val))
        try:
            kind, _v = self._yield_q.get(timeout=10)
        except Exception:
            pass
        self._done = True
        return {"value": val, "done": True}

    def spry_throw(self, error: Any = None) -> Any:
        """Throw an error into the generator at the current yield point.

        If the generator's try/catch handles the error, the next yielded value
        is returned as {value, done: False}.  If the error propagates out of the
        generator entirely, it is re-raised to the caller.
        """
        if self._done:
            raise error if error is not None else SpryRuntimeError("Generator already finished")
        if not self._started:
            # Generator hasn't started yet — just raise immediately
            self._done = True
            if error is not None:
                raise error
            raise SpryRuntimeError("Generator error")
        # Inject the error via the send queue (wrapped in sentinel)
        self._send_q.put(_GeneratorThrowSentinel(error))
        try:
            kind, val = self._yield_q.get(timeout=10)
        except Exception:
            self._done = True
            return {"value": None, "done": True}
        if kind == "yield":
            return {"value": val, "done": False}
        if kind in ("done", "return"):
            self._done = True
            return {"value": val if kind == "return" else None, "done": True}
        if kind == "error":
            self._done = True
            raise val
        self._done = True
        return {"value": None, "done": True}

    def __repr__(self) -> str:
        return f"<generator {self._fn.name}>"


# ---------------------------------------------------------------------------
# Regex pattern helper
# ---------------------------------------------------------------------------


def _parse_regex_pattern(pattern: str) -> tuple[str, int]:
    """Parse a regex pattern string, stripping optional /pattern/flags delimiters.

    Supports:
      - Plain string:   "\\d+"
      - JS-style:       "/\\d+/gi"

    Returns (pattern, flags, is_global) where flags is a Python re flags integer.
    """
    import re as _re
    if isinstance(pattern, str) and pattern.startswith("/"):
        # Extract /pattern/flags
        last_slash = pattern.rfind("/")
        if last_slash > 0:
            inner = pattern[1:last_slash]
            flag_str = pattern[last_slash + 1:]
            flags = 0
            if "i" in flag_str:
                flags |= _re.IGNORECASE
            if "m" in flag_str:
                flags |= _re.MULTILINE
            if "s" in flag_str:
                flags |= _re.DOTALL
            is_global = "g" in flag_str
            return _js_regex_to_python(inner), flags, is_global
    return _js_regex_to_python(pattern), 0, False


def _js_regex_to_python(pattern: str) -> str:
    """Translate JS regex syntax to Python regex syntax.

    Currently handles:
      - Named capture groups: (?<name>...) → (?P<name>...)
    """
    import re as _re
    # JS named capture: (?<name>...) → Python (?P<name>...)
    # But not negative lookahead (?<!...) or (?<= ...)
    result = _re.sub(r'\(\?<([A-Za-z_][A-Za-z0-9_]*)>', r'(?P<\1>', pattern)
    return result


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------


class Interpreter:
    """Evaluates a SpryCode AST."""

    def __init__(
        self,
        logger: SpryLogger | None = None,
        permissions: PermissionSet | None = None,
        secret_manager: SecretManager | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.logger = logger or SpryLogger()
        self.permissions = permissions or PermissionSet()
        self.secrets = secret_manager or SecretManager()
        self.audit = audit_logger or AuditLogger()
        self.fs = FilesystemOps(self.permissions)
        self._sql = SqlAdapter()
        self.globals = self._build_globals()
        # Record built-in global names so debug output can distinguish them from user variables.
        self._builtin_keys: frozenset[str] = frozenset(self.globals._vars.keys())
        self._app_name: str = ""
        self._app_version: str = ""
        # Debugger hook: callable(env) invoked when `debugger;` statement is reached.
        # Set by the REPL or external tooling to enable interactive debugging.
        self._debugger_hook: "Any" = None
        # Thread-local yield handler for generator coroutines
        import threading
        self._tl = threading.local()

    def _build_globals(self) -> Environment:
        env = Environment()
        # Built-in functions
        env.define("uuid", lambda: _builtin_uuid())
        env.define("now", lambda: _builtin_now())
        env.define("today", lambda: _builtin_today())
        env.define("checksum", lambda path, alg="sha256": _builtin_checksum(path, alg))
        env.define("hash", lambda text, alg="sha256": _builtin_hash_text(text, alg))
        env.define("encode", lambda fmt, val=None: self._encode(fmt, val))
        env.define("decode", lambda fmt, val: self._decode(fmt, val))
        env.define("parse", lambda fmt, val: self._parse(fmt, val))

        # Math
        env.define("abs", abs)
        env.define("min", min)
        env.define("max", max)
        env.define("round", round)
        env.define("floor", math.floor)
        env.define("ceil", math.ceil)
        env.define("sqrt", math.sqrt)
        env.define("pow", pow)
        # math namespace object
        _math_inst = _MathHelper()
        env.define("math", _math_inst)
        env.define("Math", _math_inst)  # uppercase JS-compatible alias

        # stats namespace object
        env.define("stats", _StatsHelper())

        # JSON namespace object
        env.define("json", _JsonHelper())

        # date namespace object
        env.define("date", _DateHelper())

        # random number
        env.define("random", lambda: __import__("random").random())
        env.define("randint", lambda a, b: __import__("random").randint(int(a), int(b)))

        # print (alias for log info)
        env.define("print", lambda *args: print(*[self._builtin_str(a) for a in args]))
        env.define("len", len)
        env.define("str", self._builtin_str)
        env.define("int", int)
        env.define("float", float)
        env.define("bool", bool)
        env.define("list", list)
        env.define("type", self._spry_type)

        # Sequence builtins
        env.define("range", lambda *args: list(range(*[int(a) for a in args])))
        env.define("sorted", lambda lst, **kw: sorted(lst))
        env.define("reversed", lambda lst: list(reversed(lst)))
        env.define("sum", sum)
        env.define("any", any)
        env.define("all", all)
        env.define("zip", lambda *iterables: [list(t) for t in zip(*iterables)])
        env.define("enumerate", lambda lst, start=0: [[i, v] for i, v in enumerate(lst, start)])
        env.define("flatten", lambda lst: [x for sub in lst for x in (sub if isinstance(sub, list) else [sub])])
        env.define("unique", lambda lst: list(dict.fromkeys(lst)))
        env.define("keys", lambda d: list(d.keys()) if isinstance(d, dict) else [])
        env.define("values", lambda d: list(d.values()) if isinstance(d, dict) else [])
        env.define("entries", lambda d: [[k, v] for k, v in d.items()] if isinstance(d, dict) else [])

        # Dict/Object helpers
        def _from_entries(entries: Any) -> dict:
            if isinstance(entries, list):
                return {str(k): v for k, v in entries}
            if isinstance(entries, SpryMap):
                return {str(k): v for k, v in entries._data.items()}
            return {}
        env.define("fromEntries", _from_entries)
        env.define("merge", lambda *dicts: {k: v for d in dicts if isinstance(d, dict) for k, v in d.items()})

        # Parsing helpers (global convenience functions)
        def _js_parse_int(s: Any, base: Any = None) -> Any:
            import re as _re
            s_str = str(s).strip()
            if not s_str:
                return float("nan")
            # Hex prefix
            if base is None or int(base) == 16:
                if s_str.startswith("0x") or s_str.startswith("0X"):
                    m = _re.match(r"0[xX]([0-9a-fA-F]+)", s_str)
                    return int(m.group(1), 16) if m else float("nan")
            # Octal prefix (0o or 0 followed by digits)
            if base is None or int(base) == 8:
                if s_str.startswith("0o") or s_str.startswith("0O"):
                    m = _re.match(r"0[oO]([0-7]+)", s_str)
                    return int(m.group(1), 8) if m else float("nan")
            # Binary prefix
            if base is None or int(base) == 2:
                if s_str.startswith("0b") or s_str.startswith("0B"):
                    m = _re.match(r"0[bB]([01]+)", s_str)
                    return int(m.group(1), 2) if m else float("nan")
            actual_base = 10 if base is None else int(base)
            # Match leading digits (and sign)
            if actual_base == 10:
                m = _re.match(r"[+-]?\d+", s_str)
            elif actual_base == 16:
                m = _re.match(r"[+-]?[0-9a-fA-F]+", s_str)
            elif actual_base == 2:
                m = _re.match(r"[+-]?[01]+", s_str)
            elif actual_base == 8:
                m = _re.match(r"[+-]?[0-7]+", s_str)
            else:
                m = _re.match(r"[+-]?[0-9a-zA-Z]+", s_str)
            if not m:
                return float("nan")
            try:
                return int(m.group(0), actual_base)
            except ValueError:
                return float("nan")

        def _js_parse_float(s: Any) -> Any:
            import re as _re
            s_str = str(s).strip()
            if not s_str:
                return float("nan")
            m = _re.match(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", s_str)
            if not m:
                return float("nan")
            try:
                return float(m.group(0))
            except ValueError:
                return float("nan")

        def _is_nan_coercive(x: Any) -> bool:
            if isinstance(x, bool):
                return False
            if isinstance(x, (int, float)):
                return math.isnan(float(x))
            if isinstance(x, str):
                v = x.strip()
                if v == "":
                    return False  # empty string → 0 → not NaN
                try:
                    return math.isnan(float(v))
                except ValueError:
                    return True
            return False

        def _is_finite_coercive(x: Any) -> bool:
            if isinstance(x, bool):
                return True
            if x is None:
                return True  # null → 0 → finite
            if isinstance(x, (int, float)):
                return math.isfinite(float(x))
            if isinstance(x, str):
                try:
                    return math.isfinite(float(x))
                except ValueError:
                    return False
            return False

        env.define("parseInt", _js_parse_int)
        env.define("parseFloat", _js_parse_float)
        env.define("isNaN", _is_nan_coercive)
        env.define("isFinite", _is_finite_coercive)
        # URI encoding/decoding (JS-compat)
        import urllib.parse as _urllib_parse
        env.define("encodeURIComponent", lambda s: _urllib_parse.quote(str(s), safe=""))
        env.define("decodeURIComponent", lambda s: _urllib_parse.unquote(str(s)))
        # encodeURI preserves URI-safe characters
        _URI_SAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.!~*'();/?:@&=+$,#"
        env.define("encodeURI", lambda s: _urllib_parse.quote(str(s), safe=_URI_SAFE))
        env.define("decodeURI", lambda s: _urllib_parse.unquote(str(s)))

        # Constants
        env.define("ok", SPRY_OK)
        env.define("true", True)
        env.define("false", False)
        env.define("null", None)
        env.define("Infinity", float("inf"))
        env.define("NaN", float("nan"))
        env.define("undefined", SPRY_UNDEFINED)  # JS-compat undefined sentinel

        # Environment and formatting
        env.define("env", lambda key, default=None: os.environ.get(str(key), default))
        env.define("format", lambda template, *args: self._builtin_format(template, *args))

        # Global namespace objects (JS-style)
        env.define("JSON", _JsonNamespace(call_fn=self._call_value))
        _array_ns = _ArrayNamespace()
        _array_ns._interp = self
        env.define("Array", _array_ns)
        _object_ns = _ObjectNamespace(call_fn=self._call_value)
        self._object_ns = _object_ns
        env.define("Object", _object_ns)
        env.define("Number", _NumberNamespace())

        # Event bus
        env.define("events", _EventsHelper(self._call_value))

        # String global namespace
        _string_ns = _StringNamespace()
        _string_ns._interp = self
        env.define("String", _string_ns)

        # Map global namespace
        _map_ns = _MapNamespace()
        env.define("Map", _map_ns)

        # Symbol global
        env.define("Symbol", _SymbolNamespace())

        # Boolean callable converter
        env.define("Boolean", _BooleanCallable())

        # WeakRef global
        env.define("WeakRef", _WeakRefNamespace())

        # SprySet — proper Set type with set operations
        env.define("SprySet", _SprySetNamespace())

        # Iterator global — Iterator.from(iterable)
        env.define("Iterator", _IteratorNamespace(self))

        # Fetch API and related Web types
        env.define("Blob", _BlobNamespace())
        env.define("File", _FileNamespace())
        env.define("Headers", _HeadersNamespace())
        env.define("FormData", _FormDataNamespace())
        env.define("Request", _RequestNamespace())
        env.define("Response", _ResponseNamespace())
        env.define("fetch", _make_fetch_fn(self.permissions))

        # EventTarget / Event / CustomEvent
        env.define("EventTarget", _EventTargetNamespace(self._call_value))
        env.define("Event", _EventNamespace())
        env.define("CustomEvent", _CustomEventNamespace())
        env.define("MessageEvent", _EventNamespace())  # alias for basic use

        # Web Streams API (WritableStream doesn't need interpreter ref)
        env.define("WritableStream", _WritableStreamNamespace())
        env.define("CompressionStream", _CompressionStreamNamespace())
        env.define("DecompressionStream", _DecompressionStreamNamespace())

        # Messaging
        env.define("BroadcastChannel", _BroadcastChannelNamespace(self._call_value))
        env.define("MessageChannel", _MessageChannelNamespace(self._call_value))

        # Microservice primitives (Phase 110)
        env.define("Queue", _SpryQueueNamespace())
        env.define("Channel", _SpryChannelNamespace())
        env.define("CircuitBreaker", _SpryCircuitBreakerNamespace(self._call_value))
        env.define("throttle", self._builtin_throttle)
        env.define("debounce", self._builtin_debounce)

        # navigator
        env.define("navigator", _NavigatorNamespace())

        # ReadableStream/WritableStream/TransformStream need interpreter ref for callbacks
        env.define("ReadableStream", _ReadableStreamNamespace(self._call_value))
        env.define("TransformStream", _TransformStreamNamespace(self._call_value))

        # Promise namespace
        env.define("Promise", _PromiseNamespace())

        # Error types
        for _ename in ("Error", "TypeError", "RangeError", "SyntaxError",
                       "ReferenceError", "EvalError", "URIError"):
            env.define(_ename, _ErrorNamespace(_ename))
        env.define("AggregateError", _AggregateErrorNamespace())
        env.define("SuppressedError", _SuppressedErrorNamespace())

        # Date namespace
        env.define("Date", _DateNamespace())

        # console namespace
        env.define("console", _ConsoleNamespace())

        # crypto namespace
        env.define("crypto", _CryptoNamespace())

        # WeakMap global
        env.define("WeakMap", _WeakMapNamespace())

        # WeakSet global
        env.define("WeakSet", _WeakSetNamespace())

        # Intl namespace
        env.define("Intl", _IntlNamespace())

        # FinalizationRegistry
        env.define("FinalizationRegistry", _FinalizationRegistryNamespace())

        # Proxy
        env.define("Proxy", _ProxyNamespace(self))

        # eval — evaluate SpryCode source string
        def _spry_eval(src: Any) -> Any:
            from .lexer import Lexer as _Lexer
            from .parser import Parser as _Parser
            _tokens = _Lexer(str(src)).tokenize()
            _prog = _Parser(_tokens).parse()
            _result = None
            for stmt in _prog.body:
                _result = self._eval(stmt, env)
            return _result
        env.define("eval", _spry_eval)

        # Reflect namespace
        env.define("Reflect", _ReflectNamespace(self))

        # globalThis — reference to the interpreter's global env dict
        env.define("globalThis", {"__type__": "GlobalThis", "undefined": SPRY_UNDEFINED})

        # structuredClone — deep clone that handles SpryMap, SprySet, SpryDate, dict, list
        def _structured_clone(val: Any) -> Any:
            if isinstance(val, SpryMap):
                new_map = SpryMap()
                for k, v in val._data.items():
                    new_map.spry_set(_structured_clone(k), _structured_clone(v))
                return new_map
            if isinstance(val, SprySet):
                new_set = SprySet()
                for item in val._data:
                    new_set.add(_structured_clone(item))
                return new_set
            if isinstance(val, SpryDate):
                import datetime as _datetime_mod
                new_date = object.__new__(SpryDate)
                new_date._dt = val._dt.replace()  # replace() with no args copies all datetime fields
                return new_date
            if isinstance(val, dict):
                return {k: _structured_clone(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_structured_clone(item) for item in val]
            # Primitives (int, float, str, bool, None) are immutable — return as-is
            return val
        env.define("structuredClone", _structured_clone)

        # queueMicrotask — executes fn immediately (synchronous SpryCode model)
        env.define("queueMicrotask", lambda fn: fn() if callable(fn) else None)

        # Set — now a proper SprySet namespace supporting Set.new([...])
        env.define("Set", _SprySetNamespace())

        # setTimeout / clearTimeout / setInterval / clearInterval — sync stubs
        _timer_counter = [0]
        def _set_timeout(fn: Any, delay: Any = 0) -> int:
            _timer_counter[0] += 1
            # Execute immediately in synchronous SpryCode model
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
            return _timer_counter[0]
        def _clear_timeout(timer_id: Any = None) -> None:
            pass  # no-op in synchronous model
        def _set_interval(fn: Any, delay: Any = 0) -> int:
            _timer_counter[0] += 1
            return _timer_counter[0]  # no-op stub
        env.define("setTimeout", _set_timeout)
        env.define("clearTimeout", _clear_timeout)
        env.define("setInterval", _set_interval)
        env.define("clearInterval", _clear_timeout)

        # performance namespace
        env.define("performance", _PerformanceNamespace())

        # URL global
        env.define("URL", _URLNamespace())
        env.define("URLSearchParams", _URLSearchParamsNamespace())

        # TextEncoder / TextDecoder
        env.define("TextEncoder", _TextEncoderNamespace())
        env.define("TextDecoder", _TextDecoderNamespace())

        # AbortController / AbortSignal
        env.define("AbortController", _AbortControllerNamespace())
        env.define("AbortSignal", _AbortSignalNamespace())

        # RegExp global constructor
        env.define("RegExp", _RegExpNamespace())

        # ArrayBuffer and TypedArrays
        env.define("ArrayBuffer", _ArrayBufferNamespace())
        env.define("SharedArrayBuffer", _SharedArrayBufferNamespace())
        env.define("DataView", _DataViewNamespace())
        env.define("Atomics", _AtomicsNamespace())
        env.define("Int8Array", _TypedArrayNamespace("Int8Array", 1))
        env.define("Uint8Array", _TypedArrayNamespace("Uint8Array", 1))
        env.define("Uint8ClampedArray", _Uint8ClampedArrayNamespace())
        env.define("Int16Array", _TypedArrayNamespace("Int16Array", 2))
        env.define("Uint16Array", _TypedArrayNamespace("Uint16Array", 2))
        env.define("Int32Array", _TypedArrayNamespace("Int32Array", 4))
        env.define("Uint32Array", _TypedArrayNamespace("Uint32Array", 4))
        env.define("Float32Array", _TypedArrayNamespace("Float32Array", 4))
        env.define("Float64Array", _TypedArrayNamespace("Float64Array", 8))
        env.define("BigInt64Array", _TypedArrayNamespace("BigInt64Array", 8))
        env.define("BigUint64Array", _TypedArrayNamespace("BigUint64Array", 8))

        # Money helper
        env.define("money", _MoneyHelper())

        # HTTP helper
        env.define("http", _HttpHelper(self.permissions))

        # SQL adapter
        env.define("sql", self._sql)

        # Audit logger
        env.define("audit", self.audit)

        # btoa / atob (Phase 55)
        import base64 as _base64_mod
        def _btoa(s: Any) -> str:
            return _base64_mod.b64encode(str(s).encode("latin-1")).decode("ascii")
        def _atob(s: Any) -> str:
            return _base64_mod.b64decode(str(s)).decode("latin-1")
        env.define("btoa", _btoa)
        env.define("atob", _atob)

        # BigInt constructor (Phase 63)
        env.define("BigInt", _BigIntNamespace())

        return env

    def _eval_fstring(self, template: str, env: "Environment") -> str:
        """Evaluate an f-string template by substituting {expr} with evaluated values.

        Uses a depth-aware scan instead of a simple regex so that nested braces
        and inner backtick template literals inside ``{...}`` expressions are
        handled correctly.
        """
        result = ""
        i = 0
        n = len(template)
        while i < n:
            if template[i] == "{":
                # Depth-tracking scan for the matching closing }
                i += 1
                depth = 1
                expr_start = i
                while i < n and depth > 0:
                    c = template[i]
                    if c == "{":
                        depth += 1
                        i += 1
                    elif c == "}":
                        depth -= 1
                        i += 1
                    elif c == "`":
                        # Inner backtick string — skip until matching close backtick,
                        # tracking its own ${...} depth so inner } don't confuse us.
                        i += 1
                        while i < n:
                            bc = template[i]
                            if bc == "\\":
                                i += 2  # skip escape + escaped char
                            elif bc == "`":
                                i += 1
                                break
                            elif bc == "$" and i + 1 < n and template[i + 1] == "{":
                                i += 2  # skip ${
                                inner_d = 1
                                while i < n and inner_d > 0:
                                    ic = template[i]
                                    if ic == "{":
                                        inner_d += 1
                                    elif ic == "}":
                                        inner_d -= 1
                                    i += 1
                            else:
                                i += 1
                    elif c in ("'", '"'):
                        quote = c
                        i += 1
                        while i < n:
                            sc = template[i]
                            if sc == "\\":
                                i += 2
                            elif sc == quote:
                                i += 1
                                break
                            else:
                                i += 1
                    else:
                        i += 1
                expr_src = template[expr_start:i - 1]  # exclude trailing }
                try:
                    from .lexer import Lexer as _Lexer
                    from .parser import Parser as _Parser
                    tokens = _Lexer(expr_src).tokenize()
                    prog = _Parser(tokens).parse()
                    # prog.body[0] is the expression statement
                    val = self._eval(prog.body[0], env)
                    result += self._builtin_str(val)
                except Exception as e:
                    result += f"{{{expr_src}}}"
            else:
                result += template[i]
                i += 1
        return result

    def _eval_tagged_template(self, node: "TaggedTemplateExpression", env: "Environment") -> Any:
        """Evaluate a tagged template literal: tag`hello ${expr} world`.

        Calls tag(strings, ...values) where strings is the list of raw string parts
        and values are the evaluated expressions.
        """
        tag_fn = self._eval(node.tag, env)

        def _parse_template(template: str) -> "tuple[list[str], list[Any]]":
            """Split template into string parts and expression sources."""
            parts: list[str] = []
            exprs: list[str] = []
            i = 0
            n = len(template)
            current_str = ""
            while i < n:
                if template[i] == "{":
                    i += 1
                    depth = 1
                    expr_start = i
                    while i < n and depth > 0:
                        c = template[i]
                        if c == "{":
                            depth += 1
                            i += 1
                        elif c == "}":
                            depth -= 1
                            i += 1
                        elif c == "`":
                            i += 1
                            while i < n:
                                bc = template[i]
                                if bc == "\\":
                                    i += 2
                                elif bc == "`":
                                    i += 1
                                    break
                                elif bc == "$" and i + 1 < n and template[i + 1] == "{":
                                    i += 2
                                    inner_d = 1
                                    while i < n and inner_d > 0:
                                        ic = template[i]
                                        if ic == "{":
                                            inner_d += 1
                                        elif ic == "}":
                                            inner_d -= 1
                                        i += 1
                                else:
                                    i += 1
                        else:
                            i += 1
                    parts.append(current_str)
                    current_str = ""
                    exprs.append(template[expr_start:i - 1])
                else:
                    current_str += template[i]
                    i += 1
            parts.append(current_str)
            return parts, exprs

        # Build cooked strings from the processed template (escape sequences resolved)
        cooked_template = node.template
        raw_template = node.raw_template if node.raw_template else node.template
        cooked_parts, expr_srcs = _parse_template(cooked_template)
        raw_parts, _ = _parse_template(raw_template)

        values: list[Any] = []
        for expr_src in expr_srcs:
            try:
                from .lexer import Lexer as _Lexer
                from .parser import Parser as _Parser
                _tokens = _Lexer(expr_src).tokenize()
                _prog = _Parser(_tokens).parse()
                val = self._eval(_prog.body[0], env)
                values.append(val)
            except Exception:
                values.append(None)

        strings = SpryTaggedStringList(cooked_parts, raw_parts)
        return self._call_value(tag_fn, [strings, *values])

    def _builtin_str(self, value: Any) -> str:
        """Convert any SpryCode value to a string."""
        if isinstance(value, _SpryUndefinedType):
            return "undefined"
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, dict):
            prim = self._dict_to_primitive(value, "string")
            if not isinstance(prim, dict):
                return self._builtin_str(prim)
        if isinstance(value, SpryInstance):
            # Prefer [Symbol.toPrimitive]("string") first
            sym_key = "Symbol('toPrimitive')"
            fn = value.fields.get(sym_key)
            if fn is None:
                for k, v in value.fields.items():
                    if isinstance(k, SprySymbol) and k.description == "toPrimitive":
                        fn = v
                        break
            if fn is not None:
                if isinstance(fn, (SpryFunction, BoundMethod)):
                    try:
                        bm = fn if isinstance(fn, BoundMethod) else BoundMethod(instance=value, fn=fn)
                        result = self._call_bound_method(bm, ["string"], None)
                        if not isinstance(result, SpryInstance):
                            return str(result)
                    except Exception:
                        pass
            # Then a user-defined toString() method
            if "toString" in value.fields:
                v = value.fields["toString"]
                if isinstance(v, (SpryFunction, BoundMethod)):
                    try:
                        bm = v if isinstance(v, BoundMethod) else BoundMethod(instance=value, fn=v)
                        return str(self._call_bound_method(bm, [], None))
                    except Exception:
                        pass
        if isinstance(value, SpryResult):
            if value.ok:
                return str(value.value) if value.value is not None else ""
            return value.error
        if isinstance(value, SprySecret):
            return str(value)
        if isinstance(value, SpryMoney):
            return str(value)
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        return str(value)

    def _to_primitive(self, value: Any, hint: str = "default") -> Any:
        """Coerce a SpryInstance to a primitive value (JS ToPrimitive semantics).

        1. If the instance has a ``[Symbol.toPrimitive]`` method, call it with ``hint``.
        2. Otherwise, for ``"string"`` hint try ``toString()`` then ``valueOf()``;
           for ``"number"``/``"default"`` try ``valueOf()`` then ``toString()``.
        Returns the original value unchanged if no coercion method is found.
        """
        if not isinstance(value, SpryInstance):
            return value
        # Check [Symbol.toPrimitive]
        sym_key = "Symbol('toPrimitive')"
        fn = value.fields.get(sym_key)
        if fn is None:
            for k, v in value.fields.items():
                if isinstance(k, SprySymbol) and k.description == "toPrimitive":
                    fn = v
                    break
        if fn is not None:
            if isinstance(fn, (SpryFunction, BoundMethod)):
                try:
                    bm = fn if isinstance(fn, BoundMethod) else BoundMethod(instance=value, fn=fn)
                    return self._call_bound_method(bm, [hint], None)
                except Exception:
                    pass
        if hint == "string":
            # Try toString first, then valueOf
            for mname in ("toString", "valueOf"):
                if mname in value.fields:
                    fn = value.fields[mname]
                    if isinstance(fn, (SpryFunction, BoundMethod)):
                        try:
                            bm = fn if isinstance(fn, BoundMethod) else BoundMethod(instance=value, fn=fn)
                            result = self._call_bound_method(bm, [], None)
                            if not isinstance(result, SpryInstance):
                                return result
                        except Exception:
                            pass
        else:
            # "number" / "default": try valueOf first, then toString
            for mname in ("valueOf", "toString"):
                if mname in value.fields:
                    fn = value.fields[mname]
                    if isinstance(fn, (SpryFunction, BoundMethod)):
                        try:
                            bm = fn if isinstance(fn, BoundMethod) else BoundMethod(instance=value, fn=fn)
                            result = self._call_bound_method(bm, [], None)
                            if not isinstance(result, SpryInstance):
                                return result
                        except Exception:
                            pass
        return value

    def _dict_to_primitive(self, d: dict, hint: str) -> Any:
        """Coerce a plain dict to a primitive using Symbol.toPrimitive if available."""
        sym_key = "Symbol('toPrimitive')"
        fn = d.get(sym_key)
        if fn is None:
            for k, v in d.items():
                if isinstance(k, SprySymbol) and k.description == "toPrimitive":
                    fn = v
                    break
        if fn is not None and isinstance(fn, SpryFunction):
            try:
                return self._call_dict_bound_method(fn, d, [hint], None)
            except Exception:
                pass
        return d

    def _to_numeric(self, value: Any) -> Any:
        """Coerce *value* to a numeric primitive (JS ToNumeric-lite).

        For SpryInstance, tries ``Symbol.toPrimitive("number")``, then
        ``valueOf()``, then ``toString()`` (parsed as a number).
        Falls back to ``float("nan")`` if nothing works.
        """
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, bool):
            return 1 if value else 0
        if value is None:
            return 0
        if isinstance(value, _SpryUndefinedType):
            return float("nan")
        if isinstance(value, str):
            v = value.strip()
            if v == "":
                return 0
            try:
                return int(v)
            except ValueError:
                try:
                    return float(v)
                except ValueError:
                    return float("nan")
        if isinstance(value, SpryInstance):
            prim = self._to_primitive(value, "number")
            if not isinstance(prim, SpryInstance):
                return self._to_numeric(prim)
        if isinstance(value, dict):
            prim = self._dict_to_primitive(value, "number")
            if not isinstance(prim, dict):
                return self._to_numeric(prim)
        return float("nan")

    @staticmethod
    def _builtin_format(template: str, *args: Any) -> str:
        """String formatting — supports both Python % style (format('%05d', 42))
        and positional {} style (format('Hello {}', name))."""
        try:
            # Detect printf/% style: template contains %d, %s, %f, %0Nd etc.
            import re as _re
            if _re.search(r"%[-+0 #]*\d*\.?\d*[diouxXeEfFgGcsr%]", template):
                # Printf-style
                if len(args) == 1:
                    return template % args[0]
                return template % args
            # Positional {} style
            return template.format(*args)
        except (IndexError, KeyError, ValueError, TypeError):
            return template

    def _builtin_throttle(self, fn: Any, interval_ms: Any = 0) -> SpryThrottledFn:
        """throttle(fn, intervalMs) — wraps fn so it fires at most once per interval."""
        return SpryThrottledFn(fn, float(interval_ms or 0), call_fn=self._call_value)

    def _builtin_debounce(self, fn: Any, delay_ms: Any = 0) -> SpryDebouncedFn:
        """debounce(fn, delayMs) — wraps fn so it fires only after delay of silence."""
        return SpryDebouncedFn(fn, float(delay_ms or 0), call_fn=self._call_value)

    def _encode(self, fmt: str, val: Any = None) -> Any:
        if fmt in ("json",):
            return _builtin_encode_json(val)
        if fmt in ("base64",):
            return _builtin_encode_base64(str(val) if val is not None else "")
        if fmt in ("yaml",):
            return _builtin_encode_yaml(val)
        return str(val) if val is not None else ""

    def _decode(self, fmt: str, val: str) -> Any:
        if fmt in ("base64",):
            return _builtin_decode_base64(val)
        return val

    def _parse(self, fmt: str, val: str) -> Any:
        if fmt in ("json",):
            return _builtin_parse_json(val)
        if fmt in ("csv",):
            return _builtin_parse_csv(val)
        if fmt in ("yaml",):
            return _builtin_parse_yaml(val)
        return val

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, program: Program) -> Any:
        """Execute a full program. If the program defines a 'main' task but has
        no other executable top-level statements, auto-run the 'main' task."""
        # Check whether there are any executable statements (non-declaration, non-app)
        executable = [
            s for s in program.body
            if not isinstance(s, (AppDeclaration, TaskDeclaration, FunctionDeclaration,
                                  ConnectorDeclaration, AdapterDeclaration,
                                  AllowStatement, DenyStatement,
                                  PrivateDataDeclaration, SensitiveDataDeclaration,
                                  ImportStatement,
                                  UseStatement))
        ]
        result = self._exec_block_stmts(program.body, self.globals)
        # Auto-run 'main' task if nothing executable was at the top level
        if not executable and self.globals.has("main"):
            main_val = self.globals.get("main")
            if isinstance(main_val, SpryTask):
                result = self._call_task(main_val)
        return result

    def run_task(self, program: Program, task_name: str) -> Any:
        """Execute a named task from the program."""
        # First pass: register all tasks and functions
        self._exec_block_stmts(program.body, self.globals, register_only=True)
        # Now run the task
        task = self.globals.get(task_name)
        if not isinstance(task, SpryTask):
            raise SpryRuntimeError(f"Task {task_name!r} not found")
        return self._call_task(task)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _exec_block_stmts(
        self,
        stmts: list[Node],
        env: Environment,
        register_only: bool = False,
    ) -> Any:
        result = None
        for stmt in stmts:
            if register_only:
                # Only register declarations (tasks, functions, connectors, imports)
                if isinstance(stmt, (TaskDeclaration, FunctionDeclaration, ConnectorDeclaration,
                                     ImportStatement)):
                    self._exec(stmt, env)
            else:
                result = self._exec(stmt, env)
        return result

    def _exec_block(self, block: Block, env: Environment) -> Any:
        result = None
        disposables: list[tuple[str, Any]] = []
        try:
            for stmt in block.body:
                if isinstance(stmt, UsingDeclaration):
                    value = self._eval(stmt.value, env) if stmt.value is not None else None
                    env.define(stmt.name, value, mutable=False)
                    disposables.append((stmt.name, value))
                    result = None
                else:
                    result = self._exec(stmt, env)
        finally:
            # Dispose resources in LIFO order (even on exception)
            for _name, resource in reversed(disposables):
                if resource is None:
                    continue
                dispose_fn = None
                if isinstance(resource, SpryInstance):
                    dispose_fn = (
                        resource.fields.get("[Symbol.dispose]")
                        or resource.fields.get("Symbol('dispose')")
                        or resource.fields.get("dispose")
                    )
                    if dispose_fn is None:
                        # Check for SprySymbol key with description "dispose"
                        for k, v in resource.fields.items():
                            if isinstance(k, SprySymbol) and k.description == "dispose":
                                dispose_fn = v
                                break
                    if isinstance(dispose_fn, SpryFunction):
                        bm = BoundMethod(instance=resource, fn=dispose_fn)
                        try:
                            self._call_bound_method(bm, [], block)
                        except Exception:
                            pass
                        continue
                elif isinstance(resource, dict):
                    dispose_fn = (
                        resource.get("[Symbol.dispose]")
                        or resource.get("Symbol('dispose')")
                        or resource.get("dispose")
                    )
                    if dispose_fn is None:
                        for k, v in resource.items():
                            if isinstance(k, SprySymbol) and k.description == "dispose":
                                dispose_fn = v
                                break
                if dispose_fn is None:
                    continue
                if callable(dispose_fn):
                    try:
                        dispose_fn()
                    except Exception:
                        pass
                else:
                    try:
                        self._call_function(dispose_fn, [], block)
                    except Exception:
                        pass
        return result

    def _exec(self, node: Node, env: Environment) -> Any:  # noqa: C901
        if isinstance(node, Program):
            return self._exec_block_stmts(node.body, env)

        if isinstance(node, Block):
            return self._exec_block(node, env.child())

        if isinstance(node, DeclarationList):
            # Multiple declarations from `var a=1, b=2` — execute in CURRENT env (no new scope)
            for stmt in node.body:
                self._exec(stmt, env)
            return None

        if isinstance(node, AppDeclaration):
            self._app_name = node.name
            self._app_version = node.version
            return None

        if isinstance(node, LetDeclaration):
            value = self._eval(node.value, env) if node.value is not None else SPRY_UNDEFINED
            if isinstance(value, SpryFunction) and not value.name:
                value.name = node.name
            elif isinstance(value, (SpryLambda, SpryMultiLambda)) and not value.name:
                value.name = node.name
            env.define(node.name, value, mutable=not node.is_const)
            return None

        if isinstance(node, VarDeclaration):
            value = self._eval(node.value, env) if node.value is not None else SPRY_UNDEFINED
            if isinstance(value, SpryFunction) and not value.name:
                value.name = node.name
            elif isinstance(value, (SpryLambda, SpryMultiLambda)) and not value.name:
                value.name = node.name
            env.define(node.name, value, mutable=True)
            return None

        if isinstance(node, UsingDeclaration):
            value = self._eval(node.value, env) if node.value is not None else None
            env.define(node.name, value, mutable=False)
            return None

        if isinstance(node, Assignment):
            value = self._eval(node.value, env) if node.value is not None else None
            env.set(node.name, value)
            return value

        if isinstance(node, MemberAssignment):
            obj = self._eval(node.object, env)
            value = self._eval(node.value, env)
            if isinstance(obj, SpryProxy):
                obj._spry_set_prop(node.property, value)
            elif hasattr(obj, "_spry_set_prop") and not isinstance(obj, (SpryInstance, dict, SpryClass, SpryFunction)):
                obj._spry_set_prop(node.property, value)
            elif isinstance(obj, SpryInstance):
                # Check for setter first
                setter_key = f"__setter__{node.property}"
                if setter_key in obj.fields:
                    setter_fn = obj.fields[setter_key]
                    if isinstance(setter_fn, SpryFunction):
                        bm = BoundMethod(instance=obj, fn=setter_fn)
                        self._call_bound_method(bm, [value], node)
                        return None
                obj.set(node.property, value)
            elif isinstance(obj, dict):
                # Check for frozen object — silently ignore writes (JS non-strict behavior)
                if id(obj) in self._object_ns._frozen_ids:
                    return None
                # Check for setter
                setter_key = f"__setter__{node.property}"
                if setter_key in obj:
                    setter_fn = obj[setter_key]
                    if isinstance(setter_fn, SpryFunction):
                        self._call_dict_bound_method(setter_fn, obj, [value], node)
                        return None
                    elif isinstance(setter_fn, (SpryLambda, SpryMultiLambda, BoundMethod)):
                        self._call_value(setter_fn, [value])
                        return None
                    elif callable(setter_fn):
                        try:
                            setter_fn(value)
                        except Exception as e:
                            raise SpryRuntimeError(str(e), node)
                        return None
                obj[node.property] = value
            elif isinstance(obj, SpryFunction) and node.property == "prototype":
                obj._prototype = value
            elif isinstance(obj, SpryClass):
                obj._static_fields[node.property] = value
            elif hasattr(obj, "__setattr__") and not isinstance(obj, type):
                # Namespace objects with custom __setattr__ (e.g., _ErrorNamespace)
                try:
                    setattr(obj, node.property, value)
                except (AttributeError, TypeError) as e:
                    raise SpryRuntimeError(
                        f"Cannot assign property {node.property!r} on {type(obj).__name__}", node
                    )
            else:
                raise SpryRuntimeError(
                    f"Cannot assign property {node.property!r} on {type(obj).__name__}", node
                )
            return value

        if isinstance(node, CompoundMemberAssignment):
            obj = self._eval(node.object, env)
            rhs = self._eval(node.value, env)
            if isinstance(obj, SpryInstance):
                current = obj.fields.get(node.property)
            elif isinstance(obj, dict):
                current = obj.get(node.property)
            elif isinstance(obj, SpryClass):
                current = obj._static_fields.get(node.property)
                # Seed from AST if not yet stored
                if current is None and node.property not in obj._static_fields:
                    cls_env = obj.closure.child()
                    for stmt in obj.body.body:  # type: ignore[union-attr]
                        if isinstance(stmt, (LetDeclaration, VarDeclaration)) and stmt.name == node.property:
                            current = self._eval(stmt.value, cls_env) if stmt.value is not None else None
                            break
            else:
                raise SpryRuntimeError(
                    f"Cannot compound-assign property {node.property!r} on {type(obj).__name__}", node
                )
            if node.op == "+":
                # JS-style: if either operand is a string, coerce the other
                if isinstance(current, str) and not isinstance(rhs, str):
                    rhs = self._builtin_str(rhs)
                elif isinstance(rhs, str) and not isinstance(current, str):
                    current = self._builtin_str(current)
                new_val = current + rhs
            elif node.op == "-":
                new_val = current - rhs
            elif node.op == "*":
                new_val = current * rhs
            elif node.op == "/":
                if rhs == 0:
                    new_val = float("nan") if current == 0 else math.copysign(float("inf"), current)
                else:
                    new_val = current / rhs
            elif node.op == "&":
                new_val = int(current) & int(rhs)
            elif node.op == "|":
                new_val = int(current) | int(rhs)
            elif node.op == "^":
                new_val = int(current) ^ int(rhs)
            elif node.op == "<<":
                new_val = int(current) << int(rhs)
            elif node.op == ">>":
                new_val = int(current) >> int(rhs)
            elif node.op == "??":
                new_val = rhs if current is None else current
            elif node.op == "&&":
                new_val = rhs if self._truthy(current) else current
            elif node.op == "||":
                new_val = current if self._truthy(current) else rhs
            else:
                raise SpryRuntimeError(f"Unknown compound operator: {node.op!r}", node)
            if isinstance(obj, SpryInstance):
                obj.set(node.property, new_val)
            elif isinstance(obj, dict):
                obj[node.property] = new_val
            elif isinstance(obj, SpryClass):
                obj._static_fields[node.property] = new_val
            return None

        if isinstance(node, IndexAssignment):
            obj = self._eval(node.object, env)
            idx = self._eval(node.index, env)
            value = self._eval(node.value, env)
            # Symbol subscript assignment — check for computed setter on SpryInstance
            if isinstance(idx, SprySymbol) and isinstance(obj, SpryInstance):
                key_str = str(idx)
                setter_key = f"__setter__{key_str}"
                if setter_key in obj.fields:
                    setter_fn = obj.fields[setter_key]
                    bm = BoundMethod(instance=obj, fn=setter_fn)
                    self._call_bound_method(bm, [value], node)
                    return None
                obj.fields[key_str] = value
                return None
            # Plain dict with Symbol key — use the symbol object itself as key (identity semantics)
            if isinstance(idx, SprySymbol) and isinstance(obj, dict):
                obj[idx] = value
                return None
            try:
                obj[idx] = value
            except (TypeError, KeyError, IndexError) as e:
                raise SpryRuntimeError(f"Index assignment error: {e}", node)
            return None

        if isinstance(node, CompoundAssignment):
            current = env.get(node.name)
            rhs = self._eval(node.value, env)
            if node.op == "+":
                # JS-style: if either operand is a string, coerce the other
                if isinstance(current, str) and not isinstance(rhs, str):
                    rhs = self._builtin_str(rhs)
                elif isinstance(rhs, str) and not isinstance(current, str):
                    current = self._builtin_str(current)
                new_val = current + rhs
            elif node.op == "-":
                new_val = current - rhs
            elif node.op == "*":
                new_val = current * rhs
            elif node.op == "/":
                if rhs == 0:
                    new_val = float("nan") if current == 0 else math.copysign(float("inf"), current)
                else:
                    new_val = current / rhs
            elif node.op == "%":
                if rhs == 0:
                    new_val = float("nan")
                else:
                    new_val = current % rhs
            elif node.op == "??":
                # ??= : only assign if current value is null/None or undefined
                if current is None or isinstance(current, _SpryUndefinedType):
                    new_val = rhs
                else:
                    return None  # no-op
            elif node.op == "&&":
                # &&= : only assign if current is truthy
                if self._truthy(current):
                    new_val = rhs
                else:
                    return None  # no-op
            elif node.op == "||":
                # ||= : only assign if current is falsy
                if not self._truthy(current):
                    new_val = rhs
                else:
                    return None  # no-op
            elif node.op == "&":
                new_val = int(current) & int(rhs)
            elif node.op == "|":
                new_val = int(current) | int(rhs)
            elif node.op == "^":
                new_val = int(current) ^ int(rhs)
            elif node.op == "<<":
                new_val = int(current) << int(rhs)
            elif node.op == ">>":
                new_val = int(current) >> int(rhs)
            elif node.op == "**":
                new_val = current ** rhs
            else:
                raise SpryRuntimeError(f"Unknown compound operator: {node.op!r}", node)
            env.set(node.name, new_val)
            return None

        if isinstance(node, FunctionDeclaration):
            fn = SpryFunction(
                name=node.name,
                params=node.params,
                body=node.body,  # type: ignore
                closure=env,
                defaults=node.defaults,
                rest_param=node.rest_param,
                is_generator=node.is_generator,
                is_async=node.is_async,
            )
            env.define(node.name, fn, mutable=False)
            return None

        if isinstance(node, TaskDeclaration):
            task = SpryTask(name=node.name, body=node.body, closure=env)  # type: ignore
            env.define(node.name, task, mutable=False)
            return None

        if isinstance(node, AllowStatement):
            self.permissions.add_allow(node.permission, node.argument)
            return None

        if isinstance(node, DenyStatement):
            self.permissions.add_deny(node.permission, node.argument)
            return None

        if isinstance(node, PrivateDataDeclaration):
            # Register as a private field — the interpreter doesn't need to do much here
            return None

        if isinstance(node, SensitiveDataDeclaration):
            return None

        if isinstance(node, IfStatement):
            cond = self._eval(node.condition, env)
            if self._truthy(cond):
                child = env.child()
                return self._exec_block(node.then_block, child)
            elif node.else_block is not None:
                child = env.child()
                return self._exec_block(node.else_block, child)
            return None

        if isinstance(node, TryCatchStatement):
            result = None
            exc_to_reraise = None
            try:
                child = env.child()
                result = self._exec_block(node.body, child)
            except SpryUserError as ue:
                if node.handler is not None:
                    child = env.child()
                    err_val = ue.value
                    if isinstance(err_val, dict) and "message" not in err_val:
                        err_val = {**err_val, "message": ue.message}
                    if node.error_pattern is not None:
                        self._apply_catch_pattern(node.error_pattern, err_val, child)
                    elif node.error_name:
                        child.define(node.error_name, err_val, mutable=True)
                    result = self._exec_block(node.handler, child)
                else:
                    exc_to_reraise = ue
            except (SpryRuntimeError, Exception) as e:
                if node.handler is not None:
                    child = env.child()
                    err_val = SpryResult(ok=False, error=str(e))
                    if node.error_pattern is not None:
                        self._apply_catch_pattern(node.error_pattern, err_val, child)
                    elif node.error_name:
                        child.define(node.error_name, err_val, mutable=True)
                    result = self._exec_block(node.handler, child)
                else:
                    exc_to_reraise = e
            finally:
                if node.finally_block is not None:
                    finally_child = env.child()
                    self._exec_block(node.finally_block, finally_child)
            if exc_to_reraise is not None:
                raise exc_to_reraise
            return result

        if isinstance(node, AtomicStatement):
            return self._exec_atomic(node, env)

        if isinstance(node, TransactionStatement):
            return self._exec_transaction(node, env)

        if isinstance(node, CompensateStatement):
            # Compensate blocks are handled by the transaction executor
            return None

        if isinstance(node, ForStatement):
            return self._exec_for(node, env)

        if isinstance(node, ForCStyleStatement):
            return self._exec_for_cstyle(node, env)

        if isinstance(node, WhileStatement):
            return self._exec_while(node, env)

        if isinstance(node, LoopStatement):
            return self._exec_loop(node, env)

        if isinstance(node, RetryStatement):
            return self._exec_retry(node, env)

        if isinstance(node, BreakStatement):
            raise BreakSignal(node.label)

        if isinstance(node, ContinueStatement):
            raise ContinueSignal(node.label)

        if isinstance(node, LabeledStatement):
            return self._exec_labeled(node, env)

        if isinstance(node, CreateStatement):
            return self._exec_create(node, env)

        if isinstance(node, CompressStatement):
            return self._exec_compress(node, env)

        if isinstance(node, ExtractStatement):
            return self._exec_extract(node, env)

        if isinstance(node, SleepStatement):
            duration = self._eval(node.duration, env)
            seconds = float(duration) / 1000.0 if node.unit == "ms" else float(duration)
            time.sleep(seconds)
            return None

        if isinstance(node, ScheduleStatement):
            self.logger.info(f"[schedule] {node.frequency} at {node.at_time!r} (not running — runtime scheduler needed)")
            return None

        if isinstance(node, TestBlock):
            return self._exec_test_block(node, env)

        if isinstance(node, ExpectStatement):
            return self._exec_expect(node, env)

        if isinstance(node, ReturnStatement):
            value = self._eval(node.value, env) if node.value is not None else None
            raise ReturnSignal(value)

        if isinstance(node, StopStatement):
            raise StopSignal()

        if isinstance(node, LogStatement):
            msg = self._eval(node.message, env)
            # Convert to SpryCode string representation (true/false/null instead of True/False/None)
            msg_str = self._builtin_str(msg)
            level = node.level.lower()
            if level == "info":
                self.logger.info(msg_str)
            elif level in ("warn", "warning"):
                self.logger.warn(msg_str)
            elif level == "error":
                self.logger.error(msg_str)
            elif level in ("debug", "trace", "verbose", "notice", "success"):
                self.logger.debug(msg_str)
            else:
                self.logger.info(msg_str)
            return None

        if isinstance(node, MoveStatement):
            return self._exec_move(node, env)

        if isinstance(node, CopyStatement):
            return self._exec_copy(node, env)

        if isinstance(node, ReadStatement):
            return self._exec_read(node, env)

        if isinstance(node, WriteStatement):
            return self._exec_write(node, env)

        if isinstance(node, DeleteStatement):
            return self._exec_delete(node, env)

        if isinstance(node, StreamStatement):
            return self._exec_stream(node, env)

        if isinstance(node, SyncStatement):
            return self._exec_sync(node, env)

        if isinstance(node, WatchStatement):
            # Watch is a no-op in the basic interpreter
            path = self._eval(node.path, env)
            self.logger.info(f"Watching {path}")
            return None

        if isinstance(node, ParseStatement):
            data = self._eval(node.data, env)
            return self._parse(node.format, str(data))

        if isinstance(node, ValidateStatement):
            data = self._eval(node.data, env)
            schema = self._eval(node.schema, env)
            return self._validate(data, schema, env)

        if isinstance(node, RedactStatement):
            data = self._eval(node.data, env)
            return self._redact(data, node.fields)

        if isinstance(node, UseStatement):
            # Adapter loading
            alias = node.alias or node.name
            if node.name == "sql":
                env.define(alias, self._sql, mutable=False)
            self.logger.info(f"Adapter '{node.name}' registered")
            return None

        if isinstance(node, AdapterDeclaration):
            return None

        if isinstance(node, ConnectorDeclaration):
            env.define(node.name, {"name": node.name, "type": "connector"}, mutable=False)
            return None

        if isinstance(node, FraudCheckStatement):
            return self._exec_fraud_check(node, env)

        if isinstance(node, MatchStatement):
            return self._exec_match(node, env)

        if isinstance(node, SwitchStatement):
            return self._exec_switch(node, env)

        if isinstance(node, RepeatUntilStatement):
            return self._exec_repeat_until(node, env)

        if isinstance(node, AssertStatement):
            return self._exec_assert(node, env)

        if isinstance(node, ImportStatement):
            return self._exec_import(node, env)

        if isinstance(node, ThrowStatement):
            value = self._eval(node.value, env)
            raise SpryUserError(value)

        if isinstance(node, DebuggerStatement):
            # Call debugger hook if set (used by the REPL for interactive debugging)
            if self._debugger_hook is not None:
                self._debugger_hook(env)
            return None

        if isinstance(node, EnumDeclaration):
            return self._exec_enum(node, env)

        if isinstance(node, StructDeclaration):
            return self._exec_struct(node, env)

        if isinstance(node, ClassDeclaration):
            return self._exec_class(node, env)

        if isinstance(node, InterfaceDeclaration):
            # Interface is mostly a type declaration — no runtime behaviour
            return None

        if isinstance(node, ListDestructure):
            return self._exec_list_destructure(node, env)

        if isinstance(node, ListDestructureAssignment):
            # [a, b] = expr — assigns to existing variables
            rhs = self._eval(node.value, env)
            items = list(rhs) if not isinstance(rhs, list) else rhs
            for i, name in enumerate(node.names):
                val = items[i] if i < len(items) else None
                try:
                    env.set(name, val)
                except SpryRuntimeError:
                    env.define(name, val, mutable=True)
            if node.rest_name is not None:
                rest_val = items[len(node.names):]
                try:
                    env.set(node.rest_name, rest_val)
                except SpryRuntimeError:
                    env.define(node.rest_name, rest_val, mutable=True)
            return None

        if isinstance(node, ObjectDestructure):
            return self._exec_object_destructure(node, env)

        if isinstance(node, DoWhileStatement):
            return self._exec_do_while(node, env)

        if isinstance(node, SpawnStatement):
            return self._exec_spawn(node, env)

        if isinstance(node, WebSocketStatement):
            return self._exec_websocket(node, env)

        if isinstance(node, WithStatement):
            return self._exec_with(node, env)

        if isinstance(node, DebitStatement):
            return self._exec_debit(node, env)

        if isinstance(node, CreditStatement):
            return self._exec_credit(node, env)

        if isinstance(node, YieldStatement):
            if node.delegate:
                # yield* iterable — iterate and forward each value via the yield hook
                iterable = self._eval(node.value, env) if node.value is not None else []
                yield_hook = getattr(self._tl, "yield_hook", None)
                delegate_return_val = None
                if isinstance(iterable, SpryGenerator):
                    # Use the generator's next() protocol so we get the return value
                    while True:
                        item = iterable.next()
                        if isinstance(item, SpryPromise):
                            item = item._value if item.status == "fulfilled" else {"value": None, "done": True}
                        if item["done"]:
                            delegate_return_val = item["value"]
                            break
                        val_ = item["value"]
                        if yield_hook is not None:
                            yield_hook(val_)
                        else:
                            raise YieldSignal(val_)
                else:
                    if isinstance(iterable, (list, tuple)):
                        items = list(iterable)
                    else:
                        try:
                            items = list(iterable)
                        except TypeError:
                            items = []
                    for item_ in items:
                        if yield_hook is not None:
                            yield_hook(item_)
                        else:
                            raise YieldSignal(item_)
                return delegate_return_val
            value = self._eval(node.value, env) if node.value is not None else None
            # Check for thread-local generator yield hook (used by coroutine generators)
            yield_hook = getattr(self._tl, "yield_hook", None)
            if yield_hook is not None:
                return yield_hook(value)
            raise YieldSignal(value)

        if isinstance(node, ExportStatement):
            # Execute the wrapped declaration normally; exports are treated
            # the same as regular declarations at runtime.
            if node.declaration is not None:
                return self._exec(node.declaration, env)
            return None

        # Expression as statement
        return self._eval(node, env)

    # ------------------------------------------------------------------
    # Expression evaluation
    # ------------------------------------------------------------------

    def _eval(self, node: Node | None, env: Environment) -> Any:
        if node is None:
            return None

        if isinstance(node, StringLiteral):
            return node.value

        if isinstance(node, NumberLiteral):
            # BigInt literal: 42n
            if hasattr(node, "raw") and node.raw and node.raw.endswith("n"):
                return _SpryBigInt(int(node.raw[:-1]))
            # Return int if no fractional part
            val = node.value
            if val == int(val):
                return int(val)
            return val

        if isinstance(node, BoolLiteral):
            return node.value

        if isinstance(node, NullLiteral):
            return None

        if isinstance(node, Identifier):
            if node.name in ("true", "fast"):
                return True
            if node.name == "false":
                return False
            if node.name == "null":
                return None
            if node.name == "ok":
                return SPRY_OK
            return env.get(node.name)

        if isinstance(node, SecretLiteral):
            return self.secrets.read(node.key, self.permissions)

        if isinstance(node, NewTargetExpression):
            nt = getattr(self._tl, "new_target", None)
            return nt if nt is not None else SPRY_UNDEFINED

        if isinstance(node, ObjectLiteral):
            result: dict[str, Any] = {}
            # If entries list is populated (spread or computed keys present), use it
            if node.entries:
                for key_or_marker, val_node in node.entries:
                    if key_or_marker is None:
                        # Spread element
                        spread_val = self._eval(val_node.expr, env)  # type: ignore[union-attr]
                        if isinstance(spread_val, dict):
                            result.update(spread_val)
                        elif isinstance(spread_val, SpryInstance):
                            # Spread instance fields (non-private, non-method)
                            for fname, fval in spread_val.fields.items():
                                if not fname.startswith("__") and not isinstance(fval, (SpryFunction, BoundMethod)):
                                    result[fname] = fval
                        else:
                            raise SpryRuntimeError("Object spread requires an object", node)
                    elif key_or_marker == "__computed__":
                        # Computed key: ([key_expr], value_node) tuple
                        key_expr_node, value_node_inner = val_node  # type: ignore[misc]
                        _ck = self._eval(key_expr_node, env)
                        computed_key = _ck if isinstance(_ck, SprySymbol) else str(_ck)
                        result[computed_key] = self._eval(value_node_inner, env)
                    elif key_or_marker == "__computed_getter__":
                        key_expr_node, fn_node = val_node  # type: ignore[misc]
                        _ck2 = self._eval(key_expr_node, env)
                        computed_key = _ck2 if isinstance(_ck2, SprySymbol) else str(_ck2)
                        getter_fn = self._eval(fn_node, env)
                        result[f"__getter__{computed_key}"] = getter_fn
                    elif key_or_marker == "__computed_setter__":
                        key_expr_node, fn_node = val_node  # type: ignore[misc]
                        _ck3 = self._eval(key_expr_node, env)
                        computed_key = _ck3 if isinstance(_ck3, SprySymbol) else str(_ck3)
                        setter_fn = self._eval(fn_node, env)
                        result[f"__setter__{computed_key}"] = setter_fn
                    else:
                        result[key_or_marker] = self._eval(val_node, env)
            else:
                for k, v in node.pairs.items():
                    result[k] = self._eval(v, env)
            return result

        if isinstance(node, ArrayLiteral):
            result_list: list[Any] = []
            for item in node.items:
                if isinstance(item, SpreadElement):
                    spread_val = self._eval(item.expr, env)
                    try:
                        result_list.extend(self._iter_to_list(spread_val, item))
                    except SpryRuntimeError:
                        raise SpryRuntimeError("Spread operator requires an iterable", item)
                else:
                    result_list.append(self._eval(item, env))
            return result_list

        if isinstance(node, BinaryExpression):
            return self._eval_binary(node, env)

        if isinstance(node, UnaryExpression):
            return self._eval_unary(node, env)

        if isinstance(node, CallExpression):
            return self._eval_call(node, env)

        if isinstance(node, OptionalCallExpression):
            callee = self._eval(node.callee, env)
            if callee is None or isinstance(callee, _SpryUndefinedType):
                return SPRY_UNDEFINED
            args: list[Any] = []
            for a in node.args:
                if isinstance(a, SpreadElement):
                    spread_val = self._eval(a.expr, env)
                    if isinstance(spread_val, (list, tuple)):
                        args.extend(spread_val)
                    else:
                        args.append(spread_val)
                else:
                    args.append(self._eval(a, env))
            py_args = [self._to_py_callable(a, env) for a in args]
            if isinstance(callee, SpryClass):
                return self._construct_class(callee, args, node)
            if callable(callee) and not isinstance(callee, (SpryFunction,)):
                try:
                    return callee(*py_args)
                except Exception as e:
                    raise SpryRuntimeError(str(e), node)
            if isinstance(callee, BoundMethod):
                return self._call_bound_method(callee, args, node)
            if isinstance(callee, DictBoundMethod):
                return self._call_dict_bound_method(callee.fn, callee.obj, args, node)
            if isinstance(callee, SpryFunction):
                return self._call_function(callee, args, node)
            if isinstance(callee, SpryLambda):
                return self._apply_lambda(callee, args[0] if args else None, env)
            if isinstance(callee, SpryMultiLambda):
                return self._apply_multi_lambda(callee, args, env)
            raise SpryRuntimeError(f"Optional call target is not callable: {type(callee).__name__}", node)

        if isinstance(node, AwaitExpression):
            val = self._eval(node.operand, env)
            if isinstance(val, SpryPromise):
                if val._settled:
                    return val._value
                err = val._error
                # If the rejection value is a SpryInstance (user-defined error class),
                # SpryErrorObject (builtin error), or any non-string error value,
                # re-raise as SpryUserError so try/catch in user code handles it properly
                if isinstance(err, (SpryErrorObject, SpryInstance)):
                    raise SpryUserError(err)
                if err is not None and not isinstance(err, str):
                    raise SpryUserError(err)
                raise SpryRuntimeError(str(err) if err is not None else "Promise rejected", node)
            return val

        if isinstance(node, SequenceExpression):
            result = None
            for expr in node.expressions:
                result = self._eval(expr, env)
            return result

        if isinstance(node, MemberExpression):
            return self._eval_member(node, env)

        if isinstance(node, OptionalMemberExpression):
            obj = self._eval(node.object, env)
            if obj is None or obj is SPRY_UNDEFINED:
                return SPRY_UNDEFINED
            return self._eval_member_on(obj, node.property, node)

        if isinstance(node, OptionalIndexExpression):
            obj = self._eval(node.object, env)
            if obj is None or obj is SPRY_UNDEFINED:
                return SPRY_UNDEFINED
            idx = self._eval(node.index, env)
            try:
                if isinstance(obj, dict):
                    return obj.get(idx, SPRY_UNDEFINED)
                return obj[idx]
            except (KeyError, IndexError, TypeError):
                return SPRY_UNDEFINED

        if isinstance(node, IndexExpression):
            obj = self._eval(node.object, env)
            idx = self._eval(node.index, env)
            # Symbol subscript — handle well-known symbols for built-in types
            if isinstance(idx, SprySymbol):
                if idx.description == "iterator":
                    if isinstance(obj, (list, str, range)):
                        return _make_sequence_iter(list(obj))
                    if isinstance(obj, SprySet):
                        return _make_sequence_iter(list(obj._data))
                    if isinstance(obj, SpryMap):
                        return _make_sequence_iter([[k, v] for k, v in obj._data.items()])
                # SpryClass indexed with SprySymbol — look up in _static_fields
                if isinstance(obj, SpryClass):
                    key_str = str(idx)
                    if key_str in obj._static_fields:
                        return obj._static_fields[key_str]
                    raise SpryRuntimeError(
                        f"Symbol subscript {idx!r} is not supported on SpryClass", node
                    )
                # SpryInstance indexed with SprySymbol — use str(sym) as key for consistency
                # with how computed methods are stored in _exec_class
                if isinstance(obj, SpryInstance):
                    key_str = str(idx)
                    # Check for computed getter first
                    getter_key = f"__getter__{key_str}"
                    if getter_key in obj.fields:
                        getter_fn = obj.fields[getter_key]
                        return self._call_function(getter_fn, [], node)
                    if key_str in obj.fields:
                        v = obj.fields[key_str]
                        if isinstance(v, SpryFunction):
                            return BoundMethod(instance=obj, fn=v)
                        return v
                    return None
                # Plain dict with SprySymbol — use symbol object itself as key (identity semantics)
                if isinstance(obj, dict):
                    return obj.get(idx)
                raise SpryRuntimeError(
                    f"Symbol subscript {idx!r} is not supported on {type(obj).__name__}", node
                )
            try:
                if isinstance(obj, dict):
                    # dict: missing key returns undefined (like JS obj['key'])
                    return obj.get(idx, SPRY_UNDEFINED)
                return obj[idx]
            except (KeyError, IndexError, TypeError) as e:
                raise SpryRuntimeError(f"Index error: {e}", node)

        if isinstance(node, LambdaExpression):
            # Capture closure environment for proper free-variable access
            sl = SpryLambda(param=node.param, body=node.body, closure=env)
            sl.operation = getattr(node, "operation", None)
            return sl

        if isinstance(node, MultiParamLambda):
            sml = SpryMultiLambda(params=node.params, body=node.body, closure=env)
            sml.operation = getattr(node, "operation", None)
            sml.init = getattr(node, "init", None)
            return sml

        if isinstance(node, TernaryExpression):
            cond = self._eval(node.condition, env)
            if self._truthy(cond):
                return self._eval(node.then_expr, env)
            return self._eval(node.else_expr, env)

        if isinstance(node, NullCoalesceExpression):
            left_val = self._eval(node.left, env)
            if left_val is not None and not isinstance(left_val, _SpryUndefinedType):
                return left_val
            return self._eval(node.right, env)

        if isinstance(node, NewExpression):
            callee = self._eval(node.callee, env)
            args: list[Any] = []
            for a in node.args:
                if isinstance(a, SpreadElement):
                    spread_val = self._eval(a.expr, env)
                    try:
                        args.extend(self._iter_to_list(spread_val, a))
                    except SpryRuntimeError:
                        args.append(spread_val)
                else:
                    args.append(self._eval(a, env))
            if isinstance(callee, SpryClass):
                return self._construct_class(callee, args, node)
            if isinstance(callee, SpryFunction):
                return self._construct_plain_function(callee, args, node)
            if isinstance(callee, SpryProxy):
                return callee._spry_apply(None, args)
            if callable(callee):
                try:
                    return callee(*args)
                except Exception as e:
                    raise SpryRuntimeError(str(e), node)
            raise SpryRuntimeError(f"Cannot construct {type(callee).__name__}", node)

        if isinstance(node, InExpression):
            # Private brand check: `#field in obj` — the LHS is parsed as Identifier("__private__field")
            # Don't try to evaluate it as a variable; just use the name as the private key.
            if isinstance(node.item, Identifier) and node.item.name.startswith("__private__"):
                private_key = node.item.name
                coll_val = self._eval(node.collection, env)
                if isinstance(coll_val, SpryInstance):
                    return private_key in coll_val.fields
                return False
            item_val = self._eval(node.item, env)
            coll_val = self._eval(node.collection, env)
            if isinstance(coll_val, (list, tuple)):
                # JS semantics: `key in array` checks if index exists
                if isinstance(item_val, (int, float)) and not isinstance(item_val, bool):
                    idx = int(item_val)
                    return 0 <= idx < len(coll_val)
                # String "0" etc. also treated as index
                if isinstance(item_val, str):
                    try:
                        idx = int(item_val)
                        return 0 <= idx < len(coll_val)
                    except ValueError:
                        pass
                return item_val in coll_val
            if isinstance(coll_val, SpryProxy):
                return coll_val._spry_has_prop(str(item_val))
            if isinstance(coll_val, dict):
                cur: Any = coll_val
                while cur is not None:
                    if isinstance(cur, dict) and item_val in cur:
                        return True
                    cur = cur.get("__spry_proto__") if isinstance(cur, dict) else None
                return False
            if isinstance(coll_val, str):
                return str(item_val) in coll_val
            if isinstance(coll_val, SpryInstance):
                return str(item_val) in coll_val.fields
            if isinstance(coll_val, SprySet):
                return coll_val.has(item_val)
            if isinstance(coll_val, SpryMap):
                return item_val in coll_val._data
            raise SpryRuntimeError(f"'in' requires a list, object, or string, got {type(coll_val).__name__}", node)

        if isinstance(node, FStringExpression):
            return self._eval_fstring(node.raw_template, env)

        if isinstance(node, TaggedTemplateExpression):
            return self._eval_tagged_template(node, env)

        if isinstance(node, ClassExpression):
            return self._eval_class_expression(node, env)

        if isinstance(node, PipelineExpression):
            return self._eval_pipeline(node, env)

        if isinstance(node, ParseStatement):
            data = self._eval(node.data, env)
            return self._parse(node.format, str(data))

        if isinstance(node, ReadStatement):
            return self._exec_read(node, env)

        if isinstance(node, WriteStatement):
            return self._exec_write(node, env)

        if isinstance(node, RegexLiteral):
            flags_map = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}
            re_flags = 0
            is_global = "g" in node.flags
            for f in node.flags:
                re_flags |= flags_map.get(f, 0)
            compiled = re.compile(_js_regex_to_python(node.pattern), re_flags)
            return SpryRegex(compiled, global_flag=is_global, flags_str=node.flags)

        if isinstance(node, AnonymousFunctionExpression):
            fn_name = node.name if node.name else "<anonymous>"
            is_async = getattr(node, "is_async", False)
            is_generator = getattr(node, "is_generator", False)
            if node.name:
                # Named function expression: create self-referential closure
                fn_self_env = env.child()
                fn = SpryFunction(
                    name=fn_name,
                    params=node.params,
                    body=node.body,  # type: ignore
                    closure=fn_self_env,
                    defaults=node.defaults,
                    rest_param=node.rest_param,
                    is_async=is_async,
                    is_generator=is_generator,
                )
                # Bind the function to its own name in its closure (enables recursion)
                fn_self_env.define(fn_name, fn, mutable=False)
            else:
                fn = SpryFunction(
                    name=fn_name,
                    params=node.params,
                    body=node.body,  # type: ignore
                    closure=env,
                    defaults=node.defaults,
                    rest_param=node.rest_param,
                    is_async=is_async,
                    is_generator=is_generator,
                )
            return fn

        if isinstance(node, SuperExpression):
            return self._eval_super(node, env)

        if isinstance(node, ListComprehension):
            iterable = self._eval(node.iterable, env)
            result_comp: list[Any] = []
            for item_val in self._iter(iterable, node):
                child = env.child()
                child.define(node.var, item_val, mutable=False)
                if node.condition is not None and not self._truthy(self._eval(node.condition, child)):
                    continue
                result_comp.append(self._eval(node.expr, child))
            return result_comp

        if isinstance(node, DictComprehension):
            iterable = self._eval(node.iterable, env)
            result_dict: dict = {}
            for item_val in self._iter(iterable, node):
                child = env.child()
                child.define(node.var, item_val, mutable=False)
                if node.condition is not None and not self._truthy(self._eval(node.condition, child)):
                    continue
                k = self._eval(node.key_expr, child)
                v = self._eval(node.val_expr, child)
                result_dict[k] = v
            return result_dict

        if isinstance(node, PostfixExpression):
            return self._eval_postfix(node, env)

        if isinstance(node, TypeofExpression):
            try:
                val = self._eval(node.operand, env)
            except SpryRuntimeError as e:
                if "Undefined variable" in str(e) or "not defined" in str(e):
                    return "undefined"
                raise
            return self._js_typeof(val)

        if isinstance(node, InstanceofExpression):
            val = self._eval(node.operand, env)
            # Try to find the type as a SpryClass in the environment (supports inheritance)
            try:
                target = env.get(node.type_name)
                # Check for Symbol.hasInstance static method first (custom instanceof behaviour)
                if isinstance(target, SpryClass):
                    _has_instance_key = "Symbol('hasInstance')"
                    if _has_instance_key in target._static_fields:
                        _has_instance_fn = target._static_fields[_has_instance_key]
                        return bool(self._call_function(_has_instance_fn, [val], node))
                if isinstance(target, SpryClass) and isinstance(val, SpryInstance):
                    cls: SpryClass | None = val.cls
                    while cls is not None:
                        if cls is target:
                            return True
                        cls = cls.superclass
                    return False
                # Also handle: val instanceof Error (where Error is _ErrorNamespace)
                if isinstance(target, _ErrorNamespace):
                    if isinstance(val, SpryErrorObject):
                        return True
                    if isinstance(val, SpryInstance):
                        cls_check: SpryClass | None = val.cls
                        while cls_check is not None:
                            if getattr(cls_check, '_builtin_error_superclass', None) is target:
                                return True
                            cls_check = cls_check.superclass
                    return False
                # instanceof for plain functions used as constructors (fn.prototype chain walk)
                if isinstance(target, SpryFunction) and isinstance(val, dict):
                    proto = val.get("__spry_proto__")
                    fn_proto = target._prototype
                    while proto is not None:
                        if proto is fn_proto:
                            return True
                        proto = proto.get("__spry_proto__") if isinstance(proto, dict) else None
                    return False
            except SpryRuntimeError:
                pass
            return self._spry_instanceof(val, node.type_name)

        if isinstance(node, TypeCastExpression):
            return self._eval_type_cast(node, env)

        if isinstance(node, ResultLiteral):
            value = self._eval(node.value, env) if node.value is not None else None
            if node.is_ok:
                return SpryResult(ok=True, value=value)
            return SpryResult(ok=False, error=str(value) if value is not None else "")

        if isinstance(node, DebitStatement):
            return self._exec_debit(node, env)

        if isinstance(node, CreditStatement):
            return self._exec_credit(node, env)

        # Fall through — try executing as a statement
        return self._exec(node, env)

    def _eval_binary(self, node: BinaryExpression, env: Environment) -> Any:
        op = node.op
        left = self._eval(node.left, env)

        # Short-circuit operators: evaluate right operand lazily
        if op == "&&":
            if not self._truthy(left):
                return left
            return self._eval(node.right, env)
        if op == "||":
            if self._truthy(left):
                return left
            return self._eval(node.right, env)

        right = self._eval(node.right, env)

        if op == "+":
            if isinstance(left, (SpryMoney,)) and isinstance(right, (SpryMoney,)):
                return left + right
            # Coerce SpryInstance to primitive using "default" hint
            if isinstance(left, SpryInstance):
                left = self._to_primitive(left, "default")
            if isinstance(right, SpryInstance):
                right = self._to_primitive(right, "default")
            # Coerce dict with toPrimitive
            if isinstance(left, dict):
                left = self._dict_to_primitive(left, "default")
            if isinstance(right, dict):
                right = self._dict_to_primitive(right, "default")
            # When one operand is a string, coerce the other to string (JS-style)
            if isinstance(left, str) and not isinstance(right, str):
                right = self._builtin_str(right)
            elif isinstance(right, str) and not isinstance(left, str):
                left = self._builtin_str(left)
            # JS numeric addition: null→0, undefined→NaN, bool→0/1
            elif isinstance(left, (type(None), _SpryUndefinedType, bool)) or isinstance(right, (type(None), _SpryUndefinedType, bool)):
                left = self._to_numeric(left)
                right = self._to_numeric(right)
            return left + right
        if op == "-":
            if isinstance(left, SpryMoney) and isinstance(right, SpryMoney):
                return left - right
            if isinstance(left, SpryInstance):
                left = self._to_numeric(left)
            if isinstance(right, SpryInstance):
                right = self._to_numeric(right)
            if isinstance(left, dict):
                left = self._dict_to_primitive(left, "number")
                left = self._to_numeric(left)
            if isinstance(right, dict):
                right = self._dict_to_primitive(right, "number")
                right = self._to_numeric(right)
            return left - right
        if op == "*":
            if isinstance(left, SpryMoney):
                return left * right
            if isinstance(left, SpryInstance):
                left = self._to_numeric(left)
            if isinstance(right, SpryInstance):
                right = self._to_numeric(right)
            if isinstance(left, dict):
                left = self._dict_to_primitive(left, "number")
                left = self._to_numeric(left)
            if isinstance(right, dict):
                right = self._dict_to_primitive(right, "number")
                right = self._to_numeric(right)
            return left * right
        if op == "/":
            if isinstance(left, _SpryBigInt) and isinstance(right, _SpryBigInt):
                if right._value == 0:
                    raise SpryRuntimeError("Division by zero", node)
                return left // right  # BigInt integer division
            if isinstance(left, SpryInstance):
                left = self._to_numeric(left)
            if isinstance(right, SpryInstance):
                right = self._to_numeric(right)
            if isinstance(left, dict):
                left = self._dict_to_primitive(left, "number")
                left = self._to_numeric(left)
            if isinstance(right, dict):
                right = self._dict_to_primitive(right, "number")
                right = self._to_numeric(right)
            if right == 0:
                if isinstance(left, (int, float)):
                    if left == 0:
                        return float("nan")
                    return math.copysign(float("inf"), left)
                raise SpryRuntimeError("Division by zero", node)
            return left / right
        if op == "%":
            if isinstance(left, SpryInstance):
                left = self._to_numeric(left)
            if isinstance(right, SpryInstance):
                right = self._to_numeric(right)
            if isinstance(left, dict):
                left = self._dict_to_primitive(left, "number")
                left = self._to_numeric(left)
            if isinstance(right, dict):
                right = self._dict_to_primitive(right, "number")
                right = self._to_numeric(right)
            if right == 0:
                return float("nan")
            return left % right
        if op == "**":
            if isinstance(left, SpryInstance):
                left = self._to_numeric(left)
            if isinstance(right, SpryInstance):
                right = self._to_numeric(right)
            return left ** right
        if op == "==":
            return _abstract_eq(left, right)
        if op == "!=":
            return not _abstract_eq(left, right)
        if op == "===":
            return _strict_eq(left, right)
        if op == "!==":
            return not _strict_eq(left, right)
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        # Bitwise operators
        if op == "&":
            return int(left) & int(right)
        if op == "|":
            return int(left) | int(right)
        if op == "^":
            return int(left) ^ int(right)
        if op == "<<":
            return int(left) << int(right)
        if op == ">>":
            return int(left) >> int(right)
        if op == ">>>":
            # Unsigned right shift: treat left as 32-bit unsigned
            return (int(left) & 0xFFFFFFFF) >> int(right)
        raise SpryRuntimeError(f"Unknown operator: {op!r}", node)

    def _eval_unary(self, node: UnaryExpression, env: Environment) -> Any:
        operand = self._eval(node.operand, env)
        if node.op in ("!", "not"):
            return not self._truthy(operand)
        if node.op == "+":
            return self._to_numeric(operand)
        if node.op == "-":
            if isinstance(operand, _SpryBigInt):
                return -operand
            if isinstance(operand, int) and operand == 0:
                return float(-0.0)  # JS-style negative zero
            return -self._to_numeric(operand)
        if node.op == "~":
            return ~int(operand)
        if node.op == "void":
            return None  # void operator evaluates expression and returns null
        raise SpryRuntimeError(f"Unknown unary operator: {node.op!r}", node)

    def _eval_call(self, node: CallExpression, env: Environment) -> Any:
        callee = self._eval(node.callee, env)
        # Evaluate args, expanding any SpreadElements
        args: list[Any] = []
        for a in node.args:
            if isinstance(a, SpreadElement):
                spread_val = self._eval(a.expr, env)
                try:
                    args.extend(self._iter_to_list(spread_val, a))
                except SpryRuntimeError:
                    args.append(spread_val)
            else:
                args.append(self._eval(a, env))
        # Wrap any lambda/function args so Python-level closures (e.g. list.map) can call them
        py_args = [self._to_py_callable(a, env) for a in args]

        if isinstance(callee, SpryClass):
            return self._construct_class(callee, args, node)

        if isinstance(callee, SpryProxy):
            return callee._spry_apply(None, args)

        if isinstance(callee, SpryStruct):
            return callee.create(args)

        if callable(callee) and not isinstance(callee, (SpryFunction, SpryTask)):
            # SpryCode-aware callables (namespaces, event bus, etc.) receive raw args
            # so they can handle SpryFunctions directly via _call_value
            raw_args = args if getattr(callee, "_spry_raw_args", False) else py_args
            try:
                return callee(*raw_args)
            except Exception as e:
                raise SpryRuntimeError(str(e), node)

        if isinstance(callee, BoundMethod):
            return self._call_bound_method(callee, args, node)

        if isinstance(callee, DictBoundMethod):
            return self._call_dict_bound_method(callee.fn, callee.obj, args, node)

        if isinstance(callee, SpryFunction):
            return self._call_function(callee, args, node)

        if isinstance(callee, SpryTask):
            return self._call_task(callee)

        if isinstance(callee, (SpryLambda, LambdaExpression)):
            return self._apply_lambda(callee, args[0] if args else None, env)

        if isinstance(callee, (SpryMultiLambda, MultiParamLambda)):
            return self._apply_multi_lambda(callee, args, env)

        # Zero-arg call on a non-callable property value (e.g. "hello".trim(), list.sort())
        if not args:
            return callee

        raise SpryRuntimeError(
            f"Cannot call {type(callee).__name__} (value: {callee!r})", node
        )

    def _call_function(self, fn: SpryFunction, args: list[Any], node: Node) -> Any:
        # Generator functions return a SpryGenerator object immediately
        if fn.is_generator:
            return SpryGenerator(fn, args, self)

        # fn.params contains positional params (rest_param is stored separately, never in fn.params)
        # Count required params: those with no default value and not dict-destructured
        required = [
            p for p, _ in fn.params
            if p not in fn.defaults and not p.startswith("__destruct__") and not p.startswith("__array_destruct__")
        ]
        total_positional = len(fn.params)

        if len(args) < len(required):
            raise SpryRuntimeError(
                f"Function {fn.name!r} expects at least {len(required)} args, got {len(args)}", node
            )
        # Extra args are silently ignored (JS semantics: callers may pass more args than declared)

        child = fn.closure.child()
        # Always define `arguments` (JS semantics: every function has access to all passed args)
        child.define("arguments", list(args), mutable=False)
        # Plain function calls must always see undefined for new.target.
        child.define("new.target", SPRY_UNDEFINED, mutable=False)

        for i, (pname, _ptype) in enumerate(fn.params):
            # Dict destructuring param: __destruct__:a,b  or  __destruct__:key|alias,b
            if pname.startswith("__destruct__:"):
                field_specs = pname[len("__destruct__:"):].split(",")
                arg_val = args[i] if i < len(args) else {}
                if not isinstance(arg_val, dict):
                    raise SpryRuntimeError(
                        f"Function {fn.name!r} expects an object for destructured param, got {type(arg_val).__name__}", node
                    )
                for fspec in field_specs:
                    fspec = fspec.strip()
                    if "|" in fspec:
                        fkey, flocal = fspec.split("|", 1)
                    else:
                        fkey = flocal = fspec
                    # Apply default if the key is absent from the source object (JS semantics:
                    # defaults apply when the key is missing, not when the value is null)
                    if fkey not in arg_val:
                        default_key = f"__destruct_default__{flocal}"
                        val = self._eval(fn.defaults[default_key], fn.closure) if default_key in fn.defaults else None
                    else:
                        val = arg_val[fkey]
                    child.define(flocal, val, mutable=False)
            # Array destructuring param: __array_destruct__:a,b...rest
            elif pname.startswith("__array_destruct__:"):
                raw = pname[len("__array_destruct__:"):]
                arr_rest_name: str | None = None
                if "..." in raw:
                    raw, arr_rest_name = raw.split("...", 1)
                arr_field_names = [f for f in raw.split(",") if f]
                arg_val = args[i] if i < len(args) else []
                items = list(arg_val) if not isinstance(arg_val, list) else arg_val
                for _j, _fname in enumerate(arr_field_names):
                    child.define(_fname.strip(), items[_j] if _j < len(items) else None, mutable=False)
                if arr_rest_name:
                    child.define(arr_rest_name, items[len(arr_field_names):], mutable=False)
            else:
                if i < len(args):
                    child.define(pname, args[i], mutable=False)
                elif pname in fn.defaults:
                    default_val = self._eval(fn.defaults[pname], fn.closure)
                    child.define(pname, default_val, mutable=False)
                else:
                    child.define(pname, None, mutable=False)

        if fn.rest_param is not None:
            rest_vals = args[len(fn.params):]
            child.define(fn.rest_param, list(rest_vals), mutable=False)

        try:
            self._exec_block(fn.body, child)
        except ReturnSignal as r:
            if fn.is_async:
                val = r.value
                # Unwrap awaited promise in async fn
                if isinstance(val, SpryPromise):
                    return val
                return SpryPromise(value=val)
            return r.value
        except (SpryUserError, SpryRuntimeError) as e:
            if fn.is_async:
                # Preserve the original error object for proper try/catch in user code
                if isinstance(e, SpryUserError):
                    return SpryPromise(value=None, error=e.value)
                return SpryPromise(value=None, error=str(e))
            raise
        if fn.is_async:
            return SpryPromise(value=None)
        return None

    def _call_function_with_this(
        self,
        fn: "SpryFunction",
        args: list[Any],
        this_arg: Any,
        node: "Node",
        new_target: Any = SPRY_UNDEFINED,
    ) -> Any:
        """Call fn with `this` and `self` bound to this_arg in the execution env."""
        child = fn.closure.child()
        child.define("arguments", list(args), mutable=False)
        child.define("new.target", new_target, mutable=False)
        child.define("this", this_arg, mutable=False)
        child.define("self", this_arg, mutable=False)
        # Expose instance fields if this_arg is a SpryInstance
        initial_field_values: dict[str, Any] = {}
        if isinstance(this_arg, SpryInstance):
            for fname, fval in this_arg.fields.items():
                if fname not in child._vars:
                    child.define(fname, fval, mutable=True)
                    initial_field_values[fname] = fval
        for i, (pname, _ptype) in enumerate(fn.params):
            if pname.startswith("__destruct__:"):
                field_specs = pname[len("__destruct__:"):].split(",")
                arg_val = args[i] if i < len(args) else {}
                if isinstance(arg_val, SpryInstance):
                    arg_val = arg_val.fields
                if not isinstance(arg_val, dict):
                    arg_val = {}
                for fspec in field_specs:
                    fspec = fspec.strip()
                    if "|" in fspec:
                        fkey, flocal = fspec.split("|", 1)
                    else:
                        fkey = flocal = fspec
                    if fkey not in arg_val:
                        default_key = f"__destruct_default__{flocal}"
                        fval = self._eval(fn.defaults[default_key], fn.closure) if default_key in fn.defaults else None
                    else:
                        fval = arg_val[fkey]
                    child.define(flocal, fval, mutable=False)
            elif pname.startswith("__array_destruct__:"):
                raw = pname[len("__array_destruct__:"):]
                arr_rest_name: str | None = None
                if "..." in raw:
                    raw, arr_rest_name = raw.split("...", 1)
                arr_field_names = [f for f in raw.split(",") if f]
                arg_val = args[i] if i < len(args) else []
                items = list(arg_val) if not isinstance(arg_val, list) else arg_val
                for _j, _fname in enumerate(arr_field_names):
                    child.define(_fname.strip(), items[_j] if _j < len(items) else None, mutable=False)
                if arr_rest_name:
                    child.define(arr_rest_name, items[len(arr_field_names):], mutable=False)
            elif i < len(args):
                child.define(pname, args[i], mutable=False)
            elif pname in fn.defaults:
                child.define(pname, self._eval(fn.defaults[pname], fn.closure), mutable=False)
            else:
                child.define(pname, None, mutable=False)
        if fn.rest_param is not None:
            child.define(fn.rest_param, list(args[len(fn.params):]), mutable=False)
        return_val = None
        try:
            self._exec_block(fn.body, child)
        except ReturnSignal as r:
            return_val = r.value
        # Sync back mutated fields if this_arg is a SpryInstance
        if isinstance(this_arg, SpryInstance) and initial_field_values:
            param_names = {p for p, _ in fn.params}
            for fname, initial in initial_field_values.items():
                if fname in param_names:
                    continue
                try:
                    child_val = child.get(fname)
                except SpryRuntimeError:
                    continue
                if child_val != initial:
                    this_arg.fields[fname] = child_val
        return return_val

    def _call_task(self, task: SpryTask) -> Any:
        child = task.closure.child()
        try:
            return self._exec_block(task.body, child)
        except ReturnSignal as r:
            return r.value
        except StopSignal:
            return None

    def _eval_member(self, node: MemberExpression, env: Environment) -> Any:
        # Handle super.method — route to parent class method lookup
        if isinstance(node.object, Identifier) and node.object.name == "super":
            return self._eval_super_member(node.property, env, node)
        obj = self._eval(node.object, env)
        prop = node.property

        if obj is None or isinstance(obj, _SpryUndefinedType):
            noun = "null" if obj is None else "undefined"
            err_msg = f"Cannot read properties of {noun} (reading '{prop}')"
            raise SpryUserError(SpryErrorObject("TypeError", err_msg))

        return self._eval_member_on(obj, prop, node)

    def _eval_member_on(self, obj: Any, prop: str, node: Node) -> Any:
        """Look up `prop` on `obj`. Used by both MemberExpression and OptionalMemberExpression."""

        if isinstance(obj, SpryMap):
            if prop == "size":
                return len(obj._data)
            if prop == "set":
                return obj.spry_set
            if prop == "get":
                return obj.spry_get
            if prop == "has":
                return obj.spry_has
            if prop == "delete":
                return obj.spry_delete
            if prop == "clear":
                return obj.spry_clear
            if prop == "keys":
                return obj.spry_keys
            if prop == "values":
                return obj.spry_values
            if prop == "entries":
                return obj.spry_entries
            if prop == "toEntries":
                return obj.spry_toEntries
            if prop == "forEach":
                return obj.spry_forEach
            if prop == "toObject":
                return obj.spry_toObject
            if prop == "filter":
                return obj.spry_filter
            if prop == "map":
                return obj.spry_map
            if prop == "clone":
                return obj.spry_clone
            if prop == "getOrInsert":
                return obj.spry_getOrInsert
            if prop == "getOrInsertComputed":
                return obj.spry_getOrInsertComputed
            if prop == "isEmpty":
                return len(obj._data) == 0
            raise SpryRuntimeError(f"Map has no property {prop!r}", node)

        if isinstance(obj, SprySet):
            if prop == "size":
                return obj.size
            if prop == "has":
                return obj.has
            if prop == "add":
                return obj.add
            if prop == "delete":
                return obj.delete
            if prop == "clear":
                return obj.clear
            if prop == "toList":
                return obj.toList
            if prop == "values":
                return obj.values
            if prop == "keys":
                return obj.keys
            if prop == "entries":
                return obj.entries
            if prop == "forEach":
                return obj.forEach
            if prop == "union":
                return obj.union
            if prop == "intersection":
                return obj.intersection
            if prop == "difference":
                return obj.difference
            if prop == "symmetricDifference":
                return obj.symmetricDifference
            if prop == "isSubsetOf":
                return obj.isSubsetOf
            if prop == "isSupersetOf":
                return obj.isSupersetOf
            if prop == "isDisjointFrom":
                return obj.isDisjointFrom
            raise SpryRuntimeError(f"Set has no property {prop!r}", node)

        if isinstance(obj, SpryWebSocket):
            if prop == "send":
                return lambda msg: obj.send(msg)
            if prop == "close":
                return lambda: obj.close()
            if prop == "onMessage":
                return lambda handler: obj.onMessage(handler)
            if prop == "connected":
                return obj.connected
            if prop == "url":
                return obj.url
            raise SpryRuntimeError(f"WebSocket has no property {prop!r}", node)

        if isinstance(obj, SpryRegex):
            if prop == "test":
                return lambda text: obj.test(str(text))
            if prop in ("match", "exec"):
                return lambda text: obj.exec(str(text))
            if prop == "replace":
                return lambda text, repl, count=1: obj.replace(str(text), str(repl), count)
            if prop == "replaceAll":
                return lambda text, repl: obj.replace(str(text), str(repl), 0)
            if prop == "split":
                return lambda text: obj.split(str(text))
            if prop in ("findAll", "findall"):
                return lambda text: obj.findAll(str(text))
            if prop == "source":
                return obj.pattern.pattern
            if prop == "flags":
                return obj.flags_str
            if prop == "lastIndex":
                return obj.lastIndex
            if prop == "global":
                return obj.global_flag
            if prop == "ignoreCase":
                return "i" in obj.flags_str
            if prop == "multiline":
                return "m" in obj.flags_str
            if prop == "sticky":
                return "y" in obj.flags_str
            if prop == "unicode":
                return "u" in obj.flags_str
            if prop == "dotAll":
                return "s" in obj.flags_str
            if prop == "hasIndices":
                return "d" in obj.flags_str
            raise SpryRuntimeError(f"Regex has no property {prop!r}", node)

        if isinstance(obj, SpryResult):
            if prop == "ok":
                return obj.ok
            if prop == "failed":
                return obj.failed
            if prop in ("error", "message"):
                return obj.error
            if prop == "value":
                return obj.value

        if isinstance(obj, SpryEnum):
            # Color.Red → the variant dict
            if prop in obj.variants:
                return getattr(obj, prop)
            raise SpryRuntimeError(f"Enum {obj.name!r} has no variant {prop!r}", node)

        if isinstance(obj, SpryInstance):
            # Check for getter first
            getter_key = f"__getter__{prop}"
            if getter_key in obj.fields:
                getter_fn = obj.fields[getter_key]
                if isinstance(getter_fn, SpryFunction):
                    bm = BoundMethod(instance=obj, fn=getter_fn)
                    return self._call_bound_method(bm, [], node)
            # Built-in instance methods
            if prop == "hasOwnProperty":
                def _instance_has_own(key: Any, _inst: SpryInstance = obj) -> bool:
                    return _owns_prop(_inst, str(key))
                return _instance_has_own
            # Instance field or method lookup
            if prop in obj.fields:
                v = obj.fields[prop]
                if isinstance(v, SpryFunction):
                    # Bind self to method
                    return BoundMethod(instance=obj, fn=v)
                return v
            # Fall back to prototype extra fields (added via Object.assign(Cls.prototype, ...))
            proto = obj.cls._prototype
            if proto is not None and prop in proto._extra_fields:
                v = proto._extra_fields[prop]
                if isinstance(v, SpryFunction):
                    return BoundMethod(instance=obj, fn=v)
                if callable(v):
                    def _proto_bound(v=v, _obj=obj, *args):
                        return v(*args)
                    return _proto_bound
                return v
            raise SpryRuntimeError(f"Instance of {obj.cls.name!r} has no attribute {prop!r}", node)

        if isinstance(obj, dict) and obj.get("__enum__"):
            # Enum variant dict — just return the variant name
            if prop == "__variant__":
                return obj["__variant__"]
            return obj.get(prop)

        if isinstance(obj, SpryFile):
            if prop == "path":
                return obj.path
            if prop == "name":
                return obj.name
            if prop == "extension":
                return obj.extension
            if prop == "stem":
                return obj.stem

        if isinstance(obj, SpryMoney):
            if prop == "amount":
                return float(obj.amount)
            if prop == "currency":
                return obj.currency

        if isinstance(obj, dict):
            # Check for getter before regular key lookup
            getter_key = f"__getter__{prop}"
            if getter_key in obj:
                getter_fn = obj[getter_key]
                if isinstance(getter_fn, SpryFunction):
                    # Inject this = obj so getters can access object properties
                    return self._call_dict_bound_method(getter_fn, obj, [], node)
                elif isinstance(getter_fn, (SpryLambda, SpryMultiLambda, BoundMethod)):
                    return self._call_value(getter_fn, [])
                elif callable(getter_fn):
                    try:
                        return getter_fn()
                    except Exception as e:
                        raise SpryRuntimeError(str(e), node)
            if prop in obj:
                val = obj[prop]
                # Bind 'this' for SpryFunction and SpryLambda stored as object methods
                if isinstance(val, SpryFunction):
                    return DictBoundMethod(obj, val)
                return val
            # Walk prototype chain for inherited properties
            proto = obj.get("__spry_proto__")
            while isinstance(proto, dict):
                getter_key_p = f"__getter__{prop}"
                if getter_key_p in proto:
                    getter_fn_p = proto[getter_key_p]
                    if isinstance(getter_fn_p, SpryFunction):
                        return self._call_dict_bound_method(getter_fn_p, obj, [], node)
                if prop in proto:
                    pval = proto[prop]
                    if isinstance(pval, SpryFunction):
                        return DictBoundMethod(obj, pval)
                    return pval
                proto = proto.get("__spry_proto__")
            # Built-in dict properties/methods
            if prop == "keys":
                return list(obj.keys())
            if prop == "values":
                return list(obj.values())
            if prop == "entries":
                return [[k, v] for k, v in obj.items()]
            if prop in ("length", "size"):
                return len(obj)
            if prop == "isEmpty":
                return len(obj) == 0
            if prop == "has":
                return lambda key: key in obj
            if prop in ("containsKey", "hasKey", "hasOwnProperty"):
                return lambda key: key in obj
            if prop == "get":
                return lambda key, default=None: obj.get(key, default)
            if prop == "set":
                def _dict_set(key: str, value: Any) -> None:
                    obj[key] = value
                return _dict_set
            if prop == "delete":
                def _dict_del(key: str) -> None:
                    obj.pop(key, None)
                return _dict_del
            if prop == "merge":
                def _dict_merge(other: dict) -> dict:
                    return {**obj, **other}
                return _dict_merge
            if prop in ("toList", "items"):
                return [[k, v] for k, v in obj.items()]
            if prop == "clone":
                return dict(obj)
            if prop == "toJSON":
                import json as _json
                return _json.dumps(obj, default=str)
            if prop == "assign":
                def _dict_assign(other: dict) -> dict:
                    obj.update(other)
                    return obj
                return _dict_assign
            # JS-compat: accessing a missing property returns None (undefined)
            return None

        if isinstance(obj, list):
            if prop == "raw" and isinstance(obj, SpryTaggedStringList):
                return obj.raw
            if prop == "length":
                return len(obj)
            if prop == "at":
                return lambda n, _obj=obj: _obj[int(n)] if -len(_obj) <= int(n) < len(_obj) else None
            if prop == "first":
                return obj[0] if obj else None
            if prop == "last":
                return obj[-1] if obj else None
            if prop == "isEmpty":
                return len(obj) == 0
            if prop == "push":
                def _list_push(*items: Any, _lst=obj) -> int:
                    _lst.extend(items)
                    return len(_lst)
                return _list_push
            if prop == "pop":
                return lambda: obj.pop() if obj else None
            if prop == "includes":
                def _list_includes(item: Any, from_idx: Any = 0, _o: list = obj) -> bool:
                    import math as _m
                    start = int(from_idx) if from_idx else 0
                    if start < 0:
                        start = max(0, len(_o) + start)
                    for x in _o[start:]:
                        if isinstance(item, float) and _m.isnan(item):
                            if isinstance(x, float) and _m.isnan(x):
                                return True
                        elif x == item:
                            return True
                    return False
                return _list_includes
            if prop == "join":
                return lambda sep="": sep.join(str(i) for i in obj)
            if prop == "slice":
                return lambda start, end=None: obj[start:end]
            if prop == "reverse":
                return list(reversed(obj))
            if prop == "sort":
                def _sort_fn(comparator: Any = None, _o: list = obj) -> list:
                    import functools
                    if comparator is None:
                        try:
                            _o.sort()
                        except TypeError:
                            pass  # can't sort mixed/incomparable elements
                    else:
                        def _cmp_wrap(a: Any, b: Any) -> int:
                            result = self._call_value(comparator, [a, b])
                            if isinstance(result, (int, float)) and result != 0:
                                return -1 if result < 0 else 1
                            return 0
                        _o.sort(key=functools.cmp_to_key(_cmp_wrap))
                    return _o
                try:
                    _sorted_default = sorted(obj)
                except TypeError:
                    _sorted_default = list(obj)
                return _CallableList(_sorted_default, _sort_fn)
            if prop == "sorted":
                def _sorted_fn(comparator: Any = None, _o: list = obj) -> list:
                    import functools
                    if comparator is None:
                        try:
                            return sorted(_o)
                        except TypeError:
                            return list(_o)
                    def _cmp_wrap2(a: Any, b: Any) -> int:
                        result = self._call_value(comparator, [a, b])
                        if isinstance(result, (int, float)) and result != 0:
                            return -1 if result < 0 else 1
                        return 0
                    return sorted(_o, key=functools.cmp_to_key(_cmp_wrap2))
                try:
                    _sorted_default2 = sorted(obj)
                except TypeError:
                    _sorted_default2 = list(obj)
                return _CallableList(_sorted_default2, _sorted_fn)
            if prop == "indexOf":
                def _list_index_of(item: Any, from_index: int = 0, _o: list = obj) -> int:
                    start = int(from_index) if from_index is not None else 0
                    if start < 0:
                        start = max(0, len(_o) + start)
                    for _i in range(start, len(_o)):
                        if _o[_i] == item:
                            return _i
                    return -1
                return _list_index_of
            if prop == "lastIndexOf":
                def _list_last_index_of(item: Any, from_index: Any = None, _o: list = obj) -> int:
                    end = len(_o) - 1 if from_index is None else int(from_index)
                    if end < 0:
                        end = len(_o) + end
                    end = min(end, len(_o) - 1)
                    for _i in range(end, -1, -1):
                        if _o[_i] == item:
                            return _i
                    return -1
                return _list_last_index_of
            if prop == "find":
                return lambda pred: next((x for x in obj if self._truthy(pred(x))), None)
            if prop == "filter":
                def _list_filter(pred: Any, _o: list = obj) -> list:
                    multi = getattr(pred, "_spry_arity", 1) > 1
                    if multi:
                        return [_x for _i, _x in enumerate(_o) if self._truthy(pred(_x, _i, _o))]
                    return [_x for _x in _o if self._truthy(pred(_x))]
                return _list_filter
            if prop == "map":
                def _list_map(fn: Any, _o: list = obj) -> list:
                    multi = getattr(fn, "_spry_arity", 1) > 1
                    results = []
                    for _idx, _x in enumerate(_o):
                        results.append(fn(_x, _idx, _o) if multi else fn(_x))
                    return results
                return _list_map
            if prop in ("every", "all"):
                def _list_every(pred: Any, _obj: list = obj) -> bool:
                    arity = getattr(pred, "_spry_arity", None)
                    for _idx, _x in enumerate(_obj):
                        _args = [_x, _idx, _obj] if (arity is not None and arity >= 2) else [_x]
                        if not self._truthy(self._call_value(pred, _args)):
                            return False
                    return True
                return _list_every
            if prop in ("some", "any"):
                def _list_some(pred: Any, _obj: list = obj) -> bool:
                    arity = getattr(pred, "_spry_arity", None)
                    for _idx, _x in enumerate(_obj):
                        _args = [_x, _idx, _obj] if (arity is not None and arity >= 2) else [_x]
                        if self._truthy(self._call_value(pred, _args)):
                            return True
                    return False
                return _list_some
            if prop == "reduce":
                def _list_reduce(first_arg: Any, second_arg: Any = _SENTINEL, _obj: Any = obj) -> Any:
                    # Support both:
                    #   reduce(fn)        — no init, use first element as seed
                    #   reduce(fn, init)  — fn first, init second (JS/SpryCode convention)
                    #   reduce(init, fn)  — init first, fn second (legacy convention)
                    if second_arg is _SENTINEL:
                        _fn = first_arg
                        if not _obj:
                            return None
                        arity = getattr(_fn, "_spry_arity", None)
                        acc = _obj[0]
                        for _idx, _item in enumerate(_obj[1:], 1):
                            _args = [acc, _item, _idx, _obj] if (arity is not None and arity >= 3) else [acc, _item]
                            acc = self._call_value(_fn, _args)
                        return acc
                    # Two args: detect which is fn by callability
                    if callable(first_arg) and not callable(second_arg):
                        _fn2, acc = first_arg, second_arg
                    elif callable(second_arg) and not callable(first_arg):
                        _fn2, acc = second_arg, first_arg
                    else:
                        _fn2, acc = first_arg, second_arg
                    arity2 = getattr(_fn2, "_spry_arity", None)
                    for _idx2, _item2 in enumerate(_obj):
                        _args2 = [acc, _item2, _idx2, _obj] if (arity2 is not None and arity2 >= 3) else [acc, _item2]
                        acc = self._call_value(_fn2, _args2)
                    return acc
                return _list_reduce
            if prop == "reduceRight":
                def _list_reduce_right(fn: Any, initial: Any = _SENTINEL) -> Any:
                    n = len(obj)
                    if initial is _SENTINEL:
                        if n == 0:
                            raise SpryRuntimeError("reduceRight of empty array with no initial value", node)
                        acc = obj[n - 1]
                        start_idx = n - 2
                    else:
                        acc = initial
                        start_idx = n - 1
                    for idx in range(start_idx, -1, -1):
                        item = obj[idx]
                        arity = getattr(fn, "_spry_arity", 1)
                        if arity > 1:
                            acc = fn(acc, item, idx, obj)
                        else:
                            acc = fn(acc, item)
                    return acc
                return _list_reduce_right
            if prop == "findIndex":
                def _find_index(pred: Any, _obj: Any = obj) -> int:
                    arity = getattr(pred, "_spry_arity", None)
                    for i, x in enumerate(_obj):
                        call_args = [x, i, _obj] if (arity is not None and arity >= 2) else [x]
                        if self._truthy(self._call_value(pred, call_args)):
                            return i
                    return -1
                return _find_index
            if prop == "concat":
                def _list_concat(*others: Any) -> list:
                    result = list(obj)
                    for other in others:
                        if isinstance(other, list):
                            result.extend(other)
                        elif isinstance(other, dict):
                            # Check Symbol.isConcatSpreadable (stored as SprySymbol key or string)
                            if _dict_has_ics(other):
                                n = int(other.get("length", 0))
                                for i in range(n):
                                    result.append(other.get(str(i)))
                            else:
                                result.append(other)
                        elif isinstance(other, SpryInstance):
                            if _inst_has_ics(other):
                                n = int(other.fields.get("length", 0))
                                for i in range(n):
                                    result.append(other.fields.get(str(i)))
                            else:
                                result.append(other)
                        else:
                            result.append(other)
                    return result
                return _list_concat
            if prop == "unshift":
                def _list_unshift(*items: Any) -> int:
                    for item in reversed(items):
                        obj.insert(0, item)
                    return len(obj)
                return _list_unshift
            if prop == "splice":
                def _list_splice(start: int, delete_count: int = 0, *items: Any) -> list:
                    removed = obj[start:start + delete_count]
                    del obj[start:start + delete_count]
                    for idx, it in enumerate(items):
                        obj.insert(start + idx, it)
                    return removed
                return _list_splice
            if prop == "fill":
                def _list_fill(val: Any, start: int = 0, end: int | None = None) -> list:
                    _end = end if end is not None else len(obj)
                    for idx in range(start, min(_end, len(obj))):
                        obj[idx] = val
                    return obj
                return _list_fill
            if prop == "chunk":
                def _list_chunk(size: int) -> list:
                    n = int(size)
                    return [obj[i:i + n] for i in range(0, len(obj), n)]
                return _list_chunk
            if prop == "take":
                return lambda n: obj[:int(n)]
            if prop == "drop":
                return lambda n: obj[int(n):]
            if prop in ("flatten", "flat_deep"):
                def _deep_flatten(lst: list) -> list:
                    result: list = []
                    for item in lst:
                        if isinstance(item, list):
                            result.extend(_deep_flatten(item))
                        else:
                            result.append(item)
                    return result
                return _deep_flatten(obj)
            if prop in ("flatMap", "flat_map"):
                return lambda fn: [item for x in obj for item in (fn(x) if isinstance(fn(x), list) else [fn(x)])]
            if prop == "sum":
                return sum(obj)
            if prop == "product":
                result = 1
                for _item in obj:
                    result *= _item
                return result
            if prop in ("avg", "average", "mean"):
                return sum(obj) / len(obj) if obj else None
            if prop == "min":
                return min(obj) if obj else None
            if prop == "max":
                return max(obj) if obj else None
            if prop == "unique":
                seen: set = set()
                return [x for x in obj if not (x in seen or seen.add(x))]  # type: ignore[func-returns-value]
            if prop == "count":
                return lambda val: obj.count(val)
            if prop in ("copy", "clone"):
                return list(obj)
            if prop == "toSet":
                return list(dict.fromkeys(obj))
            # --- Phase 9 array methods ---
            if prop == "shift":
                return obj.pop(0) if obj else None
            if prop == "findLast":
                def _find_last(pred: Any, _obj: Any = obj) -> Any:
                    arity = getattr(pred, "_spry_arity", None)
                    for i in range(len(_obj) - 1, -1, -1):
                        x = _obj[i]
                        call_args = [x, i, _obj] if (arity is not None and arity >= 2) else [x]
                        if self._truthy(self._call_value(pred, call_args)):
                            return x
                    return None
                return _find_last
            if prop == "findLastIndex":
                def _find_last_index(pred: Any, _obj: Any = obj) -> int:
                    arity = getattr(pred, "_spry_arity", None)
                    for i in range(len(_obj) - 1, -1, -1):
                        x = _obj[i]
                        call_args = [x, i, _obj] if (arity is not None and arity >= 2) else [x]
                        if self._truthy(self._call_value(pred, call_args)):
                            return i
                    return -1
                return _find_last_index
            if prop in ("toReversed", "reversed"):
                return list(reversed(obj))
            if prop in ("toSorted", "sortedBy"):
                def _to_sorted(comparator_or_key: Any = None) -> list:
                    if comparator_or_key is None:
                        return sorted(obj)
                    # Detect if it's a comparator (2-arg) or key fn (1-arg)
                    arity = getattr(comparator_or_key, "_spry_arity", None)
                    if arity is not None and arity > 1:
                        import functools
                        return sorted(obj, key=functools.cmp_to_key(comparator_or_key))
                    return sorted(obj, key=lambda x: comparator_or_key(x))
                return _to_sorted
            if prop == "toSpliced":
                def _to_spliced(start: int, delete_count: int = 0, *items: Any) -> list:
                    copy = list(obj)
                    del copy[int(start):int(start) + int(delete_count)]
                    for idx, it in enumerate(items):
                        copy.insert(int(start) + idx, it)
                    return copy
                return _to_spliced
            if prop == "with":
                def _with_index(index: int, value: Any) -> list:
                    copy = list(obj)
                    copy[int(index)] = value
                    return copy
                return _with_index
            if prop == "entries":
                return SpryIterator([[i, v] for i, v in enumerate(obj)])
            if prop == "keys":
                return SpryIterator(list(range(len(obj))))
            if prop == "values":
                return SpryIterator(list(obj))
            if prop == "flat":
                def _do_flat(lst: list, d: int) -> list:
                    result_f: list = []
                    for item in lst:
                        if isinstance(item, list) and d > 0:
                            result_f.extend(_do_flat(item, d - 1))
                        else:
                            result_f.append(item)
                    return result_f
                def _flat_with_depth(depth: Any = 1) -> list:
                    d = depth
                    if isinstance(d, float):
                        d = _MAX_FLAT_DEPTH if math.isinf(d) else int(d)
                    else:
                        d = int(d)
                    return _do_flat(obj, d)
                # Return a _CallableList so `list.flat` works as a property (depth=1)
                # AND `list.flat(depth)` works as a call
                return _CallableList(
                    _do_flat(obj, 1),
                    _flat_with_depth,
                )
            if prop == "shuffle":
                import random as _random
                copy = list(obj)
                _random.shuffle(copy)
                return copy
            if prop == "sample":
                import random as _random
                def _sample(n: int = 1) -> Any:
                    k = min(int(n), len(obj))
                    result_s = _random.sample(obj, k)
                    return result_s[0] if int(n) == 1 and k > 0 else result_s
                return _sample
            if prop == "partition":
                return lambda pred: [[x for x in obj if self._truthy(pred(x))],
                                     [x for x in obj if not self._truthy(pred(x))]]
            if prop == "groupBy":
                def _group_by(key_fn: Any) -> dict:
                    result_g: dict = {}
                    for item in obj:
                        key = key_fn(item)
                        result_g.setdefault(key, []).append(item)
                    return result_g
                return _group_by
            if prop == "tally":
                tally_result: dict = {}
                for item in obj:
                    tally_result[item] = tally_result.get(item, 0) + 1
                return tally_result
            if prop == "zip":
                # Already handled above for two-arg zip; make it also work as a method
                def _zip_with(other: list, fn: Any = None) -> list:
                    if fn is None:
                        return [[a, b] for a, b in zip(obj, other)]
                    return [fn(a, b) for a, b in zip(obj, other)]
                return _zip_with
            if prop == "intersect":
                return lambda other: [x for x in obj if x in other]
            if prop == "difference":
                return lambda other: [x for x in obj if x not in other]
            if prop == "union":
                return lambda other: list(dict.fromkeys(obj + [x for x in other if x not in obj]))
            # --- Phase 11 list methods ---
            if prop == "compact":
                return [x for x in obj if x is not None and x is not False and x != 0 and x != "" and x != []]
            if prop == "countBy":
                def _count_by(key_fn: Any) -> dict:
                    result_cb: dict = {}
                    for item in obj:
                        k = key_fn(item)
                        result_cb[k] = result_cb.get(k, 0) + 1
                    return result_cb
                return _count_by
            if prop == "minBy":
                def _min_by(key_fn: Any) -> Any:
                    if not obj:
                        return None
                    return min(obj, key=key_fn)
                return _min_by
            if prop == "maxBy":
                def _max_by(key_fn: Any) -> Any:
                    if not obj:
                        return None
                    return max(obj, key=key_fn)
                return _max_by
            if prop == "sumBy":
                def _sum_by(key_fn: Any) -> Any:
                    return sum(key_fn(x) for x in obj)
                return _sum_by
            if prop == "takeWhile":
                def _take_while(pred: Any) -> list:
                    result_tw: list = []
                    for item in obj:
                        if not self._truthy(pred(item)):
                            break
                        result_tw.append(item)
                    return result_tw
                return _take_while
            if prop == "dropWhile":
                def _drop_while(pred: Any) -> list:
                    result_dw = list(obj)
                    while result_dw and self._truthy(pred(result_dw[0])):
                        result_dw.pop(0)
                    return result_dw
                return _drop_while
            if prop == "copyWithin":
                def _copy_within(target: int, start: int = 0, end: int | None = None, _obj: list = obj) -> list:
                    n = len(_obj)
                    t = int(target) % n if n else 0
                    s = int(start) % n if n else 0
                    e = int(end) if end is not None else n
                    if e < 0:
                        e = max(0, n + e)
                    result_cw = list(_obj)
                    chunk = result_cw[s:e]
                    for i, v in enumerate(chunk):
                        if t + i >= n:
                            break
                        result_cw[t + i] = v
                    return result_cw
                return _copy_within
            if prop == "group":
                def _group(fn: Any, _obj: list = obj) -> dict:
                    result_g: dict = {}
                    for item in _obj:
                        k = fn(item)
                        if k not in result_g:
                            result_g[k] = []
                        result_g[k].append(item)
                    return result_g
                return _group
            if prop == "forEach":
                def _list_foreach(fn: Any, _o: list = obj) -> None:
                    multi = getattr(fn, "_spry_arity", 1) > 1
                    for _idx, _x in enumerate(_o):
                        fn(_x, _idx, _o) if multi else fn(_x)
                return _list_foreach
            if prop == "toArray":
                return list(obj)  # plain list — toArray() returns itself as a new list

        if isinstance(obj, str):
            if prop == "length":
                return len(obj)
            if prop in ("upper", "toUpper", "toUpperCase"):
                return obj.upper()
            if prop in ("lower", "toLower", "toLowerCase"):
                return obj.lower()
            if prop == "trim":
                return obj.strip()
            if prop == "trimStart":
                return obj.lstrip()
            if prop == "trimEnd":
                return obj.rstrip()
            if prop == "trimLeft":
                return obj.lstrip()
            if prop == "trimRight":
                return obj.rstrip()
            if prop == "split":
                def _str_split(sep: Any = " ", limit: Any = None, _obj: str = obj) -> list:
                    if isinstance(sep, SpryRegex):
                        import re as _re
                        result = _re.split(sep.pattern.pattern, _obj)
                    elif isinstance(sep, str):
                        if sep == "":
                            # JS/TS: "hello".split("") → ['h', 'e', 'l', 'l', 'o']
                            result = list(_obj)
                        else:
                            result = _obj.split(sep)
                    else:
                        result = _obj.split(str(sep))
                    if limit is not None:
                        result = result[:int(limit)]
                    return result
                return _str_split
            if prop == "contains":
                return lambda sub: sub in obj
            if prop == "includes":
                def _str_includes(sub: Any, position: Any = None, _obj: str = obj) -> bool:
                    pos = int(position) if position is not None else 0
                    return str(sub) in _obj[pos:]
                return _str_includes
            if prop == "startsWith":
                def _str_startswith(prefix: Any, position: Any = None, _obj: str = obj) -> bool:
                    pos = int(position) if position is not None else 0
                    return _obj[pos:].startswith(str(prefix))
                return _str_startswith
            if prop == "endsWith":
                def _str_endswith(suffix: Any, length: Any = None, _obj: str = obj) -> bool:
                    s = _obj[:int(length)] if length is not None else _obj
                    return s.endswith(str(suffix))
                return _str_endswith
            if prop == "replace":
                def _str_replace(old: Any, new: Any, _obj: str = obj) -> str:
                    import re as _re
                    if isinstance(old, SpryRegex):
                        _count = 0 if old.global_flag else 1
                        if callable(new):
                            return old.pattern.sub(lambda m: str(new(m.group(0))), _obj, count=_count)
                        return old.pattern.sub(str(new), _obj, count=_count)
                    if callable(new):
                        idx = _obj.find(str(old))
                        if idx == -1:
                            return _obj
                        matched = _obj[idx:idx + len(str(old))]
                        return _obj[:idx] + str(new(matched)) + _obj[idx + len(str(old)):]
                    return _obj.replace(str(old), str(new), 1)
                return _str_replace
            if prop == "replaceAll":
                def _str_replace_all(old: Any, new: Any, _obj: str = obj) -> str:
                    import re as _re
                    if isinstance(old, SpryRegex):
                        if callable(new):
                            return old.pattern.sub(lambda m: str(new(m.group(0))), _obj)
                        return old.pattern.sub(str(new), _obj)
                    if callable(new):
                        result = ""
                        remaining = _obj
                        search = str(old)
                        while True:
                            idx = remaining.find(search)
                            if idx == -1:
                                result += remaining
                                break
                            result += remaining[:idx] + str(new(search))
                            remaining = remaining[idx + len(search):]
                        return result
                    return _obj.replace(str(old), str(new))
                return _str_replace_all
            if prop == "slice":
                return lambda start, end=None: obj[start:end]
            if prop == "isEmpty":
                return len(obj) == 0
            if prop == "isNotEmpty":
                return len(obj) > 0
            if prop == "indexOf":
                def _str_index_of(sub: str, from_index: int = 0, _s: str = obj) -> int:
                    start = max(0, int(from_index)) if from_index is not None else 0
                    return _s.find(str(sub), start)
                return _str_index_of
            if prop == "lastIndexOf":
                def _str_last_index_of(sub: str, from_index: Any = None, _s: str = obj) -> int:
                    if from_index is None:
                        return _s.rfind(str(sub))
                    end = int(from_index) + len(str(sub))
                    return _s.rfind(str(sub), 0, end)
                return _str_last_index_of
            if prop == "at":
                def _str_at(n: Any, _s: str = obj) -> Any:
                    n = int(n)
                    if n < 0:
                        n = len(_s) + n
                    return _s[n] if 0 <= n < len(_s) else None
                return _str_at
            if prop == "localeCompare":
                def _locale_compare(other: Any, locale: Any = None, options: Any = None, _s: str = obj) -> int:
                    o = str(other)
                    if _s < o:
                        return -1
                    if _s > o:
                        return 1
                    return 0
                return _locale_compare
            if prop == "charAt":
                return lambda n: obj[int(n)] if 0 <= int(n) < len(obj) else ""
            if prop in ("padStart", "padLeft"):
                return lambda width, ch=" ": obj.rjust(width, ch)
            if prop in ("padEnd", "padRight"):
                return lambda width, ch=" ": obj.ljust(width, ch)
            if prop == "repeat":
                return lambda n: obj * n
            if prop == "concat":
                return lambda *args: obj + "".join(str(a) for a in args)
            if prop == "chars":
                return list(obj)
            if prop == "lines":
                return obj.splitlines()
            if prop == "substring":
                return lambda start, end=None: obj[int(start):int(end)] if end is not None else obj[int(start):]
            if prop == "substr":
                def _str_substr(start: Any, length: Any = None, _obj: str = obj) -> str:
                    s = int(start)
                    if length is None:
                        return _obj[s:]
                    return _obj[s:s + int(length)]
                return _str_substr
            if prop == "match":
                import re as _re
                def _str_match(pattern: Any, _obj: str = obj) -> Any:
                    if isinstance(pattern, SpryRegex):
                        if pattern.global_flag:
                            # global match: return all full-match strings (JS behaviour)
                            matches = list(pattern.pattern.finditer(_obj))
                            if not matches:
                                return None
                            all_groups = [m.group(0) for m in matches]
                            return SpryRegexMatch(all_groups, matches[0].start(), _obj)
                        else:
                            # non-global: return first match with all capture groups + named groups
                            m = pattern.pattern.search(_obj)
                            if m is None:
                                return None
                            groups = [m.group(0)] + list(m.groups())
                            return SpryRegexMatch(groups, m.start(), _obj,
                                                  named_groups=m.groupdict() or {})
                    # Plain string pattern: use findall to return all matches (legacy behaviour)
                    pat, flags, _g = _parse_regex_pattern(str(pattern))
                    try:
                        return _re.findall(pat, _obj, flags) or None
                    except _re.error:
                        return None
                return _str_match
            if prop == "matchAll":
                import re as _re
                def _str_matchall(pattern: Any, _obj: str = obj) -> list:
                    if isinstance(pattern, SpryRegex):
                        return [SpryRegexMatch([m.group(), *m.groups()], m.start(), _obj,
                                               named_groups=m.groupdict() or {})
                                for m in pattern.pattern.finditer(_obj)]
                    pat, flags, _g = _parse_regex_pattern(str(pattern))
                    try:
                        compiled = _re.compile(pat, flags)
                    except _re.error:
                        return []
                    return [SpryRegexMatch([m.group(), *m.groups()], m.start(), _obj,
                                           named_groups=m.groupdict() or {})
                            for m in compiled.finditer(_obj)]
                return _str_matchall
            if prop == "search":
                import re as _re
                def _str_search(pattern: Any, _obj: str = obj) -> int:
                    if isinstance(pattern, SpryRegex):
                        m = pattern.pattern.search(_obj)
                        return m.start() if m else -1
                    pat, flags, _g = _parse_regex_pattern(str(pattern))
                    m = _re.search(pat, _obj, flags)
                    return m.start() if m else -1
                return _str_search
            if prop in ("toNumber", "toFloat", "toInt", "parseInt", "parseFloat"):
                try:
                    return int(obj) if "." not in obj else float(obj)
                except ValueError:
                    return None
            if prop in ("toString", "toStr"):
                return obj
            if prop == "normalize":
                import unicodedata
                return lambda form="NFC": unicodedata.normalize(form, obj)
            if prop == "byteLength":
                return len(obj.encode("utf-8"))
            # --- Phase 9 string methods ---
            if prop in ("toCamelCase", "camelCase"):
                import re as _re
                words = _re.sub(r"[\s_\-]+", " ", obj).strip().split()
                return words[0].lower() + "".join(w.capitalize() for w in words[1:]) if words else ""
            if prop in ("toSnakeCase", "snakeCase"):
                import re as _re
                s = _re.sub(r"[\s\-]+", "_", obj)
                s = _re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
                s = _re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
                return s.lower()
            if prop in ("toKebabCase", "kebabCase"):
                import re as _re
                s = _re.sub(r"[\s_]+", "-", obj)
                s = _re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", s)
                s = _re.sub(r"([a-z\d])([A-Z])", r"\1-\2", s)
                return s.lower()
            if prop in ("toPascalCase", "pascalCase"):
                import re as _re
                words = _re.sub(r"[\s_\-]+", " ", obj).strip().split()
                return "".join(w.capitalize() for w in words)
            if prop in ("toTitleCase", "titleCase"):
                return obj.title()
            if prop == "toBase64":
                import base64 as _b64
                return _b64.b64encode(obj.encode("utf-8")).decode("ascii")
            if prop == "fromBase64":
                import base64 as _b64
                try:
                    return _b64.b64decode(obj).decode("utf-8")
                except Exception:
                    return None
            if prop == "levenshtein":
                def _levenshtein(other: str, _s: str = obj) -> int:
                    s1, s2 = _s, str(other)
                    m, n = len(s1), len(s2)
                    dp = list(range(n + 1))
                    for i in range(1, m + 1):
                        prev = dp[0]
                        dp[0] = i
                        for j in range(1, n + 1):
                            temp = dp[j]
                            dp[j] = (prev if s1[i-1] == s2[j-1]
                                     else 1 + min(prev, dp[j], dp[j-1]))
                            prev = temp
                    return dp[n]
                return _levenshtein
            if prop == "count":
                return lambda sub: obj.count(str(sub))
            if prop == "truncate":
                def _truncate(max_len: int, suffix: str = "...") -> str:
                    n = int(max_len)
                    return obj if len(obj) <= n else obj[:n - len(suffix)] + suffix
                return _truncate
            if prop == "wrap":
                import textwrap as _textwrap
                return lambda width: _textwrap.fill(obj, int(width))
            if prop == "isNumeric":
                try:
                    float(obj)
                    return True
                except ValueError:
                    return False
            if prop == "isAlpha":
                return obj.isalpha()
            if prop in ("isAlphaNum", "isAlphanumeric"):
                return obj.isalnum()
            if prop == "isLower":
                return obj.islower()
            if prop == "isUpper":
                return obj.isupper()
            if prop == "center":
                return lambda width, fill=" ": obj.center(int(width), fill)
            if prop == "encode":
                return lambda enc="utf-8": list(obj.encode(str(enc)))
            if prop == "format":
                return lambda *args, **kwargs: obj.format(*args, **kwargs)
            # --- Phase 11 string methods ---
            if prop == "charCodeAt":
                return lambda n=0, _obj=obj: ord(_obj[int(n)]) if 0 <= int(n) < len(_obj) else None
            if prop == "codePointAt":
                return lambda n=0, _obj=obj: ord(_obj[int(n)]) if 0 <= int(n) < len(_obj) else None
            if prop == "isWellFormed":
                # Python strings are always well-formed Unicode sequences
                return lambda _obj=obj: True
            if prop == "toWellFormed":
                # Python strings are already well-formed; return unchanged
                return lambda _obj=obj: _obj
            if prop == "bytes":
                return lambda _obj=obj: list(_obj.encode("utf-8"))
            if prop == "values":
                return lambda _obj=obj: SpryIterator(list(_obj))
            if prop == "chars":
                return lambda _obj=obj: list(_obj)
            if prop == "replaceRegex":
                def _replace_regex(pattern: Any, repl: str = "", _obj: str = obj) -> str:
                    if isinstance(pattern, SpryRegex):
                        return pattern.pattern.sub(str(repl), _obj)
                    pat, flags, _g = _parse_regex_pattern(str(pattern))
                    return re.sub(pat, str(repl), _obj, flags=flags)
                return _replace_regex

        if isinstance(obj, (int, float)):
            if prop in ("toFixed", "toFixed"):
                return lambda digits=0: f"{obj:.{int(digits)}f}"
            if prop == "toPrecision":
                def _to_precision(digits: int = 6, _obj: Any = obj) -> str:
                    d = int(digits)
                    # Use Python's f-string with precision, then trim trailing zeros
                    # to match JS toPrecision: preserves trailing zeros
                    result = f"{float(_obj):.{d}g}"
                    # If the result has no decimal, add zeros for the requested precision
                    if "e" not in result and "E" not in result and "." not in result:
                        if d > len(result.lstrip("-")):
                            result = result + "." + "0" * (d - len(result.lstrip("-")))
                    elif "e" not in result and "E" not in result:
                        int_part, frac_part = result.split(".")
                        int_digits = len(int_part.lstrip("-"))
                        needed_frac = d - int_digits
                        if needed_frac > len(frac_part):
                            result = result + "0" * (needed_frac - len(frac_part))
                    return result
                return _to_precision
            if prop in ("toStr", "toString"):
                def _num_to_str(base: int = 10, _n: Any = obj) -> str:
                    is_integer_float = isinstance(_n, float) and _n == int(_n)
                    n = int(_n) if is_integer_float else _n
                    if base == 10:
                        return str(int(n)) if isinstance(n, float) and n == int(n) else str(n)
                    if base == 16:
                        return format(int(n), 'x')
                    if base == 2:
                        return format(int(n), 'b')
                    if base == 8:
                        return format(int(n), 'o')
                    # Generic: convert to given base
                    if int(n) == 0:
                        return "0"
                    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
                    result_s, num = "", abs(int(n))
                    while num:
                        result_s = digits[num % base] + result_s
                        num //= base
                    return ("-" if int(n) < 0 else "") + result_s
                return _num_to_str
            if prop in ("toInt", "floor"):
                return int(obj)
            if prop in ("toFloat",):
                return float(obj)
            if prop == "abs":
                return abs(obj)
            if prop == "isNaN":
                return isinstance(obj, float) and (obj != obj)
            if prop == "isFinite":
                return not (isinstance(obj, float) and (obj != obj or obj == float("inf") or obj == float("-inf")))
            if prop in ("ceil",):
                return math.ceil(obj)
            if prop in ("round",):
                return round(obj)
            if prop == "toExponential":
                def _to_exp(digits: Any = None, _obj: Any = obj) -> str:
                    import re as _re
                    fval = float(_obj)
                    if digits is None:
                        # No-arg: minimum digits needed (JS semantics) via repr shortest form
                        if fval == 0.0:
                            return "0e+0"
                        _sign = "-" if fval < 0 else ""
                        _r = repr(abs(fval))
                        if "e" in _r:
                            _mantissa_s, _exp_s = _r.split("e")
                            _exp_n = int(_exp_s)
                        else:
                            _int_p, _frac_p = _r.split(".") if "." in _r else (_r, "")
                            if _int_p == "0":
                                _leading = len(_frac_p) - len(_frac_p.lstrip("0"))
                                _exp_n = -(_leading + 1)
                                _sig = _frac_p.lstrip("0")
                            else:
                                _exp_n = len(_int_p) - 1
                                _sig = (_int_p + _frac_p).rstrip("0")
                            _mantissa_s = _sig[0] + ("." + _sig[1:] if len(_sig) > 1 else "")
                        _esign = "+" if _exp_n >= 0 else "-"
                        return f"{_sign}{_mantissa_s}e{_esign}{abs(_exp_n)}"
                    else:
                        raw = f"{fval:.{int(digits)}e}"
                    # JS uses e+4 not e+04 — strip leading zero from exponent
                    return _re.sub(r"e([+-])0+(\d)", lambda m: f"e{m.group(1)}{m.group(2)}", raw)
                return _to_exp
            if prop == "sign":
                return 1 if obj > 0 else (-1 if obj < 0 else 0)
            if prop == "trunc":
                return math.trunc(obj)
            if prop == "clamp":
                return lambda lo, hi: max(lo, min(hi, obj))
            if prop in ("toRadians", "rad"):
                return math.radians(float(obj))
            if prop in ("toDegrees", "deg"):
                return math.degrees(float(obj))
            # --- Phase 10 number formatting ---
            if prop == "toLocaleString":
                def _to_locale_string(locale: Any = None, _obj: Any = obj) -> str:
                    v = float(_obj)
                    if v == int(v):
                        return f"{int(v):,}"
                    return f"{v:,}"
                return _to_locale_string
            if prop == "toPercent":
                return lambda decimals=2, _obj=obj: f"{float(_obj) * 100:.{int(decimals)}f}%"
            if prop == "toCurrency":
                def _to_currency(symbol: str = "$", decimals: int = 2, _obj: Any = obj) -> str:
                    return f"{symbol}{float(_obj):,.{int(decimals)}f}"
                return _to_currency
            # --- Phase 11 number methods ---
            if prop == "toHex":
                return lambda prefix=True, _obj=obj: (
                    ("0x" if prefix else "") + format(int(_obj), "x")
                )
            if prop == "toBinary":
                return lambda prefix=True, _obj=obj: (
                    ("0b" if prefix else "") + format(int(_obj), "b")
                )
            if prop == "toOctal":
                return lambda prefix=True, _obj=obj: (
                    ("0o" if prefix else "") + format(int(_obj), "o")
                )
            if prop == "toOrdinal":
                def _to_ordinal(_obj: Any = obj) -> str:
                    n = int(_obj)
                    abs_n = abs(n)
                    if 11 <= abs_n % 100 <= 13:
                        suffix = "th"
                    else:
                        suffix = {1: "st", 2: "nd", 3: "rd"}.get(abs_n % 10, "th")
                    return f"{n}{suffix}"
                return _to_ordinal

        if isinstance(obj, SpryClass):
            if prop == "new":
                return lambda *args: self._construct_class(obj, list(args), node)
            if prop == "name":
                return obj.name
            if prop == "prototype":
                return obj.prototype
            # Walk the class hierarchy for static members
            cls_iter: SpryClass | None = obj
            while cls_iter is not None:
                # Check mutable static field storage first
                if prop in cls_iter._static_fields:
                    return cls_iter._static_fields[prop]
                # Look up static methods and properties from class body
                cls_env = cls_iter.closure.child()
                for stmt in cls_iter.body.body:  # type: ignore[union-attr]
                    if isinstance(stmt, FunctionDeclaration) and stmt.name == prop:
                        return SpryFunction(
                            name=stmt.name,
                            params=stmt.params,
                            body=stmt.body,  # type: ignore
                            closure=cls_env,
                            defaults=stmt.defaults,
                            rest_param=stmt.rest_param,
                        )
                    # Static let/var declarations
                    if isinstance(stmt, (LetDeclaration, VarDeclaration)) and stmt.name == prop:
                        val = self._eval(stmt.value, cls_env) if stmt.value is not None else None
                        # Seed into _static_fields for future mutation
                        if prop not in cls_iter._static_fields:
                            cls_iter._static_fields[prop] = val
                        return cls_iter._static_fields[prop]
                    # Static getter: GetterDeclaration with name __static__<prop>
                    if isinstance(stmt, GetterDeclaration) and stmt.name == f"__static__{prop}":
                        getter_fn = SpryFunction(
                            name=f"get_{prop}",
                            params=[],
                            body=stmt.body,  # type: ignore
                            closure=cls_env,
                            defaults={},
                            rest_param=None,
                        )
                        return self._call_function(getter_fn, [], node)
                # Walk to superclass
                if cls_iter.superclass:
                    parent = (
                        cls_iter.superclass
                        if isinstance(cls_iter.superclass, SpryClass)
                        else self._eval(cls_iter.superclass, cls_iter.closure)  # type: ignore[arg-type]
                    )
                    if isinstance(parent, SpryClass):
                        cls_iter = parent
                    else:
                        break
                else:
                    break
            raise SpryRuntimeError(f"Class {obj.name!r} has no static member {prop!r}", node)

        if isinstance(obj, SpryStruct):
            if prop == "new":
                return lambda *args: obj.create(list(args))
            if prop == "name":
                return obj.name
            raise SpryRuntimeError(f"Struct {obj.name!r} has no property {prop!r}", node)

        if isinstance(obj, SpryPromise):
            if prop == "status":
                return obj.status
            if prop == "value":
                return obj._value
            if prop == "error":
                return obj._error
            if prop in ("then", "catch", "finally"):
                # Return a wrapper that invokes SpryLambda callbacks through the interpreter
                _interp = self
                _promise = obj
                if prop == "then":
                    def _then(on_fulfilled: Any = None, on_rejected: Any = None) -> SpryPromise:
                        if _promise._settled and on_fulfilled is not None:
                            try:
                                return SpryPromise(value=_interp._call_value(on_fulfilled, [_promise._value]))
                            except Exception as e:
                                return SpryPromise(error=str(e))
                        if not _promise._settled and on_rejected is not None:
                            try:
                                return SpryPromise(value=_interp._call_value(on_rejected, [_promise._error]))
                            except Exception as e:
                                return SpryPromise(error=str(e))
                        return _promise
                    return _then
                if prop == "catch":
                    def _catch(on_rejected: Any) -> SpryPromise:
                        if not _promise._settled and on_rejected is not None:
                            try:
                                return SpryPromise(value=_interp._call_value(on_rejected, [_promise._error]))
                            except Exception as e:
                                return SpryPromise(error=str(e))
                        return _promise
                    return _catch
                if prop == "finally":
                    def _finally(fn: Any) -> SpryPromise:
                        if fn is not None:
                            try:
                                _interp._call_value(fn, [])
                            except Exception:
                                pass
                        return _promise
                    return _finally
            if prop in ("state",):
                return "fulfilled" if obj._settled else "rejected"
            if prop in ("reason",):
                return obj._error
            raise SpryRuntimeError(f"Promise has no property {prop!r}", node)

        if isinstance(obj, SpryGenerator):
            if prop == "next":
                return obj.next
            if prop == "return":
                return obj.spry_return
            if prop == "throw":
                return obj.spry_throw
            if prop == "done":
                return obj._done
            if prop == "toArray":
                obj._materialise()
                return lambda: list(obj._collected)
            if prop == "take":
                def _gen_take(n: int, _g: SpryGenerator = obj) -> list:
                    _g._materialise()
                    return list(_g._collected[:int(n)])  # type: ignore[index]
                return _gen_take
            if prop == "drop":
                def _gen_drop(n: int, _g: SpryGenerator = obj) -> list:
                    _g._materialise()
                    return list(_g._collected[int(n):])  # type: ignore[index]
                return _gen_drop
            if prop == "map":
                def _gen_map(fn: Any, _g: SpryGenerator = obj) -> list:
                    _g._materialise()
                    return [fn(v) for v in _g._collected]  # type: ignore[union-attr]
                return _gen_map
            if prop == "filter":
                def _gen_filter(fn: Any, _g: SpryGenerator = obj) -> list:
                    _g._materialise()
                    return [v for v in _g._collected if self._truthy(fn(v))]  # type: ignore[union-attr]
                return _gen_filter
            if prop == "forEach":
                def _gen_foreach(fn: Any, _g: SpryGenerator = obj) -> None:
                    _g._materialise()
                    for v in _g._collected:  # type: ignore[union-attr]
                        fn(v)
                return _gen_foreach
            if prop == "reduce":
                def _gen_reduce(fn: Any, init: Any = None, _g: SpryGenerator = obj) -> Any:
                    _g._materialise()
                    acc = init
                    for v in _g._collected:  # type: ignore[union-attr]
                        acc = fn(acc, v)
                    return acc
                return _gen_reduce
            if prop == "length" or prop == "size":
                obj._materialise()
                return len(obj._collected)  # type: ignore[arg-type]
            raise SpryRuntimeError(f"Generator has no property {prop!r}", node)

        if isinstance(obj, SpryIterator):
            if prop == "next":
                return lambda _it=obj: _it.next()
            if prop in ("toList", "toArray"):
                return lambda _it=obj: _it.toArray()
            if prop in ("values", "entries", "keys"):
                return lambda _it=obj: _it  # iterators are already iterators
            # Iterator helper methods — inject interpreter call_fn so lambdas work
            _call_fn = self._call_value
            if prop == "filter":
                def _iter_filter(fn: Any, _it: SpryIterator = obj) -> SpryIterator:
                    result = []
                    for _item in _it._items[_it._index:]:
                        if _call_fn(fn, [_item]):
                            result.append(_item)
                    return SpryIterator(result, _call_fn)
                return _iter_filter
            if prop == "map":
                def _iter_map(fn: Any, _it: SpryIterator = obj) -> SpryIterator:
                    return SpryIterator(
                        [_call_fn(fn, [_item]) for _item in _it._items[_it._index:]],
                        _call_fn,
                    )
                return _iter_map
            if prop == "take":
                def _iter_take(n: Any, _it: SpryIterator = obj) -> SpryIterator:
                    return SpryIterator(_it._items[_it._index:_it._index + int(n)], _call_fn)
                return _iter_take
            if prop == "drop":
                def _iter_drop(n: Any, _it: SpryIterator = obj) -> SpryIterator:
                    return SpryIterator(_it._items[_it._index + int(n):], _call_fn)
                return _iter_drop
            if prop == "flatMap":
                def _iter_flatmap(fn: Any, _it: SpryIterator = obj) -> SpryIterator:
                    result: list = []
                    for _item in _it._items[_it._index:]:
                        _val = _call_fn(fn, [_item])
                        if isinstance(_val, (list, SpryIterator)):
                            result.extend(_val)
                        else:
                            result.append(_val)
                    return SpryIterator(result, _call_fn)
                return _iter_flatmap
            if prop == "forEach":
                def _iter_foreach(fn: Any, _it: SpryIterator = obj) -> None:
                    for _item in _it._items[_it._index:]:
                        _call_fn(fn, [_item])
                return _iter_foreach
            if prop == "reduce":
                def _iter_reduce(fn: Any, initial: Any = _MISSING, _it: SpryIterator = obj) -> Any:
                    items = _it._items[_it._index:]
                    has_initial = initial is not _MISSING
                    if not items:
                        if not has_initial:
                            raise SpryRuntimeError("reduce of empty iterator with no initial value", node)
                        return initial
                    acc = initial if has_initial else items[0]
                    start = 0 if has_initial else 1
                    for _item in items[start:]:
                        acc = _call_fn(fn, [acc, _item])
                    return acc
                return _iter_reduce
            if prop == "some":
                def _iter_some(fn: Any, _it: SpryIterator = obj) -> bool:
                    for _item in _it._items[_it._index:]:
                        if _call_fn(fn, [_item]):
                            return True
                    return False
                return _iter_some
            if prop == "every":
                def _iter_every(fn: Any, _it: SpryIterator = obj) -> bool:
                    for _item in _it._items[_it._index:]:
                        if not _call_fn(fn, [_item]):
                            return False
                    return True
                return _iter_every
            if prop == "find":
                def _iter_find(fn: Any, _it: SpryIterator = obj) -> Any:
                    for _item in _it._items[_it._index:]:
                        if _call_fn(fn, [_item]):
                            return _item
                    return None
                return _iter_find
            if prop == "length" or prop == "size":
                return len(obj._items) - obj._index
            raise SpryRuntimeError(f"Iterator has no property {prop!r}", node)

        if isinstance(obj, SpryProxy):
            return obj._spry_get_prop(prop)

        if isinstance(obj, (_ObjectPrototype, _ObjectPrototypeHasOwnProperty, _ObjectPrototypeToString)):
            return obj._spry_get_prop(prop)

        # SpryTypedArray — callback methods need access to self._call_value
        if isinstance(obj, SpryTypedArray):
            _call_fn = self._call_value
            if prop == "map":
                def _ta_map(fn: Any, _arr: SpryTypedArray = obj,
                            _cf: Any = _call_fn) -> SpryTypedArray:
                    result = SpryTypedArray(_arr._type_name, _arr._element_size, len(_arr._data))
                    result._data = [_arr._coerce(_cf(fn, [v, i, _arr]))
                                    for i, v in enumerate(_arr._data)]
                    return result
                return _ta_map
            if prop == "filter":
                def _ta_filter(fn: Any, _arr: SpryTypedArray = obj,
                               _cf: Any = _call_fn) -> SpryTypedArray:
                    items = [v for i, v in enumerate(_arr._data) if _cf(fn, [v, i, _arr])]
                    return SpryTypedArray(_arr._type_name, _arr._element_size, items)
                return _ta_filter
            if prop == "find":
                def _ta_find(fn: Any, _arr: SpryTypedArray = obj,
                             _cf: Any = _call_fn) -> Any:
                    for i, v in enumerate(_arr._data):
                        if _cf(fn, [v, i, _arr]):
                            return v
                    return SPRY_UNDEFINED
                return _ta_find
            if prop == "findIndex":
                def _ta_findIndex(fn: Any, _arr: SpryTypedArray = obj,
                                  _cf: Any = _call_fn) -> int:
                    for i, v in enumerate(_arr._data):
                        if _cf(fn, [v, i, _arr]):
                            return i
                    return -1
                return _ta_findIndex
            if prop == "findLast":
                def _ta_findLast(fn: Any, _arr: SpryTypedArray = obj,
                                 _cf: Any = _call_fn) -> Any:
                    for i in range(len(_arr._data) - 1, -1, -1):
                        if _cf(fn, [_arr._data[i], i, _arr]):
                            return _arr._data[i]
                    return SPRY_UNDEFINED
                return _ta_findLast
            if prop == "findLastIndex":
                def _ta_findLastIndex(fn: Any, _arr: SpryTypedArray = obj,
                                      _cf: Any = _call_fn) -> int:
                    for i in range(len(_arr._data) - 1, -1, -1):
                        if _cf(fn, [_arr._data[i], i, _arr]):
                            return i
                    return -1
                return _ta_findLastIndex
            if prop == "every":
                def _ta_every(fn: Any, _arr: SpryTypedArray = obj,
                              _cf: Any = _call_fn) -> bool:
                    return all(bool(_cf(fn, [v, i, _arr])) for i, v in enumerate(_arr._data))
                return _ta_every
            if prop == "some":
                def _ta_some(fn: Any, _arr: SpryTypedArray = obj,
                             _cf: Any = _call_fn) -> bool:
                    return any(bool(_cf(fn, [v, i, _arr])) for i, v in enumerate(_arr._data))
                return _ta_some
            if prop == "forEach":
                def _ta_forEach(fn: Any, _arr: SpryTypedArray = obj,
                                _cf: Any = _call_fn) -> None:
                    for i, v in enumerate(_arr._data):
                        _cf(fn, [v, i, _arr])
                return _ta_forEach
            if prop == "reduce":
                _TA_MISSING = object()

                def _ta_reduce(fn: Any, initial: Any = _TA_MISSING, _arr: SpryTypedArray = obj,
                               _cf: Any = _call_fn, _m: Any = _TA_MISSING) -> Any:
                    data = _arr._data
                    if not data:
                        if initial is _m:
                            raise SpryRuntimeError(
                                f"reduce of empty typed array with no initial value", node)
                        return initial
                    acc = initial if initial is not _m else data[0]
                    start = 0 if initial is not _m else 1
                    for i in range(start, len(data)):
                        acc = _cf(fn, [acc, data[i], i, _arr])
                    return acc
                return _ta_reduce
            if prop == "reduceRight":
                _TA_MISSING2 = object()

                def _ta_reduceRight(fn: Any, initial: Any = _TA_MISSING2,
                                    _arr: SpryTypedArray = obj,
                                    _cf: Any = _call_fn, _m: Any = _TA_MISSING2) -> Any:
                    data = _arr._data
                    if not data:
                        if initial is _m:
                            raise SpryRuntimeError(
                                f"reduceRight of empty typed array with no initial value", node)
                        return initial
                    acc = initial if initial is not _m else data[-1]
                    start = len(data) - 2 if initial is _m else len(data) - 1
                    for i in range(start, -1, -1):
                        acc = _cf(fn, [acc, data[i], i, _arr])
                    return acc
                return _ta_reduceRight
            if prop == "sort":
                import functools as _ft

                def _ta_sort(fn: Any = None, _arr: SpryTypedArray = obj,
                             _cf: Any = _call_fn) -> SpryTypedArray:
                    if fn is None:
                        _arr._data.sort()
                    else:
                        def _cmp(a: Any, b: Any) -> int:
                            r = _cf(fn, [a, b])
                            return -1 if r < 0 else (1 if r > 0 else 0)
                        _arr._data.sort(key=_ft.cmp_to_key(_cmp))
                    return _arr
                return _ta_sort
            # Fall through to _spry_get_prop for pure methods
            return obj._spry_get_prop(prop)

        if isinstance(obj, (SpryURL, SpryURLSearchParams, SpryArrayBuffer, SprySharedArrayBuffer,
                             SpryDataView,
                             SpryTextEncoder, SpryTextDecoder,
                             SpryAbortController, SpryAbortSignal,
                             _AtomicsNamespace)):
            return obj._spry_get_prop(prop)

        if isinstance(obj, SpryErrorObject):
            return obj._spry_get_prop(prop)

        if isinstance(obj, (SpryBlob, SpryHeaders, SpryFormData,
                             SpryRequest, SpryResponse,
                             SpryEvent, SpryEventTarget,
                             SpryReadableStream, SpryWritableStream, SpryTransformStream,
                             _ReadableStreamDefaultReader, _WritableStreamDefaultWriter,
                             _ReadableStreamController, _TransformStreamDefaultController,
                             _CompressionStreamImpl,
                             SpryBroadcastChannel, SpryMessageChannel, SpryMessagePort,
                             _NavigatorNamespace, _SubtleCryptoNamespace,
                             SpryQueue, SpryChannel, SpryCircuitBreaker,
                             SpryDebouncedFn)):
            return obj._spry_get_prop(prop)

        if isinstance(obj, (SpryFunction, SpryLambda, SpryMultiLambda, BoundMethod)):
            if prop == "bind":
                def _fn_bind(this_arg: Any, *bound_args: Any, _fn=obj) -> Any:
                    def _bound(*call_args: Any) -> Any:
                        all_args = list(bound_args) + list(call_args)
                        if this_arg is not None and isinstance(_fn, SpryFunction):
                            return self._call_function_with_this(_fn, all_args, this_arg, node)
                        return self._call_value(_fn, all_args)
                    return _bound
                return _fn_bind
            if prop == "call":
                def _fn_call(this_arg: Any, *call_args: Any, _fn=obj) -> Any:
                    if isinstance(_fn, BoundMethod):
                        # Rebind the underlying function to the new this_arg
                        underlying = _fn.fn
                        if this_arg is not None:
                            return self._call_function_with_this(underlying, list(call_args), this_arg, node)
                        return self._call_bound_method(_fn, list(call_args), node)
                    if this_arg is not None and isinstance(_fn, SpryFunction):
                        return self._call_function_with_this(_fn, list(call_args), this_arg, node)
                    return self._call_value(_fn, list(call_args))
                return _fn_call
            if prop == "apply":
                def _fn_apply(this_arg: Any, args_list: Any = None, _fn=obj) -> Any:
                    args = list(args_list) if args_list is not None else []
                    if isinstance(_fn, BoundMethod):
                        underlying = _fn.fn
                        if this_arg is not None:
                            return self._call_function_with_this(underlying, args, this_arg, node)
                        return self._call_bound_method(_fn, args, node)
                    if this_arg is not None and isinstance(_fn, SpryFunction):
                        return self._call_function_with_this(_fn, args, this_arg, node)
                    return self._call_value(_fn, args)
                return _fn_apply
            if prop == "name":
                if isinstance(obj, SpryFunction):
                    return obj.name
                if isinstance(obj, (SpryLambda, SpryMultiLambda)):
                    return obj.name
                return ""
            if prop == "length":
                if isinstance(obj, SpryFunction):
                    return len(obj.params)
                return 0
            if prop in ("toString", "__str__"):
                return lambda: repr(obj)
            if prop == "prototype":
                if isinstance(obj, SpryFunction):
                    if not hasattr(obj, "_prototype") or obj._prototype is None:
                        obj._prototype = {"constructor": obj}  # type: ignore[attr-defined]
                    elif "constructor" not in obj._prototype:
                        obj._prototype["constructor"] = obj  # type: ignore[attr-defined]
                    return obj._prototype  # type: ignore[attr-defined]
                return {}
            raise SpryRuntimeError(f"Function has no property {prop!r}", node)

        if isinstance(obj, SprySymbol):
            if prop == "description":
                return obj.description
            if prop in ("toString", "__str__"):
                _sym_desc = obj.description
                return lambda _d=_sym_desc: f"Symbol({_d})"
            if prop == "valueOf":
                return lambda _s=obj: _s
            # symbols have no other properties
            return None

        # Python callables: add JS-style call/apply/bind support
        if callable(obj) and prop in ("call", "apply", "bind"):
            if prop == "call":
                def _py_call(this_arg: Any, *call_args: Any, _fn=obj) -> Any:
                    return _fn(*call_args)
                return _py_call
            if prop == "apply":
                def _py_apply(this_arg: Any, args_list: Any = None, _fn=obj) -> Any:
                    args = list(args_list) if args_list is not None else []
                    return _fn(*args)
                return _py_apply
            if prop == "bind":
                def _py_bind(this_arg: Any, *bound_args: Any, _fn=obj) -> Any:
                    def _bound(*call_args: Any) -> Any:
                        return _fn(*(list(bound_args) + list(call_args)))
                    return _bound
                return _py_bind

        # Try attribute access
        try:
            return getattr(obj, prop)
        except AttributeError:
            raise SpryRuntimeError(f"Property {prop!r} not found on {type(obj).__name__}", node)

    def _eval_pipeline(self, node: PipelineExpression, env: Environment) -> Any:
        """Evaluate a pipeline: val |> filter x => ... |> map x => ... |> reduce (acc, x) => ..."""
        value = self._eval(node.stages[0], env)

        for stage in node.stages[1:]:
            # Multi-param lambda stages (reduce, reduce_with_init)
            if isinstance(stage, (MultiParamLambda, SpryMultiLambda)):
                operation = getattr(stage, "operation", "reduce")
                if operation == "reduce":
                    if not isinstance(value, list):
                        raise SpryRuntimeError("'reduce' requires a list", stage)
                    if len(value) == 0:
                        continue
                    acc = value[0]
                    for item in value[1:]:
                        acc = self._apply_multi_lambda(stage, [acc, item], env)
                    value = acc
                elif operation == "reduce_with_init":
                    init_node = stage.init
                    init_val = self._eval(init_node, env) if hasattr(init_node, "__class__") and not isinstance(init_node, (int, float, str, bool, type(None))) else init_node
                    if not isinstance(value, list):
                        raise SpryRuntimeError("'reduce' requires a list", stage)
                    acc = init_val
                    for item in value:
                        acc = self._apply_multi_lambda(stage, [acc, item], env)
                    value = acc
                continue

            # Single-param lambda stages (filter, map, each, groupBy, sortBy)
            if isinstance(stage, (LambdaExpression, SpryLambda)):
                operation = getattr(stage, "operation", "map")
                if operation == "filter":
                    if isinstance(value, list):
                        value = [item for item in value if self._truthy(self._apply_lambda(stage, item, env))]
                    else:
                        value = value if self._truthy(self._apply_lambda(stage, value, env)) else None
                elif operation == "each":
                    if isinstance(value, list):
                        for item in value:
                            self._apply_lambda(stage, item, env)
                    else:
                        self._apply_lambda(stage, value, env)
                    # "each" is side-effect only — value passes through unchanged
                elif operation == "groupBy":
                    if not isinstance(value, list):
                        raise SpryRuntimeError("'groupBy' requires a list", stage)
                    groups: dict[Any, list] = {}
                    for item in value:
                        key = self._apply_lambda(stage, item, env)
                        # Non-primitive keys (e.g. dicts, lists) are converted to their
                        # string representation for dict compatibility.  Note: objects with
                        # identical str() representations will be grouped together.
                        str_key = str(key) if not isinstance(key, (str, int, float, bool)) else key
                        if str_key not in groups:
                            groups[str_key] = []
                        groups[str_key].append(item)
                    value = groups
                elif operation == "sortBy":
                    if isinstance(value, list):
                        value = sorted(value, key=lambda item: self._apply_lambda(stage, item, env))
                else:  # "map"
                    if isinstance(value, list):
                        value = [self._apply_lambda(stage, item, env) for item in value]
                    else:
                        value = self._apply_lambda(stage, value, env)
                continue

            if isinstance(stage, Identifier):
                # Named function/operation call
                if stage.name == "__take__":
                    n = int(self._eval(stage._take_count, env))  # type: ignore[attr-defined]
                    value = value[:n] if isinstance(value, list) else value
                    continue
                if stage.name == "__skip__":
                    n = int(self._eval(stage._skip_count, env))  # type: ignore[attr-defined]
                    value = value[n:] if isinstance(value, list) else value
                    continue
                fn = self._eval(stage, env)
                operation = getattr(stage, "operation", None)
                # Named function reference with explicit pipeline operation (map/filter/each)
                if operation == "filter":
                    if isinstance(value, list):
                        value = [item for item in value if self._truthy(self._call_value(fn, [item]))]
                    else:
                        value = value if self._truthy(self._call_value(fn, [value])) else None
                elif operation == "each":
                    if isinstance(value, list):
                        for item in value:
                            self._call_value(fn, [item])
                    else:
                        self._call_value(fn, [value])
                elif operation == "map":
                    if isinstance(value, list):
                        value = [self._call_value(fn, [item]) for item in value]
                    else:
                        value = self._call_value(fn, [value])
                else:
                    # No explicit operation — call function with whole value (e.g. nums |> len)
                    value = self._call_value(fn, [value])
                continue

            if isinstance(stage, ParseStatement):
                value = self._parse(stage.format, str(value))
                continue

            if isinstance(stage, WriteStatement):
                path = self._eval(stage.path, env)
                # Write the accumulated value
                if isinstance(value, list):
                    data = "\n".join(str(item) for item in value)
                else:
                    data = str(value)
                result = self.fs.write_file(str(path), data)
                value = result
                continue

            # General expression stage — evaluate and apply
            result = self._eval(stage, env)
            if isinstance(result, (SpryLambda, LambdaExpression)):
                operation = getattr(result, "operation", "map")
                if operation == "filter":
                    if isinstance(value, list):
                        value = [item for item in value if self._truthy(self._apply_lambda(result, item, env))]
                elif operation == "each":
                    if isinstance(value, list):
                        for item in value:
                            self._apply_lambda(result, item, env)
                else:
                    if isinstance(value, list):
                        value = [self._apply_lambda(result, item, env) for item in value]
                    else:
                        value = self._apply_lambda(result, value, env)
            elif isinstance(result, (SpryMultiLambda, MultiParamLambda)):
                value = self._apply_multi_lambda(result, [value], env)
            elif isinstance(result, SpryFunction):
                value = self._call_function(result, [value], stage)
            elif callable(result):
                value = result(value)

        return value

    def _apply_lambda(self, lam: "LambdaExpression | SpryLambda", item: Any, env: Environment) -> Any:
        # Use closure environment if available (proper closures for SpryLambda)
        if isinstance(lam, SpryLambda):
            child = lam.closure.child()
            child.define(lam.param, item, mutable=False)
            body = lam.body
        else:
            # Fallback for raw LambdaExpression nodes (pipeline stages)
            child = env.child()
            child.define(lam.param, item, mutable=False)
            body = lam.body
        # Block body (from `x => { ... }`) — execute as a block
        if isinstance(body, Block):
            try:
                return self._exec_block(body, child)
            except ReturnSignal as r:
                return r.value
        return self._eval(body, child)

    def _apply_multi_lambda(self, lam: "MultiParamLambda | SpryMultiLambda", args: list[Any], env: Environment) -> Any:
        if isinstance(lam, SpryMultiLambda):
            child = lam.closure.child()
        else:
            child = env.child()
        # Separate rest param encoding from regular params
        params = lam.params
        rest_param_name: str | None = None
        if params and params[-1].startswith("__rest__:"):
            rest_param_name = params[-1][len("__rest__:"):]
            params = params[:-1]
        for i, param in enumerate(params):
            arg_val = args[i] if i < len(args) else None
            # Dict destructuring param: __destruct__:a,b  or  __destruct__:key|alias,b
            if param.startswith("__destruct__:"):
                field_specs = param[len("__destruct__:"):].split(",")
                src = arg_val if isinstance(arg_val, dict) else {}
                for fspec in field_specs:
                    fspec = fspec.strip()
                    if "|" in fspec:
                        fkey, flocal = fspec.split("|", 1)
                    else:
                        fkey = flocal = fspec
                    child.define(flocal, src.get(fkey), mutable=False)
            # Array destructuring param: __array_destruct__:a,b...rest
            elif param.startswith("__array_destruct__:"):
                raw = param[len("__array_destruct__:"):]
                arr_rest_name: str | None = None
                if "..." in raw:
                    raw, arr_rest_name = raw.split("...", 1)
                arr_field_names = [f for f in raw.split(",") if f]
                items = list(arg_val) if isinstance(arg_val, (list, tuple)) else []
                for _j, _fname in enumerate(arr_field_names):
                    child.define(_fname.strip(), items[_j] if _j < len(items) else None, mutable=False)
                if arr_rest_name:
                    child.define(arr_rest_name, items[len(arr_field_names):], mutable=False)
            else:
                child.define(param, arg_val, mutable=False)
        if rest_param_name is not None:
            child.define(rest_param_name, list(args[len(params):]), mutable=False)
        body = lam.body
        if isinstance(body, Block):
            try:
                return self._exec_block(body, child)
            except ReturnSignal as r:
                return r.value
        return self._eval(body, child)

    def _to_py_callable(self, fn: Any, env: Environment) -> Any:
        """Wrap a SpryCode callable as a Python callable for use in method closures."""
        if isinstance(fn, SpryLambda):
            w = lambda *args: self._apply_lambda(fn, args[0] if args else None, env)
            w._spry_arity = 1  # type: ignore[attr-defined]
            return w
        if isinstance(fn, SpryMultiLambda):
            w = lambda *args: self._apply_multi_lambda(fn, list(args), env)
            w._spry_arity = len(fn.params)  # type: ignore[attr-defined]
            return w
        if isinstance(fn, LambdaExpression):
            w = lambda *args: self._apply_lambda(fn, args[0] if args else None, env)
            w._spry_arity = 1  # type: ignore[attr-defined]
            return w
        if isinstance(fn, MultiParamLambda):
            w = lambda *args: self._apply_multi_lambda(fn, list(args), env)
            w._spry_arity = len(fn.params)  # type: ignore[attr-defined]
            return w
        if isinstance(fn, SpryFunction):
            arity = len(fn.params)
            w = lambda *args: self._call_function(fn, list(args), fn)
            w._spry_arity = arity  # type: ignore[attr-defined]
            return w
        return fn

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _exec_move(self, node: MoveStatement, env: Environment) -> Any:
        source = str(self._eval(node.source, env))
        destination = str(self._eval(node.destination, env))

        if node.target_type == "folder":
            result = self.fs.move_folder(
                source,
                destination,
                verify_checksum=node.verify_checksum,
                parallel=node.parallel,
                retry=node.retry or 0,
            )
        else:
            result = self.fs.move_file(
                source,
                destination,
                verify_checksum=node.verify_checksum,
                preserve_metadata=node.preserve_metadata,
                retry=node.retry or 0,
            )
        return result

    def _exec_copy(self, node: CopyStatement, env: Environment) -> Any:
        source = str(self._eval(node.source, env))
        destination = str(self._eval(node.destination, env))

        if node.target_type == "folder":
            result = self.fs.copy_folder(source, destination)
        else:
            result = self.fs.copy_file(
                source,
                destination,
                verify_checksum=node.verify_checksum,
                preserve_metadata=node.preserve_metadata,
            )
        return result

    def _exec_read(self, node: ReadStatement, env: Environment) -> Any:
        path = str(self._eval(node.path, env))
        return self.fs.read_file(path)

    def _exec_write(self, node: WriteStatement, env: Environment) -> Any:
        path = str(self._eval(node.path, env))
        data = self._eval(node.data, env) if node.data is not None else ""
        return self.fs.write_file(path, data)

    def _exec_delete(self, node: DeleteStatement, env: Environment) -> Any:
        # JS-style `delete obj.prop` / `delete obj[key]` — remove a property from an object/dict
        if node.target_type == "file" and isinstance(node.path, (MemberExpression, IndexExpression)):
            obj = self._eval(node.path.object, env)
            prop = (
                node.path.property
                if isinstance(node.path, MemberExpression)
                else self._eval(node.path.index, env)
            )
            if isinstance(obj, dict):
                obj.pop(prop, None)
            elif isinstance(obj, SpryInstance):
                obj.fields.pop(str(prop), None)
            elif isinstance(obj, SpryProxy):
                obj._spry_delete_prop(str(prop))
            return True
        path = str(self._eval(node.path, env))
        if node.target_type == "folder":
            return self.fs.delete_folder(path)
        return self.fs.delete_file(path)

    def _exec_stream(self, node: StreamStatement, env: Environment) -> Any:
        source = str(self._eval(node.source, env))
        # Read source
        if node.target_type == "folder":
            files = self.fs.list_folder(source)
            value: Any = files
        else:
            result = self.fs.read_file(source)
            if not result.ok:
                raise SpryRuntimeError(f"Stream error: {result.error}", node)
            value = result.value

        # Apply pipeline stages
        for stage in node.pipeline:
            if isinstance(stage, LambdaExpression):
                operation = getattr(stage, "operation", "map")
                if operation == "filter":
                    if isinstance(value, list):
                        value = [item for item in value if self._truthy(self._apply_lambda(stage, item, env))]
                    else:
                        value = value if self._truthy(self._apply_lambda(stage, value, env)) else None
                elif operation == "each":
                    if isinstance(value, list):
                        for item in value:
                            self._apply_lambda(stage, item, env)
                    # value unchanged
                else:  # map
                    if isinstance(value, list):
                        value = [self._apply_lambda(stage, item, env) for item in value]
                    else:
                        value = self._apply_lambda(stage, value, env)
            elif isinstance(stage, ParseStatement):
                value = self._parse(stage.format, str(value))
            elif isinstance(stage, WriteStatement):
                path = str(self._eval(stage.path, env))
                if isinstance(value, list):
                    data = "\n".join(str(item) for item in value)
                else:
                    data = str(value)
                result = self.fs.write_file(path, data)
                value = result
            else:
                stage_val = self._eval(stage, env)
                if isinstance(stage_val, LambdaExpression):
                    operation = getattr(stage_val, "operation", "map")
                    if operation == "filter":
                        if isinstance(value, list):
                            value = [item for item in value if self._truthy(self._apply_lambda(stage_val, item, env))]
                    elif operation == "each":
                        if isinstance(value, list):
                            for item in value:
                                self._apply_lambda(stage_val, item, env)
                    else:
                        if isinstance(value, list):
                            value = [self._apply_lambda(stage_val, item, env) for item in value]
                        else:
                            value = self._apply_lambda(stage_val, value, env)

        return value

    def _exec_sync(self, node: SyncStatement, env: Environment) -> Any:
        source = str(self._eval(node.source, env))
        destination = str(self._eval(node.destination, env))
        self.logger.info(f"Syncing {source} -> {destination} (mode={node.mode})")
        # Basic local sync using copy_folder
        if not destination.startswith(("s3://", "gs://", "az://")):
            return self.fs.copy_folder(source, destination)
        self.logger.warn(f"Cloud sync not yet supported: {destination}")
        return SpryResult(ok=False, error="Cloud sync requires a connector")

    # ------------------------------------------------------------------
    # Loops
    # ------------------------------------------------------------------

    def _consume_iterator(self, iterator: Any, node: Any) -> list:
        """Consume a JS-style iterator object (has `next()` method) into a list."""
        # SpryGenerator: lazily call .next() until done
        if isinstance(iterator, SpryGenerator):
            items: list[Any] = []
            while True:
                res = iterator.next()
                if res.get("done", False):
                    break
                items.append(res.get("value"))
            return items
        items = []
        next_fn: Any = None
        if isinstance(iterator, dict) and "next" in iterator:
            raw = iterator["next"]
            if isinstance(raw, DictBoundMethod):
                # DictBoundMethod — call via _call_dict_method so `this` = the dict
                next_fn = lambda _r=raw: self._call_dict_bound_method(_r.fn, _r.obj, [], node)
            else:
                next_fn = raw
        elif isinstance(iterator, SpryInstance) and "next" in iterator.fields:
            next_fn_raw = iterator.fields["next"]
            if isinstance(next_fn_raw, SpryFunction):
                bm = BoundMethod(instance=iterator, fn=next_fn_raw)
                next_fn = lambda: self._call_bound_method(bm, [], node)
            else:
                next_fn = next_fn_raw
        if next_fn is None:
            return items
        while True:
            result = self._call_value(next_fn, [])
            if isinstance(result, SpryPromise):
                result = result._value if result.status == "fulfilled" else {"value": None, "done": True}
            if isinstance(result, dict):
                if result.get("done"):
                    break
                items.append(result.get("value"))
            else:
                break
        return items

    def _iter_to_list(self, value: Any, node: Any) -> list:
        """Convert any SpryCode iterable to a Python list.

        Handles lists, strings, ranges, generators, iterators, SprySet/SpryMap,
        SpryTypedArray, plain dicts (yields keys), SpryInstance with next()
        method (iterator protocol), and SpryInstance with [Symbol.iterator]()
        (iterable protocol).
        """
        if isinstance(value, (list, tuple)):
            return list(value)
        if isinstance(value, range):
            return list(value)
        if isinstance(value, str):
            return list(value)
        if isinstance(value, SpryGenerator):
            return list(value)
        if isinstance(value, SpryIterator):
            return list(value._items)
        if isinstance(value, SprySet):
            return list(value._data)
        if isinstance(value, SpryTypedArray):
            return list(value._data)
        if isinstance(value, SpryMap):
            return [[k, v] for k, v in value._data.items()]
        if isinstance(value, SpryInstance):
            # Try [Symbol.iterator]() iterable protocol first
            # Check for both "Symbol('iterator')" and "[Symbol.iterator]" string keys
            for sym_key in ("Symbol('iterator')", "[Symbol.iterator]"):
                if sym_key in value.fields:
                    sym_iter_fn = value.fields[sym_key]
                    if isinstance(sym_iter_fn, SpryFunction):
                        bm = BoundMethod(instance=value, fn=sym_iter_fn)
                        iterator = self._call_bound_method(bm, [], node)
                        return self._consume_iterator(iterator, node)
            # Try direct next() iterator protocol
            return self._consume_iterator(value, node) or [
                k for k, v in value.fields.items()
                if not k.startswith("__") and not isinstance(v, SpryFunction)
            ]
        if isinstance(value, dict):
            # Check for [Symbol.iterator] method first — key may be SprySymbol or string
            sym_key = "Symbol('iterator')"
            sym_iter_fn = None
            # Look for SprySymbol key with description "iterator" or string key
            for k, v in value.items():
                if (isinstance(k, SprySymbol) and k.description == "iterator") or k == sym_key:
                    sym_iter_fn = v
                    break
            if sym_iter_fn is not None:
                if isinstance(sym_iter_fn, (SpryFunction, SpryLambda, SpryMultiLambda)):
                    iterator = self._call_dict_bound_method(sym_iter_fn, value, [], node)
                elif callable(sym_iter_fn):
                    iterator = sym_iter_fn()
                else:
                    iterator = None
                if iterator is not None:
                    return self._consume_iterator(iterator, node)
            # Check if it's an iterator (has 'next') — if so consume it
            next_val = value.get("next")
            if next_val is not None and (
                callable(next_val)
                or isinstance(next_val, (DictBoundMethod, SpryFunction, SpryLambda,
                                          SpryMultiLambda, BoundMethod))
            ):
                return self._consume_iterator(value, node)
            # Collect own + prototype chain string keys (for-in semantics)
            seen: set[str] = set()
            result_keys: list[str] = []
            cur: dict | None = value
            is_own = True
            while isinstance(cur, dict):
                for k in cur.keys():
                    if isinstance(k, str) and not k.startswith("__spry_") and k not in seen:
                        # Skip non-enumerable `constructor` property on prototypes
                        if not is_own and k == "constructor":
                            seen.add(k)
                            continue
                        seen.add(k)
                        result_keys.append(k)
                cur = cur.get("__spry_proto__")
                is_own = False
            return result_keys
        raise SpryRuntimeError(
            f"Value is not iterable: {type(value).__name__}", node
        )

    def _exec_for(self, node: ForStatement, env: Environment) -> Any:
        # Range shorthand: for i in start..end (BinaryExpression with op="..")
        if isinstance(node.iterable, BinaryExpression) and node.iterable.op == "..":
            start = int(self._eval(node.iterable.left, env))
            end = int(self._eval(node.iterable.right, env))
            iterable: Any = range(start, end)
        else:
            iterable = self._eval(node.iterable, env)

        # Determine loop item binder helper
        multi_vars = node.vars if node.vars else [node.var]
        destructured = len(multi_vars) > 1
        obj_destruct_vars: list[str] | None = None
        list_destruct_node: Any = node._list_destruct_node  # type: ignore[attr-defined]
        obj_destruct_node: Any = node._obj_destruct_node    # type: ignore[attr-defined]
        if list_destruct_node is None and len(multi_vars) == 1 and multi_vars[0].startswith("__obj_destruct__:"):
            field_names_str = multi_vars[0][len("__obj_destruct__:"):]
            obj_destruct_vars = [f for f in field_names_str.split(",") if f]
            destructured = False

        def _bind_item(child: "Environment", item: Any) -> None:
            """Bind a single loop item into child env per the destructure pattern."""
            if list_destruct_node is not None:
                self._apply_list_destructure(list_destruct_node, item if isinstance(item, (list, tuple)) else [item], child, list_destruct_node.mutable)
            elif obj_destruct_node is not None:
                self._apply_object_destructure(obj_destruct_node, item, child, obj_destruct_node.mutable)
            elif obj_destruct_vars is not None:
                obj = item if isinstance(item, dict) else (item.fields if isinstance(item, SpryInstance) else {})
                for fname in obj_destruct_vars:
                    child.define(fname, obj.get(fname) if isinstance(obj, dict) else None, mutable=False)
            elif destructured:
                if isinstance(item, (list, tuple)):
                    for idx, vname in enumerate(multi_vars):
                        child.define(vname, item[idx] if idx < len(item) else None, mutable=False)
                else:
                    child.define(multi_vars[0], item, mutable=False)
            else:
                child.define(node.var, item, mutable=False)

        def _exec_body_for_item(item: Any) -> bool:
            """Execute body for one item. Returns True if we should break."""
            # For async for-of, unwrap SpryPromise items
            if node.is_async and isinstance(item, SpryPromise):
                item = item.value if item._settled else item.value
            child = env.child()
            _bind_item(child, item)
            try:
                self._exec_block(node.body, child)
            except BreakSignal as bs:
                if bs.label is None or bs.label == node.label:
                    return True  # break
                raise
            except ContinueSignal as cs:
                if cs.label is None or cs.label == node.label:
                    pass  # continue
                else:
                    raise
            return False

        # Helper: call any next() function with no args, returning the result dict
        def _call_next(next_fn: Any) -> Any:
            if isinstance(next_fn, (SpryLambda, SpryMultiLambda)):
                return self._call_value(next_fn, [])
            if isinstance(next_fn, SpryFunction):
                return self._call_function(next_fn, [], node)
            if isinstance(next_fn, BoundMethod):
                return self._call_bound_method(next_fn, [], node)
            if isinstance(next_fn, DictBoundMethod):
                return self._call_dict_method(next_fn, [], node)
            if callable(next_fn):
                return next_fn()
            return None

        def _lazy_iter_dict(iterator: dict) -> bool:
            """Lazily iterate a JS-style dict iterator {next: fn}. Returns True if done."""
            next_fn = iterator.get("next")
            if next_fn is None:
                return False
            while True:
                result = _call_next(next_fn)
                if isinstance(result, SpryPromise):
                    result = result._value if result.status == "fulfilled" else {"value": None, "done": True}
                if not isinstance(result, dict) or result.get("done", False):
                    break
                if _exec_body_for_item(result.get("value")):
                    return True  # broken
            return False

        # SpryGenerator: iterate lazily to support infinite generators with break
        if isinstance(iterable, SpryGenerator):
            while True:
                result = iterable.next()
                if not isinstance(result, dict) or result.get("done", False):
                    break
                if _exec_body_for_item(result.get("value")):
                    break
            return None

        # Dict iterator (has 'next' callable): lazy iteration
        if isinstance(iterable, dict):
            next_val = iterable.get("next")
            if next_val is not None and (
                callable(next_val)
                or isinstance(next_val, (DictBoundMethod, SpryFunction, SpryLambda, SpryMultiLambda, BoundMethod))
            ):
                _lazy_iter_dict(iterable)
                return None

        # SpryInstance with [Symbol.iterator]() — lazy iteration
        if isinstance(iterable, SpryInstance):
            sym_key = "Symbol('iterator')"
            if sym_key in iterable.fields:
                sym_iter_fn = iterable.fields[sym_key]
                if isinstance(sym_iter_fn, SpryFunction):
                    bm = BoundMethod(instance=iterable, fn=sym_iter_fn)
                    iterator = self._call_bound_method(bm, [], node)
                    if isinstance(iterator, dict):
                        _lazy_iter_dict(iterator)
                        return None
                    # If iterator is itself a SpryGenerator, handle lazily
                    if isinstance(iterator, SpryGenerator):
                        while True:
                            res = iterator.next()
                            if res.get("done", False):
                                break
                            if _exec_body_for_item(res.get("value")):
                                break
                        return None

        # for await...of: unwrap SpryPromise to get its resolved value
        if node.is_async and isinstance(iterable, SpryPromise):
            if iterable._settled:
                inner = iterable._value
                if isinstance(inner, (list, tuple)):
                    for item in inner:
                        if _exec_body_for_item(item):
                            break
                else:
                    _exec_body_for_item(inner)
            return None

        if not isinstance(iterable, range):
            iterable = self._iter_to_list(iterable, node)

        for item in iterable:
            if _exec_body_for_item(item):
                break
        return None

    def _exec_labeled(self, node: LabeledStatement, env: Environment) -> Any:
        """Execute a labeled statement, catching break/continue with matching label."""
        body = node.body
        # Propagate label to inner loop node via proper AST field (ForStatement, WhileStatement)
        if isinstance(body, (ForStatement, ForCStyleStatement, WhileStatement)):
            body.label = node.label
        try:
            return self._exec(body, env)
        except BreakSignal as bs:
            if bs.label == node.label:
                return None  # consumed
            raise
        except ContinueSignal as cs:
            if cs.label == node.label:
                return None  # consumed
            raise

    def _exec_for_cstyle(self, node: ForCStyleStatement, env: Environment) -> Any:
        """Execute C-style for loop: for var i = 0; i < n; i++ { ... }"""
        child_env = env.child()
        if node.init is not None:
            if isinstance(node.init, (Block, DeclarationList)):
                for stmt in node.init.body:
                    # In C-style for-loop init, both `let` and `const` produce LetDeclaration
                    # nodes but must be mutable (JS semantics: loop counter is reassignable)
                    if isinstance(stmt, LetDeclaration):
                        val = self._eval(stmt.value, child_env) if stmt.value is not None else None
                        child_env.define(stmt.name, val, mutable=True)
                    else:
                        self._exec(stmt, child_env)
            elif isinstance(node.init, LetDeclaration):
                # let/const in C-style for-loop init: both `let` and `const` produce LetDeclaration
                # nodes but are treated as mutable loop counters here (JS semantics for for-loop vars)
                val = self._eval(node.init.value, child_env) if node.init.value is not None else None
                child_env.define(node.init.name, val, mutable=True)
            elif isinstance(node.init, NullLiteral):
                pass  # empty init: for (;;) or for (;cond;update)
            else:
                self._exec(node.init, child_env)
        max_iterations = 100_000
        count = 0
        while node.condition is None or self._truthy(self._eval(node.condition, child_env)):
            if count >= max_iterations:
                raise SpryRuntimeError("C-style for loop exceeded iteration limit", node)
            count += 1
            body_env = child_env.child()
            try:
                self._exec_block(node.body, body_env)
            except BreakSignal as bs:
                if bs.label is None or bs.label == node.label:
                    break
                raise
            except ContinueSignal as cs:
                if cs.label is None or cs.label == node.label:
                    pass  # fall through to update
                else:
                    raise
            # Sync vars back from body to child_env
            for vname, vval in body_env._vars.items():
                if vname in child_env._vars:
                    child_env._vars[vname] = vval
            if node.update is not None:
                if isinstance(node.update, Block):
                    for upd_node in node.update.body:
                        self._eval(upd_node, child_env)
                else:
                    self._eval(node.update, child_env)
        return None

    def _exec_while(self, node: WhileStatement, env: Environment) -> Any:
        max_iterations = 100_000  # safety limit
        count = 0
        while self._truthy(self._eval(node.condition, env)):
            child = env.child()
            try:
                self._exec_block(node.body, child)
            except BreakSignal as bs:
                if bs.label is None or bs.label == node.label:
                    break
                raise
            except ContinueSignal as cs:
                if cs.label is None or cs.label == node.label:
                    pass
                else:
                    raise
            count += 1
            if count >= max_iterations:
                raise SpryRuntimeError("While loop exceeded maximum iteration limit (100,000)", node)
        return None

    def _exec_loop(self, node: LoopStatement, env: Environment) -> Any:
        """Infinite loop — runs until break is encountered."""
        max_iterations = 100_000
        count = 0
        while True:
            child = env.child()
            try:
                self._exec_block(node.body, child)
            except BreakSignal as bs:
                if bs.label is None or bs.label == node.label:
                    break
                raise
            except ContinueSignal as cs:
                if cs.label is None or cs.label == node.label:
                    pass
                else:
                    raise
            count += 1
            if count >= max_iterations:
                raise SpryRuntimeError("Loop exceeded maximum iteration limit (100,000)", node)
        return None

    def _exec_retry(self, node: RetryStatement, env: Environment) -> Any:
        """Retry block — re-runs body on error up to <attempts> times."""
        attempts = int(self._eval(node.attempts, env) or 1)
        last_err: Exception | None = None
        for attempt in range(max(1, attempts)):
            child = env.child()
            child.define("_retry_attempt", attempt)
            try:
                self._exec_block(node.body, child)
                return None  # success
            except SpryRuntimeError as exc:
                last_err = exc
            except Exception as exc:
                last_err = exc
        # All attempts exhausted — raise the last error
        if last_err is not None:
            raise last_err
        return None

    def _exec_repeat_until(self, node: "RepeatUntilStatement", env: "Environment") -> Any:
        max_iterations = 100_000
        count = 0
        while True:
            child = env.child()
            try:
                self._exec_block(node.body, child)
            except BreakSignal:
                break
            except ContinueSignal:
                pass
            count += 1
            if count >= max_iterations:
                raise SpryRuntimeError("Repeat loop exceeded maximum iteration limit (100,000)", node)
            if self._truthy(self._eval(node.condition, env)):
                break
        return None

    def _exec_match(self, node: MatchStatement, env: Environment) -> Any:
        subject_val = self._eval(node.subject, env)
        for arm in node.arms:
            if arm.is_wildcard:
                # wildcard: check guard if present
                if arm.guard is not None:
                    child = env.child()
                    if not self._truthy(self._eval(arm.guard, child)):
                        continue
                child = env.child()
                return self._exec_block(arm.body, child)
            pattern_val = self._eval(arm.pattern, env)
            matched = False
            if arm.range_end is not None:
                # Range arm: pattern_val..range_end_val (inclusive)
                range_end_val = self._eval(arm.range_end, env)
                try:
                    matched = pattern_val <= subject_val <= range_end_val
                except TypeError:
                    matched = False
            else:
                matched = subject_val == pattern_val
            if matched:
                # Check guard
                if arm.guard is not None:
                    child = env.child()
                    if not self._truthy(self._eval(arm.guard, child)):
                        continue
                child = env.child()
                return self._exec_block(arm.body, child)
        return None

    def _exec_switch(self, node: SwitchStatement, env: Environment) -> Any:
        subject_val = self._eval(node.subject, env)
        try:
            # Find first matching case and execute it. Empty cases (no body) fall
            # through to the next non-empty case. Cases with a body stop after
            # execution unless a break raises BreakSignal. This matches JS semantics
            # where empty cases fall through but non-empty cases require an explicit
            # break to continue falling through.
            executing = False
            for case in node.cases:
                case_val = self._eval(case.value, env)
                if not executing and subject_val == case_val:
                    executing = True
                if executing:
                    if case.body and case.body.body:
                        self._exec_block(case.body, env)
                        return None
            if not executing and node.default_body is not None:
                self._exec_block(node.default_body, env)
        except BreakSignal:
            pass
        return None

    def _eval_postfix(self, node: PostfixExpression, env: Environment) -> Any:
        """Handle postfix and prefix ++/-- operators."""
        op = node.op
        operand = node.operand
        if isinstance(operand, Identifier):
            current = env.get(operand.name)
            if op in ("++", "pre++"):
                new_val = current + 1
            elif op in ("--", "pre--"):
                new_val = current - 1
            else:
                raise SpryRuntimeError(f"Unknown postfix operator: {op!r}", node)
            env.set(operand.name, new_val)
            # postfix: return old value; prefix: return new value
            return current if op in ("++", "--") else new_val
        if isinstance(operand, MemberExpression):
            obj = self._eval(operand.object, env)
            prop = operand.property
            if isinstance(obj, SpryInstance):
                current = obj.fields.get(prop)
            elif isinstance(obj, dict):
                current = obj.get(prop)
            elif isinstance(obj, SpryClass):
                # Seed static field into _static_fields if not yet present
                current = self._eval_member_on(obj, prop, node)
            else:
                raise SpryRuntimeError(f"Cannot apply {op!r} to {type(obj).__name__}", node)
            if current is None:
                current = 0
            if op in ("++", "pre++"):
                new_val = current + 1
            else:
                new_val = current - 1
            if isinstance(obj, SpryInstance):
                obj.set(prop, new_val)
            elif isinstance(obj, SpryClass):
                obj._static_fields[prop] = new_val
            else:
                obj[prop] = new_val
            return current if op in ("++", "--") else new_val
        raise SpryRuntimeError(f"Operator {op!r} requires an assignable target", node)

    def _iter(self, value: Any, node: Node) -> Any:
        """Return an iterable from a SpryCode value."""
        if isinstance(value, SpryGenerator):
            return value  # SpryGenerator is iterable
        if isinstance(value, (list, tuple, str)):
            return value
        if isinstance(value, dict):
            return value.keys()
        if hasattr(value, "__iter__"):
            return value
        raise SpryRuntimeError(
            f"Cannot iterate over {type(value).__name__}", node
        )

    def _exec_do_while(self, node: DoWhileStatement, env: Environment) -> Any:
        max_iterations = 100_000
        count = 0
        while True:
            child = env.child()
            try:
                self._exec_block(node.body, child)
            except BreakSignal:
                break
            except ContinueSignal:
                pass
            count += 1
            if count >= max_iterations:
                raise SpryRuntimeError(f"Do-while loop exceeded maximum iteration limit ({max_iterations})", node)
            # Continue while condition is true; stop when it becomes false
            if not self._truthy(self._eval(node.condition, env)):
                break
        return None

    def _exec_spawn(self, node: SpawnStatement, env: Environment) -> Any:
        """Spawn: evaluate the call expression asynchronously (fire-and-forget).
        Since SpryCode is synchronous at runtime, spawn is treated as an
        immediate synchronous call — the result is discarded.
        """
        try:
            self._eval(node.call, env)
        except Exception:
            pass  # Spawned calls never propagate exceptions to the caller
        return None

    def _exec_websocket(self, node: WebSocketStatement, env: Environment) -> Any:
        """WebSocket statement: registers a WebSocket connection object.
        At runtime, creates a stub object with send/close/onMessage methods.
        """
        url_val = self._eval(node.url, env)
        ws_obj = SpryWebSocket(str(url_val), self)
        if node.name:
            env.define(node.name, ws_obj, mutable=True)
        # Execute the body in a child scope where the ws name is visible
        if node.body:
            child = env.child()
            self._exec_block(node.body, child)
        return ws_obj

    def _exec_with(self, node: WithStatement, env: Environment) -> Any:
        """with <expr> [as <name>] { body } — resource management OR object binding.

        When the expr is a dict and there is no alias, bind all its keys as local
        variables in the body scope (like JS 'with').
        Always calls close() on the resource when done.
        """
        resource = self._eval(node.expr, env)
        child = env.child()
        if node.alias:
            child.define(node.alias, resource, mutable=False)
        elif isinstance(resource, dict):
            # Bind all object keys as variables
            for k, v in resource.items():
                child.define(str(k), v, mutable=False)
        try:
            return self._exec_block(node.body, child)
        finally:
            # Auto-close the resource if it supports it
            if hasattr(resource, "close"):
                try:
                    resource.close()
                except Exception:
                    pass

    def _exec_debit(self, node: DebitStatement, env: Environment) -> Any:
        """debit account <name> amount <val> — records a debit ledger entry."""
        account = self._eval(node.account, env)
        amount = self._eval(node.amount, env)
        self.logger.info(f"DEBIT  account={account!r}  amount={amount!r}")
        self.audit.log("debit", {"account": account, "amount": amount})
        return {"type": "debit", "account": account, "amount": amount}

    def _exec_credit(self, node: CreditStatement, env: Environment) -> Any:
        """credit account <name> amount <val> — records a credit ledger entry."""
        account = self._eval(node.account, env)
        amount = self._eval(node.amount, env)
        self.logger.info(f"CREDIT account={account!r}  amount={amount!r}")
        self.audit.log("credit", {"account": account, "amount": amount})
        return {"type": "credit", "account": account, "amount": amount}

    def _spry_typeof(self, val: Any) -> str:
        """Return the SpryCode type name of a value (used for SpryCode-style type checks)."""
        if isinstance(val, _SpryUndefinedType):
            return "undefined"
        if val is None:
            return "Null"
        if isinstance(val, bool):
            return "Bool"
        if isinstance(val, _SpryBigInt):
            return "BigInt"
        if isinstance(val, int):
            return "Int"
        if isinstance(val, float):
            return "Float"
        if isinstance(val, str):
            return "Text"
        if isinstance(val, list):
            return "List"
        if isinstance(val, dict):
            return "Object"
        if isinstance(val, SpryGenerator):
            return "Generator"
        if isinstance(val, SpryPromise):
            return "Promise"
        if isinstance(val, SpryProxy):
            return "Object"  # JS: typeof proxy === typeof target
        if isinstance(val, (SpryFunction, SpryLambda, SpryMultiLambda)):
            return "Function"
        if isinstance(val, SprySymbol):
            return "Symbol"
        if isinstance(val, SpryInstance):
            return val.cls.name
        if isinstance(val, SpryClass):
            return "Class"
        if isinstance(val, SpryStruct):
            return "Struct"
        if isinstance(val, SpryMoney):
            return "Money"
        if isinstance(val, SpryResult):
            return "Result"
        if isinstance(val, SpryRegex):
            return "Regex"
        if isinstance(val, SpryFile):
            return "File"
        if isinstance(val, SpryFolder):
            return "Folder"
        if callable(val):
            return "Function"
        return type(val).__name__

    def _js_typeof(self, val: Any) -> str:
        """Return the JS-standard typeof string (lowercase) — used by the ``typeof`` operator."""
        if isinstance(val, _SpryUndefinedType):
            return "undefined"
        if val is None:
            return "object"  # JS quirk: typeof null === 'object'
        if isinstance(val, bool):
            return "boolean"
        if isinstance(val, _SpryBigInt):
            return "bigint"
        if isinstance(val, (int, float)):
            return "number"
        if isinstance(val, str):
            return "string"
        if isinstance(val, SprySymbol):
            return "symbol"
        # All callables that aren't object-like instances
        if isinstance(val, (SpryFunction, SpryLambda, SpryMultiLambda, SpryClass,
                             BoundMethod, DictBoundMethod)):
            return "function"
        if callable(val) and not isinstance(val, (SpryInstance, SpryErrorObject,
                                                   SprySet, SpryMap, SpryGenerator,
                                                   SpryPromise, SpryProxy, SpryRegex)):
            return "function"
        # Anything else is 'object'
        return "object"

    def _eval_type_cast(self, node: TypeCastExpression, env: Environment) -> Any:
        """Evaluate `expr as TypeName` — convert value to the target type."""
        val = self._eval(node.operand, env)
        t = node.type_name
        try:
            if t in ("Text", "String", "str"):
                return self._builtin_str(val)
            if t in ("Int", "Integer", "int"):
                if isinstance(val, bool):
                    return int(val)
                if isinstance(val, float):
                    return int(val)
                if isinstance(val, str):
                    return int(float(val.strip()))
                return int(val)
            if t in ("Float", "Number", "float"):
                if isinstance(val, str):
                    return float(val.strip())
                return float(val)
            if t in ("Bool", "Boolean", "bool"):
                return self._truthy(val)
            if t in ("List", "Array", "list"):
                if isinstance(val, (list, tuple)):
                    return list(val)
                if isinstance(val, str):
                    return list(val)
                return [val]
            # Unknown cast — return value unchanged
            return val
        except (ValueError, TypeError) as e:
            raise SpryRuntimeError(f"Type cast to {t!r} failed: {e}", node) from e

    def _spry_instanceof(self, val: Any, type_name: str) -> bool:
        """Return True if val is an instance of the named SpryCode type."""
        # SpryErrorObject: check .name and walk the error hierarchy
        if isinstance(val, SpryErrorObject):
            _error_hierarchy = {
                "TypeError", "RangeError", "SyntaxError", "ReferenceError",
                "EvalError", "URIError",
            }
            if type_name == "Error":
                return True
            if type_name == val.name:
                return True
            return False
        # SpryInstance: check the class name and walk the superclass chain
        if isinstance(val, SpryInstance):
            cls: SpryClass | None = val.cls
            while cls is not None:
                if cls.name == type_name:
                    return True
                # Check if this class extends a built-in error namespace
                builtin_err = getattr(cls, "_builtin_error_superclass", None)
                if builtin_err is not None and isinstance(builtin_err, _ErrorNamespace):
                    if builtin_err._name == type_name:
                        return True
                cls = cls.superclass
            return False
        actual = self._spry_typeof(val)
        # SpryCode-style aliases
        aliases: dict[str, list[str]] = {
            "Number": ["Int", "Float"],
            "Text": ["Text"],
            "Bool": ["Bool"],
            "List": ["List"],
            "Object": ["Object"],
            "Null": ["Null"],
            "Function": ["Function"],
        }
        if type_name in aliases:
            return actual in aliases[type_name]
        # JS-style type-name aliases for primitive/built-in types
        js_aliases: dict[str, Any] = {
            "Array": list,
            "String": str,
            "Boolean": bool,
            "Number": (int, float),
            "Function": (SpryFunction, SpryLambda),
            "Map": SpryMap,
            "Set": SprySet,
            "RegExp": SpryRegex,
            "Promise": SpryPromise,
            "Symbol": SprySymbol,
        }
        if type_name in js_aliases:
            py_type = js_aliases[type_name]
            if isinstance(py_type, tuple):
                return isinstance(val, py_type) and not isinstance(val, bool)
            if type_name == "Boolean":
                return isinstance(val, bool)
            if type_name == "Number":
                return isinstance(val, (int, float)) and not isinstance(val, bool)
            return isinstance(val, py_type)
        # TypedArray instanceof checks
        if isinstance(val, SpryTypedArray) and val._type_name == type_name:
            return True
        if isinstance(val, SpryArrayBuffer) and type_name == "ArrayBuffer":
            return True
        if isinstance(val, SpryTypedArray) and type_name == "TypedArray":
            return True
        return actual == type_name

    def _exec_assert(self, node: AssertStatement, env: Environment) -> Any:
        cond = self._eval(node.condition, env)
        if not self._truthy(cond):
            if node.message is not None:
                msg = self._builtin_str(self._eval(node.message, env))
            else:
                msg = "Assertion failed"
            raise SpryRuntimeError(msg, node)
        return None

    def _exec_import(self, node: ImportStatement, env: Environment) -> Any:
        """Simple import: expose Python stdlib module names into the SpryCode environment."""
        import importlib
        module = node.module
        # Allowed stdlib modules (security whitelist)
        allowed_stdlib = {"math", "json", "re", "random", "statistics", "string", "datetime"}
        if module not in allowed_stdlib:
            self.logger.warn(f"import: module '{module}' not available")
            return None
        try:
            mod = importlib.import_module(module)
            if node.names:
                # import { a, b } from "math" — each name gets its own binding
                for name in node.names:
                    env.define(name, getattr(mod, name, None), mutable=False)
            elif node.alias:
                # import "math" as m
                env.define(node.alias, mod, mutable=False)
            else:
                # import math — expose public, callable or constant names
                public_names = getattr(mod, "__all__", None) or [
                    n for n in dir(mod) if not n.startswith("_")
                ]
                for attr in public_names:
                    val = getattr(mod, attr, None)
                    if callable(val) or isinstance(val, (int, float, str)):
                        env.define(attr, val, mutable=False)
        except ImportError:
            self.logger.warn(f"import: failed to load module '{module}'")
        return None

    def _exec_list_destructure(self, node: ListDestructure, env: Environment) -> Any:
        return self._apply_list_destructure(node, None, env, node.mutable)

    def _apply_list_destructure(self, node: ListDestructure, source_val: Any, env: Environment, mutable: bool) -> None:
        """Bind names from source_val using the list destructure pattern node."""
        if source_val is None:
            val = self._eval(node.value, env) if node.value is not None else []
        else:
            val = source_val
        if not isinstance(val, (list, tuple)):
            try:
                val = self._iter_to_list(val, node)
            except Exception:
                raise SpryRuntimeError(
                    f"List destructuring requires a list, got {type(val).__name__}", node
                )
        for i, name in enumerate(node.names):
            item = val[i] if i < len(val) else None
            # Skip holes: [a, , b] — the comma with no name skips an element
            if name == "__hole__":
                continue
            if i in node.nested:
                # Nested destructuring: [[a, b], c] or [{x}, c]
                nested_node = node.nested[i]
                if isinstance(nested_node, ListDestructure):
                    self._apply_list_destructure(nested_node, item if item is not None else [], env, mutable)
                elif isinstance(nested_node, ObjectDestructure):
                    self._apply_object_destructure(nested_node, item if item is not None else {}, env, mutable)
                continue
            # Apply default if item is None/missing and a default is defined
            if item is None and name in node.defaults:
                item = self._eval(node.defaults[name], env)
            env.define(name, item, mutable=mutable)
        if node.rest_name is not None:
            rest = list(val[len(node.names):])
            env.define(node.rest_name, rest, mutable=mutable)
        return None

    def _exec_object_destructure(self, node: ObjectDestructure, env: Environment) -> Any:
        return self._apply_object_destructure(node, None, env, node.mutable)

    def _apply_object_destructure(self, node: ObjectDestructure, source_val: Any, env: Environment, mutable: bool) -> None:
        """Bind names from source_val using the destructure pattern node."""
        if source_val is None:
            val = self._eval(node.value, env) if node.value is not None else {}
        else:
            val = source_val
        if isinstance(val, SpryInstance):
            obj: dict = val.fields
        elif isinstance(val, dict):
            obj = val
        else:
            raise SpryRuntimeError(
                f"Object destructuring requires an object, got {type(val).__name__}", node
            )
        for name in node.names:
            if name in node.nested:
                # Recursively apply nested destructure pattern to the child value
                inner_val = obj.get(name)
                nested_node = node.nested[name]
                if isinstance(nested_node, ObjectDestructure):
                    self._apply_object_destructure(nested_node, inner_val, env, mutable)
                elif isinstance(nested_node, ListDestructure):
                    self._apply_list_destructure(nested_node, inner_val, env, mutable)
            else:
                alias = node.aliases.get(name, name)
                item = obj.get(name)
                # Apply default if item is None and a default is defined
                if item is None and alias in node.defaults:
                    item = self._eval(node.defaults[alias], env)
                elif item is None and name in node.defaults:
                    item = self._eval(node.defaults[name], env)
                env.define(alias, item, mutable=mutable)
        # Rest element: collect all keys not already consumed
        if node.rest_name is not None:
            consumed = set(node.aliases.get(n, n) for n in node.names) | set(node.names)
            rest_obj = {k: v for k, v in obj.items() if k not in consumed}
            env.define(node.rest_name, rest_obj, mutable=mutable)
        return None

    def _apply_catch_pattern(self, pattern: Any, err_val: Any, env: "Environment") -> None:
        """Apply a destructuring pattern (ListDestructure/ObjectDestructure) to a catch value."""
        if isinstance(pattern, ObjectDestructure):
            # Convert err_val to a dict if it's a SpryInstance or SpryErrorObject
            if isinstance(err_val, SpryInstance):
                src = err_val.fields
            elif isinstance(err_val, SpryErrorObject):
                src = {"message": err_val.message, "name": err_val.name, "stack": err_val.stack}
            elif isinstance(err_val, dict):
                src = err_val
            else:
                src = {"message": str(err_val)}
            self._apply_object_destructure(pattern, src, env, mutable=True)
        elif isinstance(pattern, ListDestructure):
            if isinstance(err_val, (list, tuple)):
                src_list = list(err_val)
            else:
                src_list = [err_val]
            self._apply_list_destructure(pattern, src_list, env, mutable=True)

    # ------------------------------------------------------------------
    # File creation / archive
    # ------------------------------------------------------------------

    def _exec_create(self, node: CreateStatement, env: Environment) -> Any:
        path = str(self._eval(node.path, env))
        content = self._eval(node.content, env) if node.content is not None else ""
        if node.target_type == "folder":
            from pathlib import Path
            self.permissions.check("filesystem.write", path)
            try:
                Path(path).mkdir(parents=True, exist_ok=True)
                return SpryResult(ok=True, value=path)
            except Exception as e:
                return SpryResult(ok=False, error=str(e))
        return self.fs.create_file(path, str(content) if content is not None else "")

    def _exec_compress(self, node: CompressStatement, env: Environment) -> Any:
        source = str(self._eval(node.source, env))
        destination = str(self._eval(node.destination, env))
        return self.fs.compress_folder(source, destination)

    def _exec_extract(self, node: ExtractStatement, env: Environment) -> Any:
        source = str(self._eval(node.source, env))
        destination = str(self._eval(node.destination, env))
        return self.fs.extract_archive(source, destination)

    # ------------------------------------------------------------------
    # Enum / Struct / Class
    # ------------------------------------------------------------------

    def _exec_enum(self, node: EnumDeclaration, env: Environment) -> Any:
        enum_obj = SpryEnum(name=node.name, variants=node.variants)
        env.define(node.name, enum_obj, mutable=False)
        return None

    def _exec_struct(self, node: StructDeclaration, env: Environment) -> Any:
        struct_obj = SpryStruct(name=node.name, fields=node.fields)
        env.define(node.name, struct_obj, mutable=False)
        return None

    def _exec_class(self, node: ClassDeclaration, env: Environment) -> Any:
        # Resolve superclass, if any
        superclass: SpryClass | None = None
        _builtin_err_ns: "_ErrorNamespace | None" = None
        if node.superclass is not None:
            try:
                sc = env.get(node.superclass)
                if isinstance(sc, SpryClass):
                    superclass = sc
                elif isinstance(sc, _ErrorNamespace):
                    _builtin_err_ns = sc
            except SpryRuntimeError:
                pass

        # Resolve mixin classes
        mixin_classes: list[SpryClass] = []
        for mname in getattr(node, "mixins", []):
            try:
                mc = env.get(mname)
                if isinstance(mc, SpryClass):
                    mixin_classes.append(mc)
            except SpryRuntimeError:
                pass

        cls = SpryClass(name=node.name, body=node.body, closure=env, superclass=superclass)
        # Attach mixin classes so _construct_class can use them
        cls._mixins = mixin_classes  # type: ignore[attr-defined]
        if _builtin_err_ns is not None:
            cls._builtin_error_superclass = _builtin_err_ns  # type: ignore[attr-defined]
        env.define(node.name, cls, mutable=False)
        # Run any static initialization blocks defined in the class body
        for stmt in node.body.body:
            if isinstance(stmt, FunctionDeclaration) and stmt.name == "__static_init__":
                static_env = env.child()
                self._exec_block(stmt.body, static_env)
        # Store static computed methods (e.g. static [Symbol.hasInstance]()) in _static_fields
        for stmt in node.body.body:
            if isinstance(stmt, ComputedFieldDeclaration) and stmt.is_static:
                computed_key = self._eval(stmt.key, env)
                computed_key_str = str(computed_key) if computed_key is not None else "__computed__"
                cls._static_fields[computed_key_str] = self._eval(stmt.value, env) if stmt.value is not None else None
            elif isinstance(stmt, ComputedMethodDeclaration) and stmt.is_static:
                computed_key = self._eval(stmt.key, env)
                computed_key_str = str(computed_key) if computed_key is not None else "__computed__"
                fn = SpryFunction(
                    name=computed_key_str,
                    params=stmt.params,
                    body=stmt.body,  # type: ignore
                    closure=env,
                    defaults=stmt.defaults,
                    rest_param=stmt.rest_param,
                )
                cls._static_fields[computed_key_str] = fn
            # static #field / static #method — store in _static_fields with __private__ prefix
            elif isinstance(stmt, VarDeclaration) and stmt.name.startswith("__static_private__"):
                priv_key = "__private__" + stmt.name[len("__static_private__"):]
                cls._static_fields[priv_key] = self._eval(stmt.value, env) if stmt.value is not None else None
            elif isinstance(stmt, FunctionDeclaration) and stmt.name.startswith("__static_private__"):
                priv_key = "__private__" + stmt.name[len("__static_private__"):]
                fn = SpryFunction(
                    name=priv_key,
                    params=stmt.params,
                    body=stmt.body,  # type: ignore
                    closure=env,
                    defaults=stmt.defaults,
                    rest_param=stmt.rest_param,
                )
                cls._static_fields[priv_key] = fn
        return None

    def _eval_class_expression(self, node: "ClassExpression", env: Environment) -> SpryClass:
        """Evaluate a class expression — creates a SpryClass but does NOT bind it to a name."""
        superclass: SpryClass | None = None
        _builtin_err_ns: "_ErrorNamespace | None" = None
        if node.superclass is not None:
            try:
                sc = env.get(node.superclass)
                if isinstance(sc, SpryClass):
                    superclass = sc
                elif isinstance(sc, _ErrorNamespace):
                    _builtin_err_ns = sc
            except SpryRuntimeError:
                pass
        cls = SpryClass(name=node.name, body=node.body, closure=env, superclass=superclass)
        cls._mixins = []  # type: ignore[attr-defined]
        if _builtin_err_ns is not None:
            cls._builtin_error_superclass = _builtin_err_ns  # type: ignore[attr-defined]
        # Store static computed methods in _static_fields
        for stmt in node.body.body:
            if isinstance(stmt, ComputedMethodDeclaration) and stmt.is_static:
                computed_key = self._eval(stmt.key, env)
                computed_key_str = str(computed_key) if computed_key is not None else "__computed__"
                fn = SpryFunction(
                    name=computed_key_str,
                    params=stmt.params,
                    body=stmt.body,  # type: ignore
                    closure=env,
                    defaults=stmt.defaults,
                    rest_param=stmt.rest_param,
                )
                cls._static_fields[computed_key_str] = fn
        return cls

    def _eval_super(self, node: SuperExpression, env: Environment) -> Any:
        """super(args) — call the parent class init() on the current instance."""
        # Resolve current instance (self) and its class
        try:
            self_val = env.get("self")
        except SpryRuntimeError:
            raise SpryRuntimeError("'super' used outside of a class method", node)
        if not isinstance(self_val, SpryInstance):
            raise SpryRuntimeError("'super' used outside of a class instance", node)
        # Determine which class we're currently executing in (for deep inheritance chains)
        try:
            current_cls = env.get("__current_class__")
        except SpryRuntimeError:
            current_cls = self_val.cls
        parent = current_cls.superclass if isinstance(current_cls, SpryClass) else self_val.cls.superclass
        if parent is None:
            # Check for builtin error superclass — super(msg) sets error fields
            builtin_err = (
                getattr(current_cls, '_builtin_error_superclass', None)
                if isinstance(current_cls, SpryClass)
                else getattr(self_val.cls, '_builtin_error_superclass', None)
            )
            if builtin_err is not None:
                args_vals = [self._eval(a, env) for a in node.args]
                msg = str(args_vals[0]) if args_vals else ""
                self_val.fields["message"] = msg
                self_val.fields["name"] = self_val.cls.name
                self_val.fields["stack"] = f"{self_val.cls.name}: {msg}"
                # Extract `cause` from the options object (second argument)
                if len(args_vals) >= 2 and isinstance(args_vals[1], dict) and "cause" in args_vals[1]:
                    self_val.fields["cause"] = args_vals[1]["cause"]
                elif "cause" not in self_val.fields:
                    self_val.fields.setdefault("cause", None)
            return None  # no superclass — silently ignore
        # Find parent's init / constructor and call it with evaluated args
        args_vals = [self._eval(a, env) for a in node.args]
        # Look up init or constructor in parent
        init_fn = None
        for stmt in parent.body.body:  # type: ignore[union-attr]
            if isinstance(stmt, FunctionDeclaration) and stmt.name in ("init", "constructor"):
                init_fn = SpryFunction(
                    name=stmt.name,
                    params=stmt.params,
                    body=stmt.body,  # type: ignore
                    closure=self_val.fields.get("__instance_env__", parent.closure).child(),
                    defaults=stmt.defaults,
                    rest_param=stmt.rest_param,
                )
                break
        if init_fn is None:
            return None
        bm = BoundMethod(instance=self_val, fn=init_fn)
        bm._defining_class = parent  # type: ignore[attr-defined]
        return self._call_bound_method(bm, args_vals, node)

    def _eval_super_member(self, prop: str, env: Environment, node: Node) -> Any:
        """super.method — look up method in parent class and return it bound to current self."""
        try:
            self_val = env.get("self")
        except SpryRuntimeError:
            raise SpryRuntimeError("'super.method' used outside of a class method", node)
        if not isinstance(self_val, SpryInstance):
            raise SpryRuntimeError("'super.method' used outside of a class instance", node)

        # Determine which class we're currently executing in so we can find ITS parent.
        try:
            current_cls = env.get("__current_class__")
        except SpryRuntimeError:
            current_cls = self_val.cls

        parent = current_cls.superclass if isinstance(current_cls, SpryClass) else None
        if parent is None:
            # Check for builtin error superclass — super.init(msg) / super.constructor(msg) sets error fields
            builtin_err = getattr(current_cls, '_builtin_error_superclass', None) if isinstance(current_cls, SpryClass) else None
            if builtin_err is not None and prop in ("init", "constructor"):
                def _builtin_error_init(*args: Any) -> None:
                    msg = str(args[0]) if args else ""
                    self_val.fields["message"] = msg
                    self_val.fields["name"] = self_val.cls.name
                    self_val.fields["stack"] = f"{self_val.cls.name}: {msg}"
                    try:
                        inst_env = self_val.fields.get("__instance_env__")
                        if inst_env is not None:
                            inst_env.assign("message", msg)
                            inst_env.assign("name", self_val.cls.name)
                            inst_env.assign("stack", f"{self_val.cls.name}: {msg}")
                    except Exception:
                        pass
                return _builtin_error_init
            raise SpryRuntimeError(f"No superclass to access 'super.{prop}'", node)

        # Walk up the ancestor chain to find the method
        search_cls: SpryClass | None = parent
        while search_cls is not None:
            for stmt in search_cls.body.body:  # type: ignore[union-attr]
                if isinstance(stmt, FunctionDeclaration) and stmt.name == prop:
                    fn = SpryFunction(
                        name=stmt.name,
                        params=stmt.params,
                        body=stmt.body,  # type: ignore
                        closure=search_cls.closure.child(),
                        defaults=stmt.defaults,
                        rest_param=stmt.rest_param,
                    )
                    bm = BoundMethod(instance=self_val, fn=fn)
                    bm._defining_class = search_cls  # type: ignore[attr-defined]
                    return bm
            search_cls = search_cls.superclass
        raise SpryRuntimeError(f"Superclass has no method {prop!r}", node)

    def _construct_class(self, cls: SpryClass, args: list[Any], node: Node, _for_inheritance: bool = False) -> SpryInstance:
        """Instantiate a SpryClass: set up fields from var declarations, run init if defined."""
        # Build instance fields by executing the class body in an isolated env
        instance_env = cls.closure.child()
        fields: dict[str, Any] = {}

        # If superclass, pre-populate fields from it (without calling super's init)
        if cls.superclass is not None:
            super_inst = self._construct_class(cls.superclass, [], node, _for_inheritance=True)
            for k, v in super_inst.fields.items():
                fields[k] = v
                instance_env.define(k, v, mutable=True)

        # If class extends a builtin error type, pre-populate error fields
        builtin_err = getattr(cls, '_builtin_error_superclass', None)
        if builtin_err is not None:
            fields["message"] = ""
            fields["name"] = cls.name
            fields["stack"] = f"{cls.name}: "
            fields["cause"] = None
            instance_env.define("message", "", mutable=True)
            instance_env.define("name", cls.name, mutable=True)
            instance_env.define("stack", f"{cls.name}: ", mutable=True)
            instance_env.define("cause", None, mutable=True)

        # Apply mixin classes: inject their fields/methods
        for mixin_cls in getattr(cls, "_mixins", []):
            mixin_inst = self._construct_class(mixin_cls, [], node, _for_inheritance=True)
            for k, v in mixin_inst.fields.items():
                # Only add if not already defined (class overrides mixin)
                if k not in fields:
                    fields[k] = v
                    instance_env.define(k, v, mutable=True)

        # Execute the class body to pick up var/fn declarations (subclass overrides superclass)
        # Create instance early so field initializers referencing `this` work correctly
        instance = SpryInstance(cls=cls, fields=fields)
        instance_env.define("self", instance, mutable=False)
        instance_env.define("this", instance, mutable=False)
        for stmt in cls.body.body:  # type: ignore[union-attr]
            if isinstance(stmt, VarDeclaration):
                # Skip static private fields — class-level, stored in _static_fields
                if stmt.name.startswith("__static_private__"):
                    continue
                val = self._eval(stmt.value, instance_env) if stmt.value is not None else None
                fields[stmt.name] = val
                instance_env.define(stmt.name, val, mutable=True)
            elif isinstance(stmt, FunctionDeclaration):
                # Skip static private methods and static init — class-level
                if stmt.name.startswith("__static_private__") or stmt.name == "__static_init__":
                    continue
                fn = SpryFunction(
                    name=stmt.name,
                    params=stmt.params,
                    body=stmt.body,  # type: ignore
                    closure=instance_env,
                    defaults=stmt.defaults,
                    rest_param=stmt.rest_param,
                    is_generator=stmt.is_generator,
                    is_async=stmt.is_async,
                )
                fields[stmt.name] = fn
                instance_env.define(stmt.name, fn, mutable=False)
            elif isinstance(stmt, LetDeclaration):
                val = self._eval(stmt.value, instance_env) if stmt.value is not None else None
                fields[stmt.name] = val
                instance_env.define(stmt.name, val, mutable=False)
            elif isinstance(stmt, GetterDeclaration):
                # Store getter function; will be wrapped in BoundMethod after self is defined
                getter_fn = SpryFunction(
                    name=f"get_{stmt.name}",
                    params=[],
                    body=stmt.body,  # type: ignore
                    closure=instance_env,
                    defaults={},
                    rest_param=None,
                )
                fields[f"__getter__{stmt.name}"] = getter_fn
                instance_env.define(f"__getter__{stmt.name}", getter_fn, mutable=False)
            elif isinstance(stmt, SetterDeclaration):
                # Store setter function; will be wrapped in BoundMethod after self is defined
                setter_fn = SpryFunction(
                    name=f"set_{stmt.name}",
                    params=[(stmt.param, None)],
                    body=stmt.body,  # type: ignore
                    closure=instance_env,
                    defaults={},
                    rest_param=None,
                )
                fields[f"__setter__{stmt.name}"] = setter_fn
                instance_env.define(f"__setter__{stmt.name}", setter_fn, mutable=False)
            elif isinstance(stmt, ComputedMethodDeclaration):
                # Skip static computed methods — they're class-level, handled in _exec_class
                if stmt.is_static:
                    continue
                # [Symbol.iterator]() { ... } — evaluate key and store method
                computed_key = self._eval(stmt.key, instance_env)
                computed_key_str = str(computed_key) if computed_key is not None else "__computed__"
                fn = SpryFunction(
                    name=computed_key_str,
                    params=stmt.params,
                    body=stmt.body,  # type: ignore
                    closure=instance_env,
                    defaults=stmt.defaults,
                    rest_param=stmt.rest_param,
                    is_generator=stmt.is_generator,
                )
                if stmt.is_getter:
                    # get [expr]() { ... } — store as computed getter
                    getter_key = f"__getter__{computed_key_str}"
                    fields[getter_key] = fn
                    instance_env.define(getter_key, fn, mutable=False)
                elif stmt.is_setter:
                    # set [expr](v) { ... } — store as computed setter
                    setter_key = f"__setter__{computed_key_str}"
                    fields[setter_key] = fn
                    instance_env.define(setter_key, fn, mutable=False)
                else:
                    fields[computed_key_str] = fn
                    instance_env.define(computed_key_str, fn, mutable=False)
            elif isinstance(stmt, Assignment) and stmt.value is not None:
                # Public instance field declaration: fieldName = value (no var/let keyword)
                val = self._eval(stmt.value, instance_env)
                fields[stmt.name] = val
                instance_env.define(stmt.name, val, mutable=True)

        # instance already created above for `this` reference during field init

        # Bind "self" so methods can use it (re-bind to ensure correct instance after field loop)
        instance_env.define("self", instance, mutable=False)
        instance_env.define("this", instance, mutable=False)

        # Re-bind all methods with updated instance_env that includes `self`
        for fname, fval in list(fields.items()):
            if isinstance(fval, SpryFunction):
                new_fn = SpryFunction(
                    name=fval.name,
                    params=fval.params,
                    body=fval.body,
                    closure=instance_env,
                    defaults=fval.defaults,
                    rest_param=fval.rest_param,
                    is_generator=fval.is_generator,
                    is_async=fval.is_async,
                )
                fields[fname] = new_fn
                instance.fields[fname] = new_fn

        # Call init() / constructor() if defined (skip when building inheritance field structure)
        if not _for_inheritance:
            prev_new_target = getattr(self._tl, "new_target", None)
            self._tl.new_target = cls  # type: ignore[attr-defined]
            try:
                ctor_fn = fields.get("init") or fields.get("constructor")
                if isinstance(ctor_fn, SpryFunction):
                    self._call_bound_method(BoundMethod(instance=instance, fn=ctor_fn), args, node, new_target=cls)
                elif args:
                    # Positional-field constructor: Counter(10) → counter.count = 10
                    field_vars = [k for k, v in fields.items() if not callable(v) and not isinstance(v, SpryFunction)]
                    for i, arg in enumerate(args):
                        if i < len(field_vars):
                            instance.set(field_vars[i], arg)
            finally:
                self._tl.new_target = prev_new_target  # type: ignore[attr-defined]

        return instance

    def _construct_plain_function(self, fn: SpryFunction, args: list[Any], node: Node) -> Any:
        """Construct a new object using a plain function as constructor (new Fn())."""
        this: dict[str, Any] = {}
        # Auto-initialize prototype with constructor reference
        if fn._prototype is None:
            fn._prototype = {"constructor": fn}
        elif "constructor" not in fn._prototype:
            fn._prototype["constructor"] = fn
        proto = fn._prototype
        if proto is not None:
            this["__spry_proto__"] = proto
        child = fn.closure.child()
        child.define("arguments", list(args), mutable=False)
        child.define("this", this, mutable=True)
        child.define("self", this, mutable=True)
        for i, (pname, _ptype) in enumerate(fn.params):
            if pname.startswith("__destruct__:"):
                field_specs = pname[len("__destruct__:"):].split(",")
                arg_val = args[i] if i < len(args) else {}
                if not isinstance(arg_val, dict):
                    arg_val = {}
                for fspec in field_specs:
                    fspec = fspec.strip()
                    if "|" in fspec:
                        fkey, flocal = fspec.split("|", 1)
                    else:
                        fkey = flocal = fspec
                    fval = arg_val.get(fkey)
                    child.define(flocal, fval, mutable=False)
            elif i < len(args):
                child.define(pname, args[i], mutable=False)
            elif pname in fn.defaults:
                child.define(pname, self._eval(fn.defaults[pname], fn.closure), mutable=False)
            else:
                child.define(pname, None, mutable=False)
        if fn.rest_param is not None:
            child.define(fn.rest_param, list(args[len(fn.params):]), mutable=False)
        prev_new_target = getattr(self._tl, "new_target", None)
        self._tl.new_target = fn  # type: ignore[attr-defined]
        return_val = None
        try:
            try:
                self._exec_block(fn.body, child)
            except ReturnSignal as r:
                return_val = r.value
        finally:
            self._tl.new_target = prev_new_target  # type: ignore[attr-defined]
        # If function explicitly returned an object, use that; otherwise return this
        if return_val is not None and isinstance(return_val, (dict, SpryInstance)):
            return return_val
        # Sync back any mutations to `this`
        try:
            this = child.get("this")
        except Exception:
            pass
        return this

    def _call_value(self, fn: Any, args: list) -> Any:
        """Call any SpryCode value as a function (used by event handlers, etc.)."""
        if isinstance(fn, SpryFunction):
            # Create a dummy CallExpression node for error context
            from .ast_nodes import Node as _Node
            class _DummyNode(_Node):
                line: int = 0
                column: int = 0
            return self._call_function(fn, args, _DummyNode())
        if isinstance(fn, BoundMethod):
            from .ast_nodes import Node as _Node
            class _DummyNode(_Node):
                line: int = 0
                column: int = 0
            return self._call_bound_method(fn, args, _DummyNode())
        if isinstance(fn, (SpryLambda, LambdaExpression)):
            return self._apply_lambda(fn, args[0] if args else None, self.globals)
        if isinstance(fn, (SpryMultiLambda, MultiParamLambda)):
            return self._apply_multi_lambda(fn, args, self.globals)
        if callable(fn):
            return fn(*args)
        return None

    def _call_bound_method(
        self,
        bm: BoundMethod,
        args: list[Any],
        node: Node,
        new_target: Any = SPRY_UNDEFINED,
    ) -> Any:
        """Call a method on an instance, binding `self` in the execution environment."""
        fn = bm.fn
        # Generator methods: create a generator with self/this pre-bound in the closure
        if fn.is_generator:
            gen_closure = fn.closure.child()
            gen_closure.define("new.target", new_target, mutable=False)
            gen_closure.define("self", bm.instance, mutable=False)
            gen_closure.define("this", bm.instance, mutable=False)
            if hasattr(bm, "_defining_class") and bm._defining_class is not None:
                gen_closure.define("__current_class__", bm._defining_class, mutable=False)
            elif isinstance(bm.instance, SpryInstance):
                gen_closure.define("__current_class__", bm.instance.cls, mutable=False)
            bound_gen_fn = SpryFunction(
                name=fn.name,
                params=fn.params,
                body=fn.body,
                closure=gen_closure,
                defaults=fn.defaults,
                rest_param=fn.rest_param,
                is_async=getattr(fn, "is_async", False),
                is_generator=True,
            )
            return SpryGenerator(bound_gen_fn, args, self)
        child = fn.closure.child()
        child.define("new.target", new_target, mutable=False)
        # Bind self so methods can do self.field = val
        child.define("self", bm.instance, mutable=False)
        child.define("this", bm.instance, mutable=False)
        # Track which class's method we're currently executing — needed for multi-level super.
        # bm.fn.closure is the env where the method was defined (the class's instance_env child).
        # We store the "defining class" so that super resolves to *its* parent, not the instance's class.
        if hasattr(bm, "_defining_class") and bm._defining_class is not None:
            child.define("__current_class__", bm._defining_class, mutable=False)
        elif isinstance(bm.instance, SpryInstance):
            child.define("__current_class__", bm.instance.cls, mutable=False)
        # Also expose instance fields as direct mutable vars (for count += 1 style),
        # recording their initial values so we can sync back only what changed directly.
        initial_field_values: dict[str, Any] = {}
        for fname, fval in bm.instance.fields.items():
            if fname not in child._vars:
                child.define(fname, fval, mutable=True)
                initial_field_values[fname] = fval

        required = [
            p for p, _ in fn.params
            if p not in fn.defaults and not p.startswith("__destruct__") and not p.startswith("__array_destruct__")
        ]
        if len(args) < len(required):
            raise SpryRuntimeError(
                f"Method {fn.name!r} expects at least {len(required)} args, got {len(args)}", node
            )
        # Define `arguments` so methods can introspect all passed args (JS semantics)
        child.define("arguments", list(args), mutable=False)

        for i, (pname, _ptype) in enumerate(fn.params):
            if pname.startswith("__destruct__:"):
                field_specs = pname[len("__destruct__:"):].split(",")
                arg_val = args[i] if i < len(args) else {}
                if not isinstance(arg_val, dict):
                    raise SpryRuntimeError(
                        f"Method {fn.name!r} expects an object for destructured param, got {type(arg_val).__name__}", node
                    )
                for fspec in field_specs:
                    fspec = fspec.strip()
                    if "|" in fspec:
                        fkey, flocal = fspec.split("|", 1)
                    else:
                        fkey = flocal = fspec
                    # Apply default when key is absent (JS semantics: missing key, not null value)
                    if fkey not in arg_val:
                        default_key = f"__destruct_default__{flocal}"
                        fval = self._eval(fn.defaults[default_key], fn.closure) if default_key in fn.defaults else None
                    else:
                        fval = arg_val[fkey]
                    child.define(flocal, fval, mutable=False)
            elif pname.startswith("__array_destruct__:"):
                raw = pname[len("__array_destruct__:"):]
                arr_rest_name: str | None = None
                if "..." in raw:
                    raw, arr_rest_name = raw.split("...", 1)
                arr_field_names = [f for f in raw.split(",") if f]
                arg_val = args[i] if i < len(args) else []
                items = list(arg_val) if not isinstance(arg_val, list) else arg_val
                for _j, _fname in enumerate(arr_field_names):
                    child.define(_fname.strip(), items[_j] if _j < len(items) else None, mutable=False)
                if arr_rest_name:
                    child.define(arr_rest_name, items[len(arr_field_names):], mutable=False)
            else:
                if i < len(args):
                    child.define(pname, args[i], mutable=False)
                elif pname in fn.defaults:
                    default_val = self._eval(fn.defaults[pname], fn.closure)
                    child.define(pname, default_val, mutable=False)
                else:
                    child.define(pname, None, mutable=False)

        if fn.rest_param is not None:
            rest_vals = args[len(fn.params):]
            child.define(fn.rest_param, list(rest_vals), mutable=False)

        return_val = None
        try:
            self._exec_block(fn.body, child)
        except ReturnSignal as r:
            return_val = r.value

        # Sync back fields that were mutated directly (count += 1 style).
        # We only sync when the local var changed from its initial value — this
        # avoids overwriting mutations already applied via self.field = val.
        # Skip fields that share a name with a parameter (params shadow fields
        # and their value doesn't reflect the field mutation done via self.field = ...).
        param_names = {p for p, _ in fn.params}
        for fname, initial in initial_field_values.items():
            if fname in param_names:
                continue  # don't let param value overwrite self.field = val
            try:
                child_val = child.get(fname)
            except SpryRuntimeError:
                continue
            if child_val != initial:
                bm.instance.fields[fname] = child_val

        return return_val

    def _call_dict_bound_method(self, fn: "SpryFunction", obj: dict,
                                args: list, node: "Node") -> Any:
        """Call a SpryFunction with ``this`` bound to a plain dict object.

        Used for object-literal shorthand methods and getter/setter functions
        stored in a dict so that ``this.x`` inside the method resolves to the dict.
        """
        child = fn.closure.child()
        child.define("new.target", SPRY_UNDEFINED, mutable=False)
        child.define("self", obj, mutable=False)
        child.define("this", obj, mutable=False)

        required = [
            p for p, _ in fn.params
            if p not in fn.defaults and not p.startswith("__destruct__") and not p.startswith("__array_destruct__")
        ]
        if len(args) < len(required):
            raise SpryRuntimeError(
                f"Function {fn.name!r} expects at least {len(required)} args, got {len(args)}", node
            )

        for i, (pname, _ptype) in enumerate(fn.params):
            if i < len(args):
                child.define(pname, args[i], mutable=False)
            elif pname in fn.defaults:
                child.define(pname, self._eval(fn.defaults[pname], fn.closure), mutable=False)
            else:
                child.define(pname, None, mutable=False)

        if fn.rest_param is not None:
            child.define(fn.rest_param, list(args[len(fn.params):]), mutable=False)

        return_val = None
        try:
            self._exec_block(fn.body, child)
        except ReturnSignal as r:
            return_val = r.value

        # Sync back mutated dict properties (this.x = val style)
        # Walk the child env to detect property writes applied via MemberAssignment.
        # We don't sync local variables back to the dict — only explicit this.x = val
        # assignments already wrote directly into obj via MemberAssignment.

        return return_val

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def _exec_test_block(self, node: TestBlock, env: Environment) -> Any:
        """Execute a test block, collecting assertion results."""
        child = env.child()
        try:
            self._exec_block(node.body, child)
            self.logger.info(f"[TEST] PASS: {node.name!r}")
            return SpryResult(ok=True, value={"test": node.name, "passed": True})
        except AssertionError as e:
            self.logger.error(f"[TEST] FAIL: {node.name!r} — {e}")
            raise

    def _exec_expect(self, node: ExpectStatement, env: Environment) -> Any:
        """Execute an expect assertion."""
        from pathlib import Path

        if node.kind == "exists":
            path = str(self._eval(node.condition, env))
            exists = Path(path).exists()
            if node.negated:
                exists = not exists
            if not exists:
                what = "not to exist" if not node.negated else "to exist"
                raise AssertionError(f"Expected {path!r} {what}")
            return SpryResult(ok=True)

        if node.kind == "denied":
            # Execute the block, expect a PermissionError
            from .permissions import PermissionError as SpryPermError
            try:
                child = env.child()
                self._exec_block(node.block, child)
                raise AssertionError("Expected operation to be denied, but it succeeded")
            except (SpryPermError, PermissionError):
                return SpryResult(ok=True)

        if node.kind == "rollback":
            # Execute the block, expect an exception (rollback signal)
            try:
                child = env.child()
                self._exec_block(node.block, child)
                raise AssertionError("Expected rollback, but block succeeded")
            except AssertionError:
                raise
            except Exception:
                return SpryResult(ok=True)

        # kind == "truthy"
        value = self._eval(node.condition, env)
        result = self._truthy(value)
        if node.negated:
            result = not result
        if not result:
            raise AssertionError(f"Expectation failed: {value!r}")
        return SpryResult(ok=True)

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def _exec_atomic(self, node: AtomicStatement, env: Environment) -> Any:
        """Execute block atomically — on error, attempt cleanup."""
        child = env.child()
        try:
            return self._exec_block(node.body, child)
        except Exception as e:
            self.logger.error(f"Atomic block failed: {e}")
            raise

    def _exec_transaction(self, node: TransactionStatement, env: Environment) -> Any:
        """
        Execute a transaction block.
        If it fails and a compensate block exists, run the compensation.
        """
        # The target is a name/scope reference — evaluate gracefully
        try:
            target = self._eval(node.target, env)
        except SpryRuntimeError:
            # Target is just a name identifier (e.g., "filesystem", "db.main")
            if hasattr(node.target, "name"):
                target = node.target.name  # type: ignore
            else:
                target = str(node.target)
        child = env.child()
        try:
            result = self._exec_block(node.body, child)
            return result
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            if node.compensate is not None:
                self.logger.info("Running compensation logic")
                try:
                    comp_child = env.child()
                    self._exec_block(node.compensate, comp_child)
                except Exception as comp_e:
                    self.logger.error(f"Compensation also failed: {comp_e}")
            raise

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    def _validate(self, data: Any, schema: Any, env: Environment) -> SpryResult:
        """Basic schema validation — checks required fields exist."""
        if isinstance(data, dict) and isinstance(schema, dict):
            for key, expected_type in schema.items():
                if key not in data:
                    return SpryResult(ok=False, error=f"Missing required field: {key!r}")
        return SpryResult(ok=True, value=data)

    def _redact(self, data: Any, fields: list[str]) -> Any:
        """Redact specified fields from a dict."""
        if isinstance(data, dict):
            result = dict(data)
            for f in fields:
                if f in result:
                    result[f] = "[REDACTED]"
            return result
        return data

    # ------------------------------------------------------------------
    # Fraud check
    # ------------------------------------------------------------------

    def _exec_fraud_check(self, node: FraudCheckStatement, env: Environment) -> Any:
        target = self._eval(node.target, env)
        self.permissions.check("fraud.check")
        self.logger.info(
            f"[FRAUD-CHECK] target={target!r} reason={node.reason!r} "
            f"case={node.case_id!r} scope={node.scope!r}"
        )
        return SpryResult(ok=True, value={"target": target, "case": node.case_id})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _spry_type(value: Any) -> str:
        """Return the SpryCode type name for a value."""
        if value is None:
            return "Null"
        if isinstance(value, bool):
            return "Bool"
        if isinstance(value, (int, float)):
            return "Number"
        if isinstance(value, str):
            return "Text"
        if isinstance(value, list):
            return "List"
        if isinstance(value, dict):
            return "Map"
        if isinstance(value, SpryResult):
            return "Result"
        if isinstance(value, SpryMoney):
            return "Money"
        if isinstance(value, SprySecret):
            return "Secret"
        if isinstance(value, SpryInstance):
            return value.cls.name
        if isinstance(value, SpryClass):
            return "Class"
        if isinstance(value, SpryEnum):
            return "Enum"
        if isinstance(value, SpryStruct):
            return "Struct"
        if isinstance(value, (SpryFunction, SpryTask)):
            return "Function"
        return type(value).__name__

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, _SpryUndefinedType):
            return False
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, (list, dict)):
            return len(value) > 0
        if isinstance(value, SpryResult):
            return value.ok
        return True


# ---------------------------------------------------------------------------
# Helper objects for member access patterns
# ---------------------------------------------------------------------------


class _MoneyHelper:
    """Provides money.sum(...) etc."""

    def sum(self, items: list) -> SpryMoney:
        from .runtime.stdlib import _builtin_money_sum
        return _builtin_money_sum(items)


class _HttpHelper:
    """HTTP client with GET, POST, PUT, PATCH, DELETE, HEAD support."""

    def __init__(self, permissions: PermissionSet) -> None:
        self._perms = permissions

    def _request(self, method: str, url: str, body: Any = None, headers: dict | None = None) -> SpryResult:
        self._perms.check("network.request", url)
        try:
            import json as _json
            import urllib.request
            data: bytes | None = None
            if body is not None:
                if isinstance(body, (dict, list)):
                    data = _json.dumps(body).encode("utf-8")
                else:
                    data = str(body).encode("utf-8")
            req = urllib.request.Request(url, data=data, method=method.upper())
            if data is not None:
                req.add_header("Content-Type", "application/json")
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read().decode("utf-8")
                return SpryResult(ok=True, value={"status": resp.status, "body": resp_body})
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def get(self, url: str, headers: dict | None = None) -> SpryResult:
        return self._request("GET", url, headers=headers)

    def post(self, url: str, body: Any = None, headers: dict | None = None) -> SpryResult:
        return self._request("POST", url, body=body, headers=headers)

    def put(self, url: str, body: Any = None, headers: dict | None = None) -> SpryResult:
        return self._request("PUT", url, body=body, headers=headers)

    def patch(self, url: str, body: Any = None, headers: dict | None = None) -> SpryResult:
        return self._request("PATCH", url, body=body, headers=headers)

    def delete(self, url: str, headers: dict | None = None) -> SpryResult:
        return self._request("DELETE", url, headers=headers)

    def head(self, url: str, headers: dict | None = None) -> SpryResult:
        self._perms.check("network.request", url)
        try:
            import urllib.request
            req = urllib.request.Request(url, method="HEAD")
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return SpryResult(ok=True, value={"status": resp.status, "body": ""})
        except Exception as e:
            return SpryResult(ok=False, error=str(e))


# ---------------------------------------------------------------------------
# Global Namespace Objects
# ---------------------------------------------------------------------------


class _JsonNamespace:
    """JSON global namespace — JSON.stringify(), JSON.parse()."""

    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn  # interpreter._call_value for SpryFunction/SpryLambda

    def stringify(self, value: Any, replacer: Any = None, indent: Any = None) -> str:
        """Serialize a value to a JSON string."""
        import json as _json

        indent_val = int(indent) if indent is not None else None

        _OMIT = object()  # sentinel for values to omit from objects

        def _spry_to_json(obj: Any, in_array: bool = False) -> Any:
            """Recursively convert SpryCode values to JSON-serializable Python values."""
            if isinstance(obj, _SpryUndefinedType):
                # In arrays: undefined → null; in objects: omit (return sentinel)
                return None if in_array else _OMIT
            if isinstance(obj, (SpryFunction, SpryLambda, SpryMultiLambda, SpryTask)):
                # functions → undefined (omit from objects, null in arrays)
                return None if in_array else _OMIT
            if isinstance(obj, SpryInstance):
                result = {}
                for k, v in obj.fields.items():
                    if isinstance(k, SprySymbol) or callable(v):
                        continue
                    converted = _spry_to_json(v, in_array=False)
                    if converted is not _OMIT:
                        result[k] = converted
                return result
            if isinstance(obj, SpryMap):
                result = {}
                for k, v in obj._data.items():
                    if isinstance(k, SprySymbol):
                        continue
                    converted = _spry_to_json(v, in_array=False)
                    if converted is not _OMIT:
                        result[str(k)] = converted
                return result
            if isinstance(obj, SprySet):
                return [_spry_to_json(v, in_array=True) for v in obj._data]
            if isinstance(obj, list):
                return [_spry_to_json(v, in_array=True) for v in obj]
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    if isinstance(k, SprySymbol):
                        continue
                    converted = _spry_to_json(v, in_array=False)
                    if converted is not _OMIT:
                        result[k] = converted
                return result
            return obj

        # Convert SpryCode objects first so filters operate on plain dicts/lists
        value = _spry_to_json(value)

        # Apply array-key replacer filter
        if isinstance(replacer, list):
            allowed = set(str(k) for k in replacer)

            def _filter(obj: Any) -> Any:
                if isinstance(obj, dict):
                    return {k: _filter(v) for k, v in obj.items() if k in allowed}
                if isinstance(obj, list):
                    return [_filter(v) for v in obj]
                return obj
            value = _filter(value)

        # Apply function replacer
        if isinstance(replacer, (SpryFunction, SpryLambda, SpryMultiLambda)) or (
                callable(replacer) and not isinstance(replacer, list)):
            def _call_replacer(key: str, val_arg: Any) -> Any:
                if self._call_fn is not None and isinstance(
                        replacer, (SpryFunction, SpryLambda, SpryMultiLambda)):
                    return self._call_fn(replacer, [key, val_arg])
                if callable(replacer):
                    try:
                        return replacer(key, val_arg)
                    except Exception:
                        return val_arg
                return val_arg

            def _replace(key: str, obj: Any) -> Any:
                result = _call_replacer(key, obj)
                if isinstance(result, _SpryUndefinedType):
                    return _OMIT
                if isinstance(result, dict):
                    out = {}
                    for k, v in result.items():
                        r = _replace(k, v)
                        if r is not _OMIT:
                            out[k] = r
                    return out
                if isinstance(result, list):
                    return [_replace(str(i), v) for i, v in enumerate(result)]
                return result
            value = _replace("", value)

        # Use compact separators (no spaces) when no indent — matches JS JSON.stringify behavior
        separators = (',', ':') if indent_val is None else None
        try:
            return _json.dumps(value, indent=indent_val, separators=separators,
                               ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise ValueError(f"JSON.stringify error: {e}") from e

    def parse(self, text: str, reviver: Any = None) -> Any:
        """Parse a JSON string into a SpryCode value."""
        import json as _json
        try:
            result = _json.loads(text)
        except (TypeError, ValueError) as e:
            raise ValueError(f"JSON.parse error: {e}") from e
        if reviver is not None and callable(reviver):
            def _apply_reviver(obj: Any) -> Any:
                if isinstance(obj, dict):
                    return {k: reviver(k, _apply_reviver(v)) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [reviver(str(i), _apply_reviver(v)) for i, v in enumerate(obj)]
                return obj
            result = reviver("", _apply_reviver(result))
        return result

    def __repr__(self) -> str:
        return "JSON"


class _ArrayNamespace:
    """Array global namespace — Array.isArray(), Array.from(), Array.of()."""

    def isArray(self, value: Any) -> bool:
        """Return True if the value is a list."""
        return isinstance(value, list)

    def from_(self, iterable: Any, map_fn: Any = None) -> list:
        """Create an array from an iterable (range, string, etc.) with optional map function."""
        if isinstance(iterable, range):
            result = list(iterable)
        elif isinstance(iterable, str):
            result = list(iterable)
        elif isinstance(iterable, SpryMap):
            result = [[k, v] for k, v in iterable._data.items()]
        elif isinstance(iterable, SprySet):
            result = list(iterable._data)
        elif isinstance(iterable, (SpryInstance, SpryGenerator)):
            # Use _iter_to_list for SpryInstance (supports [Symbol.iterator]()) and generators
            result = self._interp._iter_to_list(iterable, None)
        elif isinstance(iterable, dict):
            # Check for Symbol.iterator or next() — use _iter_to_list which handles both
            sym_key = "Symbol('iterator')"
            has_sym_iter = any(
                (isinstance(k, SprySymbol) and k.description == "iterator") or k == sym_key
                for k in iterable.keys()
            )
            has_next = "next" in iterable
            if has_sym_iter or has_next:
                result = self._interp._iter_to_list(iterable, None)
            elif "length" in iterable:
                # Array-like: {length: N, "0": x, "1": y, ...}
                n = int(iterable["length"])
                result = []
                for i in range(max(n, 0)):
                    result.append(iterable.get(str(i), iterable.get(i, None)))
            else:
                try:
                    result = list(iterable)
                except TypeError:
                    result = []
        else:
            try:
                result = list(iterable)
            except TypeError:
                result = []
        if map_fn is not None:
            arity = getattr(map_fn, "_spry_arity", 1)
            if arity > 1:
                result = [map_fn(item, idx) for idx, item in enumerate(result)]
            else:
                result = [map_fn(item) for item in result]
        return result

    # Expose as 'from' attribute (Python reserved word workaround)
    def __getattr__(self, name: str) -> Any:
        if name == "from":
            return self.from_
        if name == "fromAsync":
            return self.fromAsync
        raise AttributeError(name)

    def fromAsync(self, iterable: Any, map_fn: Any = None) -> SpryPromise:
        """ES2024 Array.fromAsync — wrap Array.from result in a fulfilled Promise."""
        result = self.from_(iterable, map_fn)
        return SpryPromise(value=result)

    def of(self, *args: Any) -> list:
        """Create an array from arguments: Array.of(1, 2, 3) → [1, 2, 3]."""
        return list(args)

    def __call__(self, *args: Any) -> list:
        """Array(n) → sparse array of length n; Array(a, b, c) → [a, b, c].

        Matches JS semantics:
        - Single integer arg → list of that length filled with None.
        - Multiple args → list of those values.
        """
        if len(args) == 1 and isinstance(args[0], (int, float)) and not isinstance(args[0], bool):
            n = int(args[0])
            if n < 0:
                raise SpryRuntimeError(f"Invalid array length: {n}", None)
            return [None] * n
        return list(args)

    def __repr__(self) -> str:
        return "Array"


class _ObjectNamespace:
    """Object global namespace — Object.keys(), Object.values(), Object.assign(), etc."""

    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn
        self._sealed_ids: set = set()
        self._frozen_ids: set = set()

    def keys(self, obj: Any) -> list:
        """Return the string-keyed enumerable properties (excludes symbol keys)."""
        if isinstance(obj, dict):
            return [k for k in obj.keys()
                    if not isinstance(k, SprySymbol) and not str(k).startswith("__")]
        if isinstance(obj, SpryInstance):
            return [k for k in obj.fields if not k.startswith("__") and not callable(obj.fields[k]) and not isinstance(obj.fields[k], SpryFunction)]
        return []

    def values(self, obj: Any) -> list:
        """Return the values of an object/dict (excludes symbol-keyed entries)."""
        if isinstance(obj, dict):
            return [v for k, v in obj.items()
                    if not isinstance(k, SprySymbol) and not str(k).startswith("__")]
        if isinstance(obj, SpryInstance):
            return [v for k, v in obj.fields.items() if not k.startswith("__") and not callable(v) and not isinstance(v, SpryFunction)]
        return []

    def entries(self, obj: Any) -> list:
        """Return [[key, value], ...] pairs (excludes symbol-keyed entries)."""
        if isinstance(obj, dict):
            return [[k, v] for k, v in obj.items()
                    if not isinstance(k, SprySymbol) and not str(k).startswith("__")]
        if isinstance(obj, SpryInstance):
            return [[k, v] for k, v in obj.fields.items() if not k.startswith("__") and not callable(v) and not isinstance(v, SpryFunction)]
        return []

    def fromEntries(self, entries: Any) -> dict:
        """Create an object from [[key, value], ...] pairs or a Map."""
        if isinstance(entries, list):
            return {str(k): v for k, v in entries}
        if isinstance(entries, SpryMap):
            return {str(k): v for k, v in entries._data.items()}
        if isinstance(entries, SpryIterator):
            return {str(k): v for k, v in entries._iterator}
        return {}

    def assign(self, *objs: Any) -> Any:
        """Mutate the first object by merging all subsequent objects into it.

        Object.assign({a:1}, {b:2}, {c:3}) → mutates first arg, returns it.
        Supports both dict and SpryInstance targets.
        Also supports Object.assign(SomeClass.prototype, mix) to add mixin methods.
        """
        if not objs:
            return {}
        target = objs[0]
        for obj in objs[1:]:
            if isinstance(obj, dict):
                src_items = list((k, v) for k, v in obj.items() if not k.startswith("__spry_") and not k.startswith("__non_extensible"))
                if isinstance(target, dict):
                    for k, v in src_items:
                        target[k] = v
                elif isinstance(target, SpryInstance):
                    for k, v in src_items:
                        target.fields[k] = v
                elif isinstance(target, SpryClassPrototype):
                    for k, v in src_items:
                        target._extra_fields[k] = v
            elif isinstance(obj, SpryInstance):
                src_items2 = list((k, v) for k, v in obj.fields.items() if not k.startswith("__"))
                if isinstance(target, dict):
                    for k, v in src_items2:
                        target[k] = v
                elif isinstance(target, SpryInstance):
                    for k, v in src_items2:
                        target.fields[k] = v
                elif isinstance(target, SpryClassPrototype):
                    for k, v in src_items2:
                        target._extra_fields[k] = v
        return target

    def create(self, proto: Any = None, props: Any = None) -> dict:
        """Create a new object with the given prototype (values are copied in)."""
        result: dict = {}
        if proto is not None and proto is not False and isinstance(proto, dict):
            # Track the prototype so getPrototypeOf can return it
            result["__spry_proto__"] = proto
        # Apply property descriptors if provided
        if isinstance(props, dict):
            for key, descriptor in props.items():
                self.defineProperty(result, key, descriptor)
        return result

    def hasOwn(self, obj: Any, key: str) -> bool:
        """Return True if the object has the given own property."""
        if isinstance(obj, dict):
            return key in obj
        return False

    def defineProperty(self, obj: Any, key: str, descriptor: Any) -> Any:
        """Define/modify a property on an object. Mutates and returns obj."""
        key_str = str(key)
        _callable_types = (SpryFunction, SpryLambda, SpryMultiLambda, BoundMethod)
        if isinstance(descriptor, dict):
            if "value" in descriptor:
                if isinstance(obj, dict):
                    obj[key_str] = descriptor["value"]
                elif isinstance(obj, SpryInstance):
                    obj.fields[key_str] = descriptor["value"]
            if "get" in descriptor and (callable(descriptor["get"]) or isinstance(descriptor["get"], _callable_types)):
                getter_key = f"__getter__{key_str}"
                if isinstance(obj, dict):
                    obj[getter_key] = descriptor["get"]
                elif isinstance(obj, SpryInstance):
                    obj.fields[getter_key] = descriptor["get"]
            if "set" in descriptor and (callable(descriptor["set"]) or isinstance(descriptor["set"], _callable_types)):
                setter_key = f"__setter__{key_str}"
                if isinstance(obj, dict):
                    obj[setter_key] = descriptor["set"]
                elif isinstance(obj, SpryInstance):
                    obj.fields[setter_key] = descriptor["set"]
        return obj

    def getOwnPropertyDescriptor(self, obj: Any, key: str) -> Any:
        """Return a property descriptor dict, including accessor descriptors."""
        key_str = str(key)
        getter_key = f"__getter__{key_str}"
        setter_key = f"__setter__{key_str}"
        if isinstance(obj, dict):
            has_getter = getter_key in obj
            has_setter = setter_key in obj
            if has_getter or has_setter:
                desc: dict = {"enumerable": True, "configurable": True}
                if has_getter:
                    desc["get"] = obj[getter_key]
                if has_setter:
                    desc["set"] = obj[setter_key]
                return desc
            if key_str in obj:
                return {"value": obj[key_str], "writable": True, "enumerable": True, "configurable": True}
        elif isinstance(obj, SpryInstance):
            has_getter = getter_key in obj.fields
            has_setter = setter_key in obj.fields
            if has_getter or has_setter:
                desc = {"enumerable": True, "configurable": True}
                if has_getter:
                    desc["get"] = obj.fields[getter_key]
                if has_setter:
                    desc["set"] = obj.fields[setter_key]
                return desc
            if key_str in obj.fields:
                return {"value": obj.fields[key_str], "writable": True, "enumerable": True, "configurable": True}
        return None

    def defineProperties(self, obj: Any, props: Any) -> Any:
        """Define multiple properties at once."""
        if isinstance(obj, dict) and isinstance(props, dict):
            for k, descriptor in props.items():
                self.defineProperty(obj, k, descriptor)
        return obj

    def preventExtensions(self, obj: Any) -> Any:
        """Mark an object as non-extensible (no new properties allowed)."""
        if isinstance(obj, dict):
            obj["__non_extensible__"] = True
        elif isinstance(obj, SpryInstance):
            obj.fields["__non_extensible__"] = True
        return obj

    def isExtensible(self, obj: Any) -> bool:
        """Return True if the object is extensible."""
        if id(obj) in self._frozen_ids or id(obj) in self._sealed_ids:
            return False
        if isinstance(obj, dict):
            return not obj.get("__non_extensible__", False)
        if isinstance(obj, SpryInstance):
            return not obj.fields.get("__non_extensible__", False)
        return False

    def seal(self, obj: Any) -> Any:
        """Seal an object (no new properties). Tracks via id set."""
        self._sealed_ids.add(id(obj))
        return obj

    def isSealed(self, obj: Any) -> bool:
        """Return True if the object is sealed or frozen."""
        return id(obj) in self._sealed_ids or id(obj) in self._frozen_ids

    def freeze(self, obj: Any) -> Any:
        """Freeze an object (non-writable, non-extensible). Tracks via id set."""
        self._frozen_ids.add(id(obj))
        return obj

    def isFrozen(self, obj: Any) -> bool:
        """Return True if the object has been frozen via Object.freeze()."""
        return id(obj) in self._frozen_ids

    def pick(self, obj: Any, *keys: Any) -> dict:
        """Return a new object with only the specified keys."""
        if not isinstance(obj, dict):
            return {}
        # Accept either multiple positional args or a single list arg
        if len(keys) == 1 and isinstance(keys[0], list):
            keys = tuple(str(k) for k in keys[0])
        return {k: obj[k] for k in keys if k in obj}

    def omit(self, obj: Any, *keys: Any) -> dict:
        """Return a new object without the specified keys."""
        if not isinstance(obj, dict):
            return {}
        if len(keys) == 1 and isinstance(keys[0], list):
            keys = tuple(str(k) for k in keys[0])
        omit_set = set(keys)
        return {k: v for k, v in obj.items() if k not in omit_set}

    def mapKeys(self, obj: Any, fn: Any) -> dict:
        """Return a new object with keys transformed by fn."""
        if not isinstance(obj, dict):
            return {}
        return {fn(k): v for k, v in obj.items()}

    def mapValues(self, obj: Any, fn: Any) -> dict:
        """Return a new object with values transformed by fn."""
        if not isinstance(obj, dict):
            return {}
        return {k: fn(v) for k, v in obj.items()}

    def invert(self, obj: Any) -> dict:
        """Return a new object with keys and values swapped."""
        if not isinstance(obj, dict):
            return {}
        return {str(v): k for k, v in obj.items()}

    def deepClone(self, obj: Any) -> Any:
        """Return a deep copy of the value."""
        import copy as _copy
        return _copy.deepcopy(obj)

    def deepMerge(self, base: Any, *overrides: Any) -> dict:
        """Recursively merge objects. Later objects override earlier ones."""
        import copy as _copy

        def _merge(a: dict, b: dict) -> dict:
            result = _copy.deepcopy(a)
            for k, v in b.items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = _merge(result[k], v)
                else:
                    result[k] = _copy.deepcopy(v)
            return result

        result = base if isinstance(base, dict) else {}
        for override in overrides:
            if isinstance(override, dict):
                result = _merge(result, override)
        return result

    def getOwnPropertyNames(self, obj: Any) -> list:
        """Return a list of all own property names."""
        if isinstance(obj, dict):
            return list(obj.keys())
        return []

    def is_(self, a: Any, b: Any) -> bool:
        """SameValue comparison — like === but NaN===NaN and -0!==+0."""
        # null and undefined are distinct in SameValue (strict equality)
        if a is None and isinstance(b, _SpryUndefinedType):
            return False
        if isinstance(a, _SpryUndefinedType) and b is None:
            return False
        if isinstance(a, float) and isinstance(b, float):
            if math.isnan(a) and math.isnan(b):
                return True
        if a == 0 and b == 0:
            # Distinguish +0 and -0
            return math.copysign(1.0, float(a)) == math.copysign(1.0, float(b))
        return a is b or a == b

    def groupBy(self, arr: Any, key_fn: Any) -> dict:
        """Group array elements by the result of key_fn. Returns a plain dict."""
        result: dict = {}
        items = list(arr) if not isinstance(arr, list) else arr
        for item in items:
            key = key_fn(item) if callable(key_fn) else str(item)
            key = str(key) if not isinstance(key, str) else key
            if key not in result:
                result[key] = []
            result[key].append(item)
        return result

    def getPrototypeOf(self, obj: Any) -> Any:
        """Return the prototype of an object.

        For objects created with Object.create(proto), returns proto.
        For SpryInstances, returns the class prototype (ClassName.prototype).
        For plain objects/instances/null, returns None.
        """
        if isinstance(obj, dict) and "__spry_proto__" in obj:
            return obj["__spry_proto__"]
        if isinstance(obj, SpryInstance):
            return obj.cls.prototype
        return None

    def setPrototypeOf(self, obj: Any, proto: Any) -> Any:
        """No-op — SpryCode does not support prototype chains."""
        return obj

    def getOwnPropertySymbols(self, obj: Any) -> list:
        """Return SprySymbol keys from dicts and SpryInstance.fields."""
        if isinstance(obj, dict):
            return [k for k in obj.keys() if isinstance(k, SprySymbol)]
        if isinstance(obj, SpryInstance):
            return [k for k in obj.fields.keys() if isinstance(k, SprySymbol)]
        return []

    def getOwnPropertyDescriptors(self, obj: Any) -> dict:
        """Return descriptors for all own properties."""
        if isinstance(obj, dict):
            return {k: {"value": v, "writable": True, "enumerable": True, "configurable": True}
                    for k, v in obj.items()}
        return {}

    def __getattr__(self, prop: str) -> Any:
        if prop == "is":
            return self.is_
        if prop == "prototype":
            proto = _ObjectPrototype(self, call_fn=self._call_fn)
            object.__setattr__(self, "prototype", proto)
            return proto
        raise AttributeError(prop)

    def __repr__(self) -> str:
        return "Object"


class _ObjectPrototype:
    """Object.prototype — provides hasOwnProperty and toString for .call() usage."""

    def __init__(self, obj_ns: Any, call_fn: Any = None) -> None:
        self._obj_ns = obj_ns
        self._call_fn = call_fn

    @property
    def hasOwnProperty(self) -> "_ObjectPrototypeHasOwnProperty":
        return _ObjectPrototypeHasOwnProperty()

    @property
    def toString(self) -> "_ObjectPrototypeToString":
        return _ObjectPrototypeToString(call_fn=self._call_fn)

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "hasOwnProperty":
            return self.hasOwnProperty
        if prop == "toString":
            return self.toString
        raise SpryRuntimeError(f"Object.prototype has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "Object.prototype"


class _ObjectPrototypeHasOwnProperty:
    """Object.prototype.hasOwnProperty — supports .call(obj, key)."""

    def call(self, obj: Any, key: Any) -> bool:
        return _owns_prop(obj, str(key))

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "call":
            return self.call
        raise SpryRuntimeError(f"Object.prototype.hasOwnProperty has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "hasOwnProperty"


class _ObjectPrototypeToString:
    """Object.prototype.toString — supports .call(obj) to return [object Tag]."""

    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn

    def call(self, obj: Any) -> str:
        if obj is None:
            return "[object Null]"
        if obj is SPRY_UNDEFINED:
            return "[object Undefined]"
        if isinstance(obj, bool):
            return "[object Boolean]"
        if isinstance(obj, (int, float)):
            return "[object Number]"
        if isinstance(obj, str):
            return "[object String]"
        if isinstance(obj, list):
            return "[object Array]"
        if isinstance(obj, SpryInstance):
            # Check for [Symbol.toStringTag] getter or plain field
            _tag_key = "Symbol('toStringTag')"
            _getter_key = f"__getter__{_tag_key}"
            if _getter_key in obj.fields:
                getter_fn = obj.fields[_getter_key]
                if self._call_fn is not None:
                    try:
                        tag = self._call_fn(getter_fn, [])
                        return f"[object {tag}]" if isinstance(tag, str) else "[object Object]"
                    except Exception:
                        pass
                return "[object Object]"
            if _tag_key in obj.fields:
                tag = obj.fields[_tag_key]
                return f"[object {tag}]" if isinstance(tag, str) else "[object Object]"
            return "[object Object]"
        if isinstance(obj, dict):
            _tag_key = "Symbol('toStringTag')"
            if _tag_key in obj:
                return f"[object {obj[_tag_key]}]"
            return "[object Object]"
        if callable(obj) or isinstance(obj, (SpryFunction, SpryLambda)):
            return "[object Function]"
        if isinstance(obj, SpryMap):
            return "[object Map]"
        if isinstance(obj, SprySet):
            return "[object Set]"
        return "[object Object]"

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "call":
            return self.call
        raise SpryRuntimeError(f"Object.prototype.toString has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "toString"


class _NumberNamespace:
    """Number global namespace — Number.isInteger(), Number.isNaN(), Number.isFinite(), etc."""

    MAX_VALUE: float = 1.7976931348623157e+308   # largest finite float64
    MIN_VALUE: float = 5e-324                    # smallest positive float64 (JS Number.MIN_VALUE)
    MAX_SAFE_INTEGER: int = 2 ** 53 - 1
    MIN_SAFE_INTEGER: int = -(2 ** 53 - 1)
    POSITIVE_INFINITY: float = float("inf")
    NEGATIVE_INFINITY: float = float("-inf")
    NaN: float = float("nan")
    EPSILON: float = 2.220446049250313e-16

    def isInteger(self, value: Any) -> bool:
        """Return True if the value is an integer (no fractional part)."""
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, float):
            return value == int(value) and not math.isinf(value) and not math.isnan(value)
        return False

    def isNaN(self, value: Any) -> bool:
        """Return True if the value is NaN."""
        if isinstance(value, float):
            return math.isnan(value)
        return False

    def isFinite(self, value: Any) -> bool:
        """Return True if the value is a finite number."""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return math.isfinite(value)
        return False

    def isSafeInteger(self, value: Any) -> bool:
        """Return True if the value is a safe integer (within ±2^53-1)."""
        if not self.isInteger(value):
            return False
        return abs(int(value)) <= 2 ** 53 - 1

    def parseInt(self, s: Any, base: Any = None) -> Any:
        """Parse a string as an integer (JS-style: stop at first non-digit)."""
        import re as _re
        s_str = str(s).strip()
        if not s_str:
            return float("nan")
        if base is None or int(base) == 16:
            if s_str.startswith("0x") or s_str.startswith("0X"):
                m = _re.match(r"0[xX]([0-9a-fA-F]+)", s_str)
                return int(m.group(1), 16) if m else float("nan")
        if base is None or int(base) == 8:
            if s_str.startswith("0o") or s_str.startswith("0O"):
                m = _re.match(r"0[oO]([0-7]+)", s_str)
                return int(m.group(1), 8) if m else float("nan")
        if base is None or int(base) == 2:
            if s_str.startswith("0b") or s_str.startswith("0B"):
                m = _re.match(r"0[bB]([01]+)", s_str)
                return int(m.group(1), 2) if m else float("nan")
        actual_base = 10 if base is None else int(base)
        if actual_base == 10:
            m = _re.match(r"[+-]?\d+", s_str)
        else:
            m = _re.match(r"[+-]?[0-9a-zA-Z]+", s_str)
        if not m:
            return float("nan")
        try:
            return int(m.group(0), actual_base)
        except ValueError:
            return float("nan")

    def parseFloat(self, s: Any) -> float:
        """Parse a string as a float (JS-style: stop at first non-numeric)."""
        import re as _re
        s_str = str(s).strip()
        if not s_str:
            return float("nan")
        m = _re.match(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", s_str)
        if not m:
            return float("nan")
        try:
            return float(m.group(0))
        except ValueError:
            return float("nan")

    def toFixed(self, value: Any, digits: int = 0) -> str:
        """Format a number with a fixed number of decimal places."""
        return f"{float(value):.{int(digits)}f}"

    def clamp(self, value: Any, lo: Any, hi: Any) -> Any:
        """Clamp value between lo and hi."""
        return max(lo, min(hi, value))

    def lerp(self, a: Any, b: Any, t: Any) -> float:
        """Linear interpolation between a and b at fraction t."""
        return float(a) + (float(b) - float(a)) * float(t)

    def random(self, lo: Any = 0, hi: Any = 1) -> float:
        """Return a random float in [lo, hi)."""
        import random as _random
        return _random.uniform(float(lo), float(hi))

    def range(self, start: Any, stop: Any = None, step: Any = 1) -> list:
        """Return a list of numbers from start to stop (exclusive) with step."""
        if stop is None:
            start, stop = 0, start
        return list(range(int(start), int(stop), int(step)))

    def __repr__(self) -> str:
        return "Number"

    def __call__(self, val: Any) -> Any:
        """Number(x) — convert x to a number."""
        if val is None:
            return 0
        if isinstance(val, bool):
            return 1 if val else 0
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, str):
            try:
                s = val.strip()
                v = float(s)
                if v == int(v) and 'e' not in s.lower() and '.' not in s:
                    return int(v)
                return v
            except (ValueError, OverflowError):
                return float('nan')
        return float('nan')


class _MathHelper:
    """math namespace: math.abs, math.floor, math.PI, etc.

    Provides a comprehensive set of mathematical functions suitable for
    algebra, trigonometry, number theory, statistics and geometry.
    """

    # ── Constants ────────────────────────────────────────────────────────────
    PI: float = math.pi
    E: float = math.e
    TAU: float = math.tau
    INF: float = float("inf")
    INFINITY: float = float("inf")
    NAN: float = float("nan")
    SQRT2: float = math.sqrt(2)
    SQRT1_2: float = math.sqrt(0.5)
    PHI: float = (1 + math.sqrt(5)) / 2          # golden ratio
    LN2: float = math.log(2)
    LN10: float = math.log(10)
    LOG2E: float = math.log2(math.e)
    LOG10E: float = math.log10(math.e)
    EPSILON: float = 2.220446049250313e-16        # machine epsilon (float64)

    # Lowercase aliases (SpryCode convention)
    pi: float = math.pi
    e: float = math.e
    tau: float = math.tau
    inf: float = float("inf")
    infinity: float = float("inf")
    nan: float = float("nan")
    sqrt2: float = math.sqrt(2)
    phi: float = (1 + math.sqrt(5)) / 2
    ln2: float = math.log(2)
    ln10: float = math.log(10)

    # ── Basic arithmetic ─────────────────────────────────────────────────────

    def abs(self, x: Any) -> Any:
        return abs(x)

    def floor(self, x: Any) -> int:
        return math.floor(x)

    def ceil(self, x: Any) -> int:
        return math.ceil(x)

    def round(self, x: Any, digits: int = 0) -> Any:
        return round(x, digits) if digits else round(x)

    def roundTo(self, x: Any, digits: int = 0) -> Any:
        """Round x to `digits` decimal places."""
        return round(float(x), int(digits))

    def toSF(self, x: Any, sig_figs: int = 3) -> float:
        """Round x to `sig_figs` significant figures."""
        if x == 0:
            return 0.0
        import math as _m
        d = _m.ceil(_m.log10(abs(float(x))))
        power = sig_figs - d
        factor = 10 ** power
        return round(float(x) * factor) / factor

    def trunc(self, x: Any) -> int:
        return math.trunc(x)

    def sign(self, x: Any) -> int:
        if x > 0:
            return 1
        if x < 0:
            return -1
        return 0

    def frac(self, x: Any) -> float:
        """Fractional part of x (always non-negative)."""
        return math.modf(float(x))[0]

    def intDiv(self, a: Any, b: Any) -> int:
        """Integer (floor) division: intDiv(10, 3) == 3."""
        return int(a) // int(b)

    def mod(self, a: Any, b: Any) -> Any:
        """Modulo — same as the % operator."""
        return a % b

    def clamp(self, x: Any, lo: Any, hi: Any) -> Any:
        return max(lo, min(hi, x))

    def lerp(self, a: Any, b: Any, t: Any) -> float:
        """Linear interpolation: lerp(0, 10, 0.5) == 5.0."""
        return float(a) + float(t) * (float(b) - float(a))

    def isEven(self, n: Any) -> bool:
        return int(n) % 2 == 0

    def isOdd(self, n: Any) -> bool:
        return int(n) % 2 != 0

    def isInteger(self, x: Any) -> bool:
        return isinstance(x, int) or (isinstance(x, float) and x == int(x))

    def isFinite(self, x: Any) -> bool:
        return math.isfinite(float(x))

    def isNaN(self, x: Any) -> bool:
        return isinstance(x, float) and math.isnan(x)

    def isBetween(self, x: Any, lo: Any, hi: Any) -> bool:
        """True iff lo <= x <= hi."""
        return float(lo) <= float(x) <= float(hi)

    # ── Powers, roots & exponentials ─────────────────────────────────────────

    def sqrt(self, x: Any) -> float:
        return math.sqrt(x)

    def cbrt(self, x: Any) -> float:
        """Cube root (handles negative x)."""
        v = float(x)
        return math.copysign(abs(v) ** (1 / 3), v)

    def nthRoot(self, x: Any, n: Any) -> float:
        """n-th root of x (handles negative x when n is odd)."""
        v, nn = float(x), float(n)
        if v < 0 and nn % 2 == 1:
            return -(-v) ** (1 / nn)
        return v ** (1 / nn)

    def pow(self, base: Any, exp: Any) -> Any:
        return base ** exp

    def exp(self, x: Any) -> float:
        """e raised to the power x."""
        return math.exp(float(x))

    def expm1(self, x: Any) -> float:
        """exp(x) - 1  (numerically stable for small x)."""
        return math.expm1(float(x))

    # ── Logarithms ───────────────────────────────────────────────────────────

    def log(self, x: Any, base: Any = None) -> float:
        return math.log(x, base) if base is not None else math.log(x)

    def ln(self, x: Any) -> float:
        """Natural logarithm (base e)."""
        return math.log(float(x))

    def log1p(self, x: Any) -> float:
        """ln(1 + x)  (numerically stable for small x)."""
        return math.log1p(float(x))

    def log2(self, x: Any) -> float:
        return math.log2(x)

    def log10(self, x: Any) -> float:
        return math.log10(x)

    def logN(self, x: Any, base: Any) -> float:
        """Logarithm of x in any base: logN(8, 2) == 3."""
        return math.log(float(x), float(base))

    # ── Trigonometry (radians) ────────────────────────────────────────────────

    def sin(self, x: Any) -> float:
        return math.sin(x)

    def cos(self, x: Any) -> float:
        return math.cos(x)

    def tan(self, x: Any) -> float:
        return math.tan(x)

    def asin(self, x: Any) -> float:
        return math.asin(float(x))

    def acos(self, x: Any) -> float:
        return math.acos(float(x))

    def atan(self, x: Any) -> float:
        return math.atan(float(x))

    def atan2(self, y: Any, x: Any) -> float:
        """atan2(y, x) — angle in radians of the vector (x, y)."""
        return math.atan2(float(y), float(x))

    def sinh(self, x: Any) -> float:
        return math.sinh(float(x))

    def cosh(self, x: Any) -> float:
        return math.cosh(float(x))

    def tanh(self, x: Any) -> float:
        return math.tanh(float(x))

    def asinh(self, x: Any) -> float:
        return math.asinh(float(x))

    def acosh(self, x: Any) -> float:
        return math.acosh(float(x))

    def atanh(self, x: Any) -> float:
        return math.atanh(float(x))

    def sec(self, x: Any) -> float:
        """Secant: 1 / cos(x)."""
        return 1 / math.cos(float(x))

    def csc(self, x: Any) -> float:
        """Cosecant: 1 / sin(x)."""
        return 1 / math.sin(float(x))

    def cot(self, x: Any) -> float:
        """Cotangent: 1 / tan(x)."""
        return 1 / math.tan(float(x))

    def hypot(self, *args: Any) -> float:
        """Euclidean distance: hypot(3, 4) == 5."""
        return math.hypot(*[float(a) for a in args])

    # ── Angle conversions ─────────────────────────────────────────────────────

    def degToRad(self, deg: Any) -> float:
        return math.radians(float(deg))

    def radToDeg(self, rad: Any) -> float:
        return math.degrees(float(rad))

    # aliases
    def toRadians(self, deg: Any) -> float:
        return math.radians(float(deg))

    def toDegrees(self, rad: Any) -> float:
        return math.degrees(float(rad))

    # ── Random ────────────────────────────────────────────────────────────────

    def random(self) -> float:
        """Return a random float in [0, 1)."""
        import random as _random
        return _random.random()

    def randomInt(self, a: Any, b: Any) -> int:
        """Return a random integer in [a, b] inclusive."""
        import random as _random
        return _random.randint(int(a), int(b))

    def shuffle(self, lst: Any) -> list:
        """Return a shuffled copy of the list."""
        import random as _random
        result = list(lst)
        _random.shuffle(result)
        return result

    def sample(self, lst: Any, k: int = 1) -> list:
        """Return k random samples from the list without replacement."""
        import random as _random
        return _random.sample(list(lst), int(k))

    # ── min / max ─────────────────────────────────────────────────────────────

    def min(self, *args: Any) -> Any:
        if len(args) == 1:
            # Single argument must be an iterable (e.g. a list of numbers)
            if not hasattr(args[0], "__iter__") or isinstance(args[0], str):
                raise TypeError(f"math.min() requires at least 2 arguments or an iterable, got {type(args[0]).__name__}")
            return min(args[0])
        return min(*args)

    def max(self, *args: Any) -> Any:
        if len(args) == 1:
            if not hasattr(args[0], "__iter__") or isinstance(args[0], str):
                raise TypeError(f"math.max() requires at least 2 arguments or an iterable, got {type(args[0]).__name__}")
            return max(args[0])
        return max(*args)

    def sum(self, lst: Any) -> Any:
        """Sum all values in a list."""
        return sum(lst)

    def product(self, lst: Any) -> Any:
        """Multiply all values in a list."""
        result = 1
        for v in lst:
            result *= v
        return result

    # ── Number theory ─────────────────────────────────────────────────────────

    def gcd(self, a: Any, b: Any) -> int:
        return math.gcd(int(a), int(b))

    def lcm(self, a: Any, b: Any) -> int:
        a, b = int(a), int(b)
        return abs(a * b) // math.gcd(a, b) if a and b else 0

    def factorial(self, n: Any) -> int:
        return math.factorial(int(n))

    def fibonacci(self, n: Any) -> int:
        """Return the n-th Fibonacci number (0-indexed: fib(0)=0, fib(1)=1)."""
        n = int(n)
        if n < 0:
            raise ValueError("fibonacci requires n >= 0")
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    def isPrime(self, n: Any) -> bool:
        """Return True if n is a prime number."""
        n = int(n)
        if n < 2:
            return False
        if n == 2:
            return True
        if n % 2 == 0:
            return False
        limit = int(math.isqrt(n))
        for i in range(3, limit + 1, 2):
            if n % i == 0:
                return False
        return True

    def isPerfect(self, n: Any) -> bool:
        """Return True if n is a perfect number (sum of proper divisors equals n)."""
        n = int(n)
        if n < 2:
            return False
        return sum(i for i in range(1, n) if n % i == 0) == n

    def primes(self, limit: Any) -> list:
        """Return all prime numbers up to (and including) limit using the Sieve of Eratosthenes."""
        n = int(limit)
        if n < 2:
            return []
        sieve = bytearray([1]) * (n + 1)
        sieve[0] = sieve[1] = 0
        for i in range(2, int(math.isqrt(n)) + 1):
            if sieve[i]:
                sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
        return [i for i, v in enumerate(sieve) if v]

    def primeFactors(self, n: Any) -> list:
        """Return the prime factorization of n as a sorted list."""
        n = int(n)
        factors: list = []
        d = 2
        while d * d <= n:
            while n % d == 0:
                factors.append(d)
                n //= d
            d += 1
        if n > 1:
            factors.append(n)
        return factors

    def combination(self, n: Any, k: Any) -> int:
        """Binomial coefficient C(n, k) = n! / (k! * (n-k)!)."""
        return math.comb(int(n), int(k))

    def permutation(self, n: Any, k: Any) -> int:
        """Number of permutations P(n, k) = n! / (n-k)!."""
        return math.perm(int(n), int(k))

    def bernoulli(self, n: Any) -> float:
        """Return the n-th Bernoulli number (B0=1, B1=-1/2 convention)."""
        n = int(n)
        if n < 0:
            raise ValueError("bernoulli requires n >= 0")
        # Use the recursive formula
        from fractions import Fraction
        B: list = [Fraction(0)] * (n + 1)
        B[0] = Fraction(1)
        for m in range(1, n + 1):
            B[m] = -sum(math.comb(m + 1, k) * B[k] for k in range(m)) / (m + 1)
        return float(B[n])

    def divisors(self, n: Any) -> list:
        """Return all positive divisors of n in sorted order."""
        n = int(n)
        divs = sorted(set(
            d
            for i in range(1, int(math.isqrt(n)) + 1)
            if n % i == 0
            for d in (i, n // i)
        ))
        return divs

    def totient(self, n: Any) -> int:
        """Euler's totient function φ(n): count of integers 1..n coprime to n."""
        n = int(n)
        result = n
        p = 2
        tmp = n
        while p * p <= tmp:
            if tmp % p == 0:
                while tmp % p == 0:
                    tmp //= p
                result -= result // p
            p += 1
        if tmp > 1:
            result -= result // tmp
        return result

    # ── Digit utilities ────────────────────────────────────────────────────────

    def digits(self, n: Any) -> list:
        """Return the decimal digits of n as a list: digits(1234) == [1,2,3,4]."""
        return [int(d) for d in str(abs(int(n)))]

    def sumDigits(self, n: Any) -> int:
        """Sum of decimal digits: sumDigits(1234) == 10."""
        return sum(int(d) for d in str(abs(int(n))))

    def reverseDigits(self, n: Any) -> int:
        """Reverse the digits of n: reverseDigits(1234) == 4321."""
        return int(str(abs(int(n)))[::-1])

    def isPalindrome(self, n: Any) -> bool:
        """True if the decimal representation of n is a palindrome."""
        s = str(abs(int(n)))
        return s == s[::-1]

    # ── Statistics ────────────────────────────────────────────────────────────

    def mean(self, lst: Any) -> float:
        """Arithmetic mean of a list."""
        data = list(lst)
        if not data:
            raise ValueError("mean() requires a non-empty list")
        return sum(data) / len(data)

    def median(self, lst: Any) -> float:
        """Median of a list."""
        data = sorted(lst)
        n = len(data)
        if n == 0:
            raise ValueError("median() requires a non-empty list")
        mid = n // 2
        return float(data[mid]) if n % 2 else (data[mid - 1] + data[mid]) / 2.0

    def mode(self, lst: Any) -> Any:
        """Most frequent value in a list (first one if tied)."""
        data = list(lst)
        if not data:
            raise ValueError("mode() requires a non-empty list")
        freq: dict = {}
        for v in data:
            freq[v] = freq.get(v, 0) + 1
        return max(freq, key=lambda k: freq[k])

    def variance(self, lst: Any, population: bool = True) -> float:
        """Variance of a list (population by default; pass False for sample)."""
        data = [float(x) for x in lst]
        n = len(data)
        if n < 2:
            raise ValueError("variance() requires at least 2 values")
        m = sum(data) / n
        denom = n if population else n - 1
        return sum((x - m) ** 2 for x in data) / denom

    def stdDev(self, lst: Any, population: bool = True) -> float:
        """Standard deviation of a list."""
        return math.sqrt(self.variance(lst, population))

    def range(self, lst: Any) -> Any:  # type: ignore[override]
        """Statistical range: max - min of a list."""
        data = list(lst)
        return max(data) - min(data)

    def percentile(self, lst: Any, p: Any) -> float:
        """p-th percentile of a list (linear interpolation, 0 <= p <= 100)."""
        data = sorted(float(x) for x in lst)
        n = len(data)
        if n == 0:
            raise ValueError("percentile() requires a non-empty list")
        rank = float(p) / 100 * (n - 1)
        lo, hi = int(rank), min(int(rank) + 1, n - 1)
        frac_part = rank - lo
        return data[lo] + frac_part * (data[hi] - data[lo])

    def quartiles(self, lst: Any) -> list:
        """Return [Q1, Q2, Q3] of the list."""
        return [self.percentile(lst, 25), self.percentile(lst, 50), self.percentile(lst, 75)]

    def correlation(self, xs: Any, ys: Any) -> float:
        """Pearson correlation coefficient between two equal-length lists."""
        xs_f = [float(x) for x in xs]
        ys_f = [float(y) for y in ys]
        n = len(xs_f)
        if n != len(ys_f) or n < 2:
            raise ValueError("correlation() requires two equal-length lists of length >= 2")
        mx, my = sum(xs_f) / n, sum(ys_f) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs_f, ys_f))
        denom = math.sqrt(sum((x - mx) ** 2 for x in xs_f) * sum((y - my) ** 2 for y in ys_f))
        return num / denom if denom else 0.0

    def dot(self, a: Any, b: Any) -> float:
        """Dot product of two equal-length lists."""
        return sum(float(x) * float(y) for x, y in zip(a, b))

    def normalize(self, lst: Any) -> list:
        """Normalize a list to [0, 1] range."""
        data = [float(x) for x in lst]
        lo, hi = min(data), max(data)
        if hi == lo:
            return [0.0] * len(data)
        return [(x - lo) / (hi - lo) for x in data]

    # ── Series & sequences ─────────────────────────────────────────────────────

    def arithmetic(self, start: Any, diff: Any, n: Any) -> list:
        """Return an arithmetic sequence: a, a+d, a+2d, ... (n terms)."""
        a, d, count = float(start), float(diff), int(n)
        return [a + i * d for i in range(count)]

    def geometric(self, start: Any, ratio: Any, n: Any) -> list:
        """Return a geometric sequence: a, a*r, a*r², ... (n terms)."""
        a, r, count = float(start), float(ratio), int(n)
        return [a * (r ** i) for i in range(count)]

    def sumAP(self, n: Any, a: Any, d: Any) -> float:
        """Sum of n terms of an arithmetic progression: n/2 * (2a + (n-1)d)."""
        n, a, d = int(n), float(a), float(d)
        return n / 2 * (2 * a + (n - 1) * d)

    def sumGP(self, n: Any, a: Any, r: Any) -> float:
        """Sum of n terms of a geometric progression: a*(r^n - 1)/(r - 1)."""
        n, a, r = int(n), float(a), float(r)
        if r == 1:
            return a * n
        return a * (r ** n - 1) / (r - 1)

    def sumInfGP(self, a: Any, r: Any) -> float:
        """Sum of an infinite geometric series (|r| < 1): a / (1 - r)."""
        a, r = float(a), float(r)
        if abs(r) >= 1:
            raise ValueError("sumInfGP requires |r| < 1")
        return a / (1 - r)

    # ── Algebra solvers ────────────────────────────────────────────────────────

    def quadratic(self, a: Any, b: Any, c: Any) -> list:
        """Solve ax² + bx + c = 0. Returns list of real roots (empty if none)."""
        a, b, c = float(a), float(b), float(c)
        if a == 0:
            if b == 0:
                return []
            return [-c / b]
        disc = b * b - 4 * a * c
        if disc < 0:
            return []
        if disc == 0:
            return [-b / (2 * a)]
        sq = math.sqrt(disc)
        return [(-b + sq) / (2 * a), (-b - sq) / (2 * a)]

    def linearSolve(self, a: Any, b: Any) -> float:
        """Solve ax + b = 0 → x = -b/a."""
        a, b = float(a), float(b)
        if a == 0:
            raise ValueError("linearSolve: coefficient a must be non-zero")
        return -b / a

    # ── Geometry helpers ───────────────────────────────────────────────────────

    def circleArea(self, r: Any) -> float:
        """Area of a circle: π * r²."""
        return math.pi * float(r) ** 2

    def circumference(self, r: Any) -> float:
        """Circumference of a circle: 2 * π * r."""
        return 2 * math.pi * float(r)

    def triangleArea(self, base: Any, height: Any) -> float:
        """Area of a triangle: 0.5 * base * height."""
        return 0.5 * float(base) * float(height)

    def heronArea(self, a: Any, b: Any, c: Any) -> float:
        """Area of a triangle via Heron's formula given three side lengths."""
        a, b, c = float(a), float(b), float(c)
        s = (a + b + c) / 2
        return math.sqrt(s * (s - a) * (s - b) * (s - c))

    def distance(self, x1: Any, y1: Any, x2: Any, y2: Any) -> float:
        """Euclidean distance between two 2-D points."""
        return math.hypot(float(x2) - float(x1), float(y2) - float(y1))

    def slope(self, x1: Any, y1: Any, x2: Any, y2: Any) -> float:
        """Slope of the line through two points: (y2-y1) / (x2-x1)."""
        dx = float(x2) - float(x1)
        if dx == 0:
            raise ValueError("slope: vertical line (x1 == x2)")
        return (float(y2) - float(y1)) / dx

    def midpoint(self, x1: Any, y1: Any, x2: Any, y2: Any) -> list:
        """Midpoint of two 2-D points: [(x1+x2)/2, (y1+y2)/2]."""
        return [(float(x1) + float(x2)) / 2, (float(y1) + float(y2)) / 2]

    # ── JS Math compatibility aliases ─────────────────────────────────────────

    def trunc(self, x: Any) -> int:
        """Truncate toward zero (JS Math.trunc equivalent)."""
        return math.trunc(float(x))

    def sign(self, x: Any) -> int:
        """Return -1, 0, or 1 (JS Math.sign equivalent)."""
        v = float(x)
        if v > 0:
            return 1
        if v < 0:
            return -1
        return 0

    def clz32(self, x: Any) -> int:
        """Count leading zeros in a 32-bit integer (JS Math.clz32 equivalent)."""
        n = int(x) & 0xFFFFFFFF
        if n == 0:
            return 32
        return 31 - int(math.log2(n))

    def fround(self, x: Any) -> float:
        """Round to nearest 32-bit float (JS Math.fround equivalent)."""
        import struct as _struct
        return _struct.unpack('f', _struct.pack('f', float(x)))[0]

    def imul(self, a: Any, b: Any) -> int:
        """32-bit integer multiplication (JS Math.imul equivalent)."""
        result = (int(a) & 0xFFFFFFFF) * (int(b) & 0xFFFFFFFF) & 0xFFFFFFFF
        # Convert to signed 32-bit
        if result >= 0x80000000:
            result -= 0x100000000
        return result


class _StatsHelper:
    """stats namespace: stats.mean, stats.stdDev, etc.

    Exposes the same statistical functions as math.* under a dedicated
    'stats' namespace for readability.
    """

    def mean(self, lst: Any) -> float:
        data = list(lst)
        if not data:
            raise ValueError("stats.mean() requires a non-empty list")
        return sum(data) / len(data)

    def median(self, lst: Any) -> float:
        data = sorted(lst)
        n = len(data)
        if n == 0:
            raise ValueError("stats.median() requires a non-empty list")
        mid = n // 2
        return float(data[mid]) if n % 2 else (data[mid - 1] + data[mid]) / 2.0

    def mode(self, lst: Any) -> Any:
        data = list(lst)
        if not data:
            raise ValueError("stats.mode() requires a non-empty list")
        freq: dict = {}
        for v in data:
            freq[v] = freq.get(v, 0) + 1
        return max(freq, key=lambda k: freq[k])

    def variance(self, lst: Any, population: bool = True) -> float:
        data = [float(x) for x in lst]
        n = len(data)
        if n < 2:
            raise ValueError("stats.variance() requires at least 2 values")
        m = sum(data) / n
        denom = n if population else n - 1
        return sum((x - m) ** 2 for x in data) / denom

    def stdDev(self, lst: Any, population: bool = True) -> float:
        return math.sqrt(self.variance(lst, population))

    def range(self, lst: Any) -> Any:  # type: ignore[override]
        data = list(lst)
        return max(data) - min(data)

    def min(self, lst: Any) -> Any:
        return min(lst)

    def max(self, lst: Any) -> Any:
        return max(lst)

    def sum(self, lst: Any) -> Any:
        return sum(lst)

    def product(self, lst: Any) -> Any:
        r = 1
        for v in lst:
            r *= v
        return r

    def percentile(self, lst: Any, p: Any) -> float:
        data = sorted(float(x) for x in lst)
        n = len(data)
        if n == 0:
            raise ValueError("stats.percentile() requires a non-empty list")
        rank = float(p) / 100 * (n - 1)
        lo, hi = int(rank), min(int(rank) + 1, n - 1)
        frac_part = rank - lo
        return data[lo] + frac_part * (data[hi] - data[lo])

    def quartiles(self, lst: Any) -> list:
        return [self.percentile(lst, 25), self.percentile(lst, 50), self.percentile(lst, 75)]

    def correlation(self, xs: Any, ys: Any) -> float:
        xs_f = [float(x) for x in xs]
        ys_f = [float(y) for y in ys]
        n = len(xs_f)
        if n != len(ys_f) or n < 2:
            raise ValueError("stats.correlation() requires two equal-length lists of length >= 2")
        mx, my = sum(xs_f) / n, sum(ys_f) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs_f, ys_f))
        denom = math.sqrt(sum((x - mx) ** 2 for x in xs_f) * sum((y - my) ** 2 for y in ys_f))
        return num / denom if denom else 0.0

    def normalize(self, lst: Any) -> list:
        data = [float(x) for x in lst]
        lo, hi = min(data), max(data)
        if hi == lo:
            return [0.0] * len(data)
        return [(x - lo) / (hi - lo) for x in data]

    def zscore(self, lst: Any) -> list:
        """Return z-scores (standard scores) for each element."""
        data = [float(x) for x in lst]
        m = sum(data) / len(data)
        sd = math.sqrt(sum((x - m) ** 2 for x in data) / len(data))
        if sd == 0:
            return [0.0] * len(data)
        return [(x - m) / sd for x in data]

    def frequency(self, lst: Any) -> dict:
        """Return a frequency dict: {value: count}."""
        freq: dict = {}
        for v in lst:
            freq[v] = freq.get(v, 0) + 1
        return freq


class _JsonHelper:
    """json namespace: json.parse, json.stringify."""

    def parse(self, text: str) -> Any:
        import json
        try:
            return json.loads(str(text))
        except Exception as e:
            raise ValueError(f"JSON parse error: {e}") from e

    def stringify(self, value: Any, replacer: Any = None, indent: Any = None) -> str:
        import json
        indent_val = int(indent) if indent is not None else None
        try:
            return json.dumps(value, indent=indent_val, default=str)
        except Exception as e:
            raise ValueError(f"JSON stringify error: {e}") from e


class _DateHelper:
    """date namespace: date.today(), date.now(), date.format(), date.parse()."""

    def today(self) -> str:
        from datetime import date
        return date.today().isoformat()

    def now(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()

    def utcnow(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def parse(self, text: str, fmt: str | None = None) -> str:
        from datetime import datetime
        try:
            if fmt:
                return datetime.strptime(str(text), fmt).isoformat()
            return datetime.fromisoformat(str(text)).isoformat()
        except Exception as e:
            raise ValueError(f"Date parse error: {e}") from e

    def format(self, dt_str: str, fmt: str) -> str:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(str(dt_str))
            return dt.strftime(fmt)
        except Exception as e:
            raise ValueError(f"Date format error: {e}") from e

    def diff(self, a: str, b: str, unit: str = "days") -> float:
        from datetime import datetime
        try:
            da = datetime.fromisoformat(str(a))
            db = datetime.fromisoformat(str(b))
            delta = db - da
            if unit == "seconds":
                return delta.total_seconds()
            if unit == "hours":
                return delta.total_seconds() / 3600
            if unit == "minutes":
                return delta.total_seconds() / 60
            return delta.days  # default: days
        except Exception as e:
            raise ValueError(f"Date diff error: {e}") from e


class _EventsHelper:
    """Simple synchronous event bus: events.on("name", handler), events.emit("name", arg)."""

    def __init__(self, call_fn: Any = None) -> None:
        self._handlers: dict[str, list] = {}
        self._call_fn = call_fn  # interpreter._call_value reference

    def __getattr__(self, prop: str) -> Any:
        if prop == "on":
            return self._on
        if prop == "off":
            return self._off
        if prop == "once":
            return self._once
        if prop == "emit":
            return self._emit
        if prop == "listeners":
            return self._listeners
        raise AttributeError(prop)

    def _invoke(self, fn: Any, args: list) -> Any:
        if self._call_fn is not None:
            return self._call_fn(fn, args)
        if callable(fn):
            return fn(*args)
        return None

    def _on(self, name: str, handler: Any) -> None:
        self._handlers.setdefault(str(name), []).append(handler)
    _on._spry_raw_args = True  # type: ignore[attr-defined]

    def _off(self, name: str, handler: Any = None) -> None:
        if handler is None:
            self._handlers.pop(str(name), None)
        else:
            handlers = self._handlers.get(str(name), [])
            if handler in handlers:
                handlers.remove(handler)
    _off._spry_raw_args = True  # type: ignore[attr-defined]

    def _once(self, name: str, handler: Any) -> None:
        """Register a one-shot handler that removes itself after first call."""
        def _wrapper(*args: Any) -> Any:
            self._off(name, _wrapper)
            return self._invoke(handler, list(args))
        self._handlers.setdefault(str(name), []).append(_wrapper)
    _once._spry_raw_args = True  # type: ignore[attr-defined]

    def _emit(self, name: str, *args: Any) -> Any:
        """Emit an event, calling all registered handlers. Returns last handler result."""
        result = None
        for handler in list(self._handlers.get(str(name), [])):
            result = self._invoke(handler, list(args))
        return result

    def _listeners(self, name: str) -> list:
        return list(self._handlers.get(str(name), []))


# ---------------------------------------------------------------------------
# Map built-in data structure
# ---------------------------------------------------------------------------


class SpryMap:
    """Ordered map data structure supporting any hashable key type.

    Accessible in SpryCode via the ``Map`` global namespace:
    ``let m = Map.new()``
    """

    def __init__(self) -> None:
        self._data: dict = {}

    # ------------------------------------------------------------------
    # Instance methods exposed as properties
    # ------------------------------------------------------------------

    def spry_set(self, k: Any, v: Any) -> "SpryMap":
        self._data[k] = v
        return self

    def spry_get(self, k: Any, default: Any = None) -> Any:
        return self._data.get(k, default)

    def spry_has(self, k: Any) -> bool:
        return k in self._data

    def spry_delete(self, k: Any) -> bool:
        if k in self._data:
            del self._data[k]
            return True
        return False

    def spry_clear(self) -> None:
        self._data.clear()

    def spry_keys(self) -> "SpryIterator":
        return SpryIterator(list(self._data.keys()))

    def spry_values(self) -> "SpryIterator":
        return SpryIterator(list(self._data.values()))

    def spry_entries(self) -> "SpryIterator":
        return SpryIterator([[k, v] for k, v in self._data.items()])

    def spry_forEach(self, fn: Any) -> None:
        for k, v in self._data.items():
            fn(v, k)

    def spry_toObject(self) -> dict:
        return dict(self._data)

    def spry_filter(self, fn: Any) -> "SpryMap":
        result = SpryMap()
        for k, v in self._data.items():
            if fn(v, k):
                result.spry_set(k, v)
        return result

    def spry_map(self, fn: Any) -> "SpryMap":
        result = SpryMap()
        for k, v in self._data.items():
            result.spry_set(k, fn(v, k))
        return result

    def spry_toEntries(self) -> list:
        return self.spry_entries()

    def spry_clone(self) -> "SpryMap":
        result = SpryMap()
        result._data = dict(self._data)
        return result

    def spry_getOrInsert(self, k: Any, default_val: Any) -> Any:
        if k not in self._data:
            self._data[k] = default_val
        return self._data[k]

    def spry_getOrInsertComputed(self, k: Any, fn: Any) -> Any:
        if k not in self._data:
            self._data[k] = fn(k) if callable(fn) else fn
        return self._data[k]

    def __repr__(self) -> str:
        return f"Map({self._data!r})"


class _MapNamespace:
    """Map global namespace — Map.new(), Map.from()."""

    def new(self, entries: Any = None) -> SpryMap:
        """Create a Map, optionally initialized from [[key,value],...] entries."""
        m = SpryMap()
        if entries is not None:
            if isinstance(entries, list):
                for pair in entries:
                    if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                        m.spry_set(pair[0], pair[1])
            elif isinstance(entries, dict):
                for k, v in entries.items():
                    m.spry_set(k, v)
            elif isinstance(entries, SpryMap):
                m._data = dict(entries._data)
        return m

    def __call__(self, entries: Any = None) -> SpryMap:
        return self.new(entries)

    def from_(self, entries: Any) -> SpryMap:
        """Create a Map from a list of [key, value] pairs."""
        m = SpryMap()
        if isinstance(entries, list):
            for pair in entries:
                if isinstance(pair, list) and len(pair) >= 2:
                    m.spry_set(pair[0], pair[1])
                elif isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    m.spry_set(pair[0], pair[1])
        elif isinstance(entries, dict):
            for k, v in entries.items():
                m.spry_set(k, v)
        return m

    def merge(self, *maps: Any) -> SpryMap:
        """Merge multiple SpryMaps into a new Map. Later maps override earlier ones."""
        result = SpryMap()
        for m in maps:
            if isinstance(m, SpryMap):
                for k, v in m._data.items():
                    result.spry_set(k, v)
            elif isinstance(m, dict):
                for k, v in m.items():
                    result.spry_set(k, v)
        return result

    def of(self, *args: Any) -> SpryMap:
        """Create a Map from flat alternating key, value args: Map.of('a', 1, 'b', 2)."""
        result = SpryMap()
        it = iter(args)
        for k in it:
            try:
                v = next(it)
            except StopIteration:
                v = None
            result.spry_set(k, v)
        return result

    def groupBy(self, lst: Any, key_fn: Any) -> SpryMap:
        """Group a list's items by the key returned by key_fn: Map.groupBy([1,2,3], x => x%2)."""
        result = SpryMap()
        if not isinstance(lst, (list, tuple)):
            raise TypeError("Map.groupBy: first argument must be a list")
        for item in lst:
            k = key_fn(item)
            if result.spry_has(k):
                result._data[k].append(item)
            else:
                result.spry_set(k, [item])
        return result

    def __getattr__(self, prop: str) -> Any:
        if prop == "from":
            return self.from_
        raise AttributeError(prop)

    def __repr__(self) -> str:
        return "Map"


# ---------------------------------------------------------------------------
# String global namespace
# ---------------------------------------------------------------------------


class _StringNamespace:
    """String global namespace — String.fromCharCode(), String.isString(), etc."""

    @staticmethod
    def _spry_str(v: Any) -> str:
        """Convert a SpryCode value to a string using SpryCode conventions."""
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float) and v == int(v):
            return str(int(v))
        return str(v)

    def fromCharCode(self, *codes: Any) -> str:
        """Create a string from character code points (integers)."""
        return "".join(chr(int(c)) for c in codes)

    def fromCodePoint(self, *codes: Any) -> str:
        """Create a string from Unicode code points."""
        return "".join(chr(int(c)) for c in codes)

    def isString(self, value: Any) -> bool:
        """Return True if the value is a string."""
        return isinstance(value, str)

    def isEmpty(self, value: Any) -> bool:
        """Return True if the value is an empty string."""
        return isinstance(value, str) and len(value) == 0

    def of(self, *chars: Any) -> str:
        """Concatenate all arguments into a single string using SpryCode conventions."""
        return "".join(self._spry_str(c) for c in chars)

    def repeat(self, s: Any, n: Any) -> str:
        """Repeat string s exactly n times."""
        return self._spry_str(s) * int(n)

    def concat(self, *parts: Any) -> str:
        """Concatenate multiple strings using SpryCode conventions."""
        return "".join(self._spry_str(p) for p in parts)

    def raw(self, strings: Any, *values: Any) -> str:
        """String.raw tagged template — return the raw template string without escape processing.

        When used as a tagged template (String.raw`foo\\nbar`), `strings` is a list of
        raw string parts and `values` are the substituted expressions.
        """
        if isinstance(strings, list):
            # Use .raw parts if available (SpryTaggedStringList), otherwise cooked
            raw_parts = getattr(strings, "raw", None) or strings
            result = raw_parts[0] if raw_parts else ""
            for i, val in enumerate(values):
                result += self._spry_str(val)
                if i + 1 < len(raw_parts):
                    result += raw_parts[i + 1]
            return result
        # Fallback: just return strings as-is
        return self._spry_str(strings)

    def __repr__(self) -> str:
        return "String"

    def __call__(self, val: Any) -> str:
        """String(x) — convert x to a string."""
        if isinstance(val, _SpryUndefinedType):
            return "undefined"
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, float):
            if math.isnan(val):
                return "NaN"
            if math.isinf(val):
                return "Infinity" if val > 0 else "-Infinity"
            if val == int(val):
                return str(int(val))
            return str(val)
        # For SpryInstance, delegate to _builtin_str so toString() is called
        if isinstance(val, SpryInstance):
            # Import here to avoid circular ref — interpreter is the one we need
            # _builtin_str is on the interpreter; fall back to str() if no interp ref
            if hasattr(self, "_interp"):
                return self._interp._builtin_str(val)
            # Fallback: call toString manually if present
            if "toString" in val.fields:
                ts = val.fields["toString"]
                if callable(ts):
                    try:
                        return str(ts())
                    except Exception:
                        pass
        return str(val)

_symbol_counter = 0


class SprySymbol:
    """Unique, immutable symbol value (like JS Symbol)."""

    def __init__(self, description: str = "") -> None:
        global _symbol_counter
        _symbol_counter += 1
        self._id = _symbol_counter
        self.description = description

    def __repr__(self) -> str:
        return f"Symbol({self.description!r})" if self.description else "Symbol()"

    def __eq__(self, other: object) -> bool:
        return self is other  # symbols are unique

    def __hash__(self) -> int:
        return id(self)


class _BooleanCallable:
    """Boolean(x) — convert x to a boolean."""

    def __call__(self, val: Any) -> bool:
        if val is None:
            return False
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val != 0 and not (isinstance(val, float) and math.isnan(val))
        if isinstance(val, str):
            return len(val) > 0
        return True

    def __repr__(self) -> str:
        return "Boolean"


class _SymbolNamespace:
    """Symbol() creates a new unique symbol. Symbol.for(key) returns a global symbol."""
    _registry: dict[str, "SprySymbol"] = {}

    def __call__(self, description: str = "") -> SprySymbol:
        return SprySymbol(str(description))

    def new(self, description: str = "") -> SprySymbol:
        return SprySymbol(str(description))

    def for_(self, key: str) -> SprySymbol:
        k = str(key)
        if k not in self._registry:
            self._registry[k] = SprySymbol(k)
        return self._registry[k]

    def keyFor(self, sym: Any) -> Any:
        for k, s in self._registry.items():
            if s is sym:
                return k
        return None

    def __getattr__(self, prop: str) -> Any:
        if prop == "for":
            return self.for_
        if prop in self._WELL_KNOWN:
            sym = SprySymbol(prop)
            setattr(_SymbolNamespace, prop, sym)
            return sym
        raise AttributeError(prop)

    _WELL_KNOWN = {
        "iterator", "asyncIterator", "toPrimitive", "toStringTag",
        "species", "hasInstance", "isConcatSpreadable", "unscopables",
        "match", "matchAll", "replace", "search", "split",
        "dispose", "asyncDispose",
    }

    def __repr__(self) -> str:
        return "Symbol"


# ---------------------------------------------------------------------------
# WeakRef global
# ---------------------------------------------------------------------------


class SpryWeakRef:
    """Simple reference wrapper (mirrors JS WeakRef semantics where practical)."""

    def __init__(self, target: Any) -> None:
        self._target = target

    def deref(self) -> Any:
        return self._target

    def __repr__(self) -> str:
        return f"WeakRef({self._target!r})"


class _WeakRefNamespace:
    """WeakRef.new(obj) / new WeakRef(obj) creates a weak reference wrapper."""

    def new(self, target: Any) -> SpryWeakRef:
        return SpryWeakRef(target)

    def __call__(self, target: Any) -> SpryWeakRef:
        """Support: new WeakRef(obj) / WeakRef(obj) call syntax."""
        return SpryWeakRef(target)

    def __repr__(self) -> str:
        return "WeakRef"


# ---------------------------------------------------------------------------
# SprySet — proper Set type with set operations
# ---------------------------------------------------------------------------


class SprySet:
    """A set of unique values supporting set-theory operations."""

    def __init__(self, items: list | None = None) -> None:
        self._data: list = []
        if items:
            for item in items:
                if item not in self._data:
                    self._data.append(item)

    @property
    def size(self) -> int:
        return len(self._data)

    def has(self, item: Any) -> bool:
        return item in self._data

    def add(self, item: Any) -> "SprySet":
        if item not in self._data:
            self._data.append(item)
        return self

    def delete(self, item: Any) -> bool:
        if item in self._data:
            self._data.remove(item)
            return True
        return False

    def clear(self) -> None:
        self._data.clear()

    def toList(self) -> list:
        return list(self._data)

    def union(self, other: "SprySet") -> "SprySet":
        result = SprySet(list(self._data))
        for item in (other._data if isinstance(other, SprySet) else other):
            if item not in result._data:
                result._data.append(item)
        return result

    def intersection(self, other: "SprySet") -> "SprySet":
        other_items = other._data if isinstance(other, SprySet) else list(other)
        return SprySet([item for item in self._data if item in other_items])

    def difference(self, other: "SprySet") -> "SprySet":
        other_items = other._data if isinstance(other, SprySet) else list(other)
        return SprySet([item for item in self._data if item not in other_items])

    def symmetricDifference(self, other: "SprySet") -> "SprySet":
        other_items = other._data if isinstance(other, SprySet) else list(other)
        result = [item for item in self._data if item not in other_items]
        result += [item for item in other_items if item not in self._data]
        return SprySet(result)

    def isSubsetOf(self, other: "SprySet") -> bool:
        other_items = other._data if isinstance(other, SprySet) else list(other)
        return all(item in other_items for item in self._data)

    def isSupersetOf(self, other: "SprySet") -> bool:
        other_items = other._data if isinstance(other, SprySet) else list(other)
        return all(item in self._data for item in other_items)

    def isDisjointFrom(self, other: "SprySet") -> bool:
        other_items = other._data if isinstance(other, SprySet) else list(other)
        return not any(item in other_items for item in self._data)

    def forEach(self, fn: Any) -> None:
        for item in self._data:
            fn(item)

    def values(self) -> "SpryIterator":
        return SpryIterator(list(self._data))

    def keys(self) -> "SpryIterator":
        return SpryIterator(list(self._data))

    def entries(self) -> "SpryIterator":
        return SpryIterator([[v, v] for v in self._data])

    def __len__(self) -> int:
        return len(self._data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SprySet):
            return self._data == other._data
        if isinstance(other, list):
            return self._data == other
        return NotImplemented

    def __iter__(self):
        return iter(self._data)

    def __repr__(self) -> str:
        return f"Set({self._data!r})"


class _SprySetNamespace:
    """Set global — supports Set(iterable) creating a SprySet, and Set.new([items])."""

    def __call__(self, lst: Any = None) -> SprySet:
        """Create a SprySet from an iterable (JS: new Set(iterable))."""
        if lst is None:
            return SprySet()
        if isinstance(lst, (list, tuple)):
            return SprySet(list(lst))
        if isinstance(lst, SprySet):
            return SprySet(list(lst._data))
        try:
            return SprySet(list(lst))
        except TypeError:
            return SprySet()

    def new(self, items: Any = None) -> SprySet:
        if items is None:
            return SprySet()
        if isinstance(items, (list, tuple)):
            return SprySet(list(items))
        return SprySet([items])

    def from_(self, iterable: Any) -> SprySet:
        try:
            return SprySet(list(iterable))
        except TypeError:
            return SprySet()

    def __getattr__(self, prop: str) -> Any:
        if prop == "from":
            return self.from_
        raise AttributeError(prop)

    def __repr__(self) -> str:
        return "SprySet"


# ---------------------------------------------------------------------------
# Iterator global — Iterator.from(iterable) + iterator helpers
# ---------------------------------------------------------------------------


class _IteratorNamespace:
    """Iterator global namespace — Iterator.from(iterable)."""

    def __init__(self, interp: Any) -> None:
        self._interp = interp

    def from_(self, iterable: Any) -> SpryIterator:
        """Convert any iterable to a SpryIterator with chainable helper methods."""
        _call_fn = self._interp._call_value
        if isinstance(iterable, SpryIterator):
            return SpryIterator(iterable._items[iterable._index:], _call_fn)
        if isinstance(iterable, SpryGenerator):
            return SpryIterator(iterable._materialise(), _call_fn)
        if isinstance(iterable, SprySet):
            return SpryIterator(list(iterable._data), _call_fn)
        if isinstance(iterable, SpryMap):
            return SpryIterator([[k, v] for k, v in iterable._data.items()], _call_fn)
        try:
            return SpryIterator(list(iterable), _call_fn)
        except TypeError:
            return SpryIterator([], _call_fn)

    def __getattr__(self, prop: str) -> Any:
        if prop == "from":
            return self.from_
        raise AttributeError(prop)

    def __repr__(self) -> str:
        return "Iterator"


# ---------------------------------------------------------------------------
# Promise — synchronous eager resolution (SpryCode has no async event loop)
# ---------------------------------------------------------------------------


class SpryPromise:
    """Synchronously-resolved promise (resolved/rejected immediately)."""

    def __init__(self, value: Any = None, error: Any = None) -> None:
        self._value = value
        self._error = error
        self._settled = error is None

    @property
    def value(self) -> Any:
        return self._value

    @property
    def error(self) -> Any:
        return self._error

    @property
    def status(self) -> str:
        return "fulfilled" if self._settled else "rejected"

    @property
    def state(self) -> str:
        return "fulfilled" if self._settled else "rejected"

    @property
    def reason(self) -> Any:
        return self._error

    def then(self, on_fulfilled: Any = None, on_rejected: Any = None) -> "SpryPromise":
        if self._settled and on_fulfilled is not None and callable(on_fulfilled):
            try:
                return SpryPromise(value=on_fulfilled(self._value))
            except Exception as e:
                return SpryPromise(error=str(e))
        if not self._settled and on_rejected is not None and callable(on_rejected):
            try:
                return SpryPromise(value=on_rejected(self._error))
            except Exception as e:
                return SpryPromise(error=str(e))
        return self

    def catch(self, on_rejected: Any) -> "SpryPromise":
        return self.then(None, on_rejected)

    def finally_(self, fn: Any) -> "SpryPromise":
        if callable(fn):
            fn()
        return self

    def __repr__(self) -> str:
        if self._settled:
            return f"Promise(fulfilled: {self._value!r})"
        return f"Promise(rejected: {self._error!r})"


class _PromiseNamespace:
    """Promise global namespace."""

    def resolve(self, value: Any = None) -> SpryPromise:
        return SpryPromise(value=value)

    def reject(self, reason: Any = None) -> SpryPromise:
        return SpryPromise(value=None, error=reason)

    def all(self, promises: Any) -> SpryPromise:
        """Resolve all promises; return list of values or first rejection."""
        results = []
        for p in (promises if isinstance(promises, (list, tuple)) else [promises]):
            if isinstance(p, SpryPromise):
                if not p._settled:
                    return SpryPromise(value=None, error=p._error)
                results.append(p._value)
            else:
                results.append(p)  # treat plain value as resolved
        return SpryPromise(value=results)

    def allSettled(self, promises: Any) -> SpryPromise:
        """Return list of {status, value/reason} for each promise."""
        results = []
        for p in (promises if isinstance(promises, (list, tuple)) else [promises]):
            if isinstance(p, SpryPromise):
                if p._settled:
                    results.append({"status": "fulfilled", "value": p._value})
                else:
                    results.append({"status": "rejected", "reason": p._error})
            else:
                results.append({"status": "fulfilled", "value": p})
        return SpryPromise(value=results)

    def race(self, promises: Any) -> SpryPromise:
        """Return first settled promise."""
        for p in (promises if isinstance(promises, (list, tuple)) else [promises]):
            if isinstance(p, SpryPromise):
                return p
            return SpryPromise(value=p)
        return SpryPromise(value=None)

    def any(self, promises: Any) -> SpryPromise:
        """Return first fulfilled promise; reject with AggregateError if all rejected."""
        errors = []
        for p in (promises if isinstance(promises, (list, tuple)) else [promises]):
            if isinstance(p, SpryPromise):
                if p._settled:
                    return p
                errors.append(p._error)
            else:
                return SpryPromise(value=p)
        return SpryPromise(value=None, error=errors)

    def withResolvers(self) -> dict:
        """ES2024: Return {promise, resolve, reject} with the promise pre-resolved.

        In SpryCode's synchronous model the promise is already settled; resolve/reject
        are no-op callables that mimic the JS API shape.
        """
        promise: SpryPromise = SpryPromise(value=None)
        container: dict = {"_p": promise}

        def _resolve(value: Any = None) -> None:
            container["_p"] = SpryPromise(value=value)

        def _reject(reason: Any = None) -> None:
            container["_p"] = SpryPromise(value=None, error=reason)

        class _LazyPromise:
            """Proxy that delegates to the container's current promise."""
            def __getattr__(self_, attr: str) -> Any:  # noqa: N805
                return getattr(container["_p"], attr)
            def __repr__(self_) -> str:  # noqa: N805
                return repr(container["_p"])

        return {"promise": _LazyPromise(), "resolve": _resolve, "reject": _reject}

    def try_(self, fn: Any) -> SpryPromise:
        """Promise.try(fn) — call fn() and wrap result in resolved/rejected promise."""
        try:
            result = fn() if callable(fn) else fn
            if isinstance(result, SpryPromise):
                return result
            return SpryPromise(value=result)
        except SpryUserError as e:
            return SpryPromise(value=None, error=e.value)
        except Exception as e:
            return SpryPromise(value=None, error=str(e))

    def __getattr__(self, name: str) -> Any:
        if name == "try":
            return self.try_
        raise AttributeError(name)

    def __getitem__(self, key: str) -> Any:
        if key == "try":
            return self.try_
        raise KeyError(key)

    def __repr__(self) -> str:
        return "Promise"


# ---------------------------------------------------------------------------
# Date namespace
# ---------------------------------------------------------------------------


class SpryDate:
    """A simple date/time object."""

    def __init__(self, year: int = 0, month: int = 1, day: int = 1,
                 hour: int = 0, minute: int = 0, second: int = 0,
                 millisecond: int = 0) -> None:
        import datetime
        self._dt = datetime.datetime(
            int(year), int(month), int(day),
            int(hour), int(minute), int(second),
            int(millisecond) * 1000
        )

    @property
    def year(self) -> int:
        return self._dt.year

    @property
    def month(self) -> int:
        return self._dt.month

    @property
    def day(self) -> int:
        return self._dt.day

    @property
    def hour(self) -> int:
        return self._dt.hour

    @property
    def minute(self) -> int:
        return self._dt.minute

    @property
    def second(self) -> int:
        return self._dt.second

    @property
    def millisecond(self) -> int:
        return self._dt.microsecond // 1000

    def getTime(self) -> float:
        """Return milliseconds since epoch."""
        import datetime
        epoch = datetime.datetime(1970, 1, 1)
        return (self._dt - epoch).total_seconds() * 1000

    def toISOString(self) -> str:
        return self._dt.isoformat() + "Z"

    def toLocaleDateString(self) -> str:
        return self._dt.strftime("%m/%d/%Y")

    def toLocaleTimeString(self) -> str:
        return self._dt.strftime("%H:%M:%S")

    def toLocaleString(self) -> str:
        return self._dt.strftime("%m/%d/%Y, %H:%M:%S")

    def getFullYear(self) -> int:
        return self._dt.year

    def getMonth(self) -> int:
        return self._dt.month - 1  # JS getMonth is 0-indexed

    def getDate(self) -> int:
        return self._dt.day

    def getDay(self) -> int:
        # JS: 0=Sunday … 6=Saturday; Python weekday(): 0=Monday … 6=Sunday
        return (self._dt.weekday() + 1) % 7

    def getHours(self) -> int:
        return self._dt.hour

    def getMinutes(self) -> int:
        return self._dt.minute

    def getSeconds(self) -> int:
        return self._dt.second

    def getMilliseconds(self) -> int:
        return self._dt.microsecond // 1000

    def getTimezoneOffset(self) -> int:
        """Return timezone offset in minutes. SpryCode has no timezone support — always 0."""
        return 0

    # ------------------------------------------------------------------
    # Setter methods — return new timestamp (ms since epoch), mutate self
    # ------------------------------------------------------------------

    def _replace_dt(self, **kwargs: Any) -> float:
        """Replace datetime fields and return new timestamp.

        Accepts ``int`` values for all standard ``datetime`` fields plus
        ``microsecond`` (passed pre-multiplied by callers).  All values are
        coerced to ``int`` here as a safety net for any callers that pass
        numeric strings or floats.
        """
        import datetime as _dt
        self._dt = self._dt.replace(**{k: int(v) for k, v in kwargs.items()})
        return self.getTime()

    def setFullYear(self, year: Any, month: Any = None, day: Any = None) -> float:
        kw: dict = {"year": int(year)}
        if month is not None:
            kw["month"] = int(month) + 1  # JS month is 0-indexed
        if day is not None:
            kw["day"] = int(day)
        return self._replace_dt(**kw)

    def setMonth(self, month: Any, day: Any = None) -> float:
        kw: dict = {"month": int(month) + 1}  # JS month is 0-indexed
        if day is not None:
            kw["day"] = int(day)
        return self._replace_dt(**kw)

    def setDate(self, day: Any) -> float:
        return self._replace_dt(day=int(day))

    def setHours(self, hours: Any, minutes: Any = None,
                 seconds: Any = None, ms: Any = None) -> float:
        kw: dict = {"hour": int(hours)}
        if minutes is not None:
            kw["minute"] = int(minutes)
        if seconds is not None:
            kw["second"] = int(seconds)
        if ms is not None:
            kw["microsecond"] = int(ms) * 1000
        return self._replace_dt(**kw)

    def setMinutes(self, minutes: Any, seconds: Any = None, ms: Any = None) -> float:
        kw: dict = {"minute": int(minutes)}
        if seconds is not None:
            kw["second"] = int(seconds)
        if ms is not None:
            kw["microsecond"] = int(ms) * 1000
        return self._replace_dt(**kw)

    def setSeconds(self, seconds: Any, ms: Any = None) -> float:
        kw: dict = {"second": int(seconds)}
        if ms is not None:
            kw["microsecond"] = int(ms) * 1000
        return self._replace_dt(**kw)

    def setMilliseconds(self, ms: Any) -> float:
        return self._replace_dt(microsecond=int(ms) * 1000)

    def setTime(self, ms: Any) -> float:
        import datetime as _dt
        epoch = _dt.datetime(1970, 1, 1)
        self._dt = epoch + _dt.timedelta(milliseconds=float(ms))
        return self.getTime()

    # ------------------------------------------------------------------
    # UTC getters — treat internal datetime as UTC (no tz conversion)
    # ------------------------------------------------------------------

    def getUTCFullYear(self) -> int:
        return self._dt.year

    def getUTCMonth(self) -> int:
        return self._dt.month - 1  # 0-indexed

    def getUTCDate(self) -> int:
        return self._dt.day

    def getUTCDay(self) -> int:
        return (self._dt.weekday() + 1) % 7

    def getUTCHours(self) -> int:
        return self._dt.hour

    def getUTCMinutes(self) -> int:
        return self._dt.minute

    def getUTCSeconds(self) -> int:
        return self._dt.second

    def getUTCMilliseconds(self) -> int:
        return self._dt.microsecond // 1000

    # ------------------------------------------------------------------
    # UTC setters — SpryCode has no timezone support; all dates are treated as
    # UTC internally, so UTC setters are identical to their local counterparts.
    # ------------------------------------------------------------------

    def setUTCFullYear(self, year: Any, month: Any = None, day: Any = None) -> float:
        return self.setFullYear(year, month, day)

    def setUTCMonth(self, month: Any, day: Any = None) -> float:
        return self.setMonth(month, day)

    def setUTCDate(self, day: Any) -> float:
        return self.setDate(day)

    def setUTCHours(self, hours: Any, minutes: Any = None,
                    seconds: Any = None, ms: Any = None) -> float:
        return self.setHours(hours, minutes, seconds, ms)

    def setUTCMinutes(self, minutes: Any, seconds: Any = None, ms: Any = None) -> float:
        return self.setMinutes(minutes, seconds, ms)

    def setUTCSeconds(self, seconds: Any, ms: Any = None) -> float:
        return self.setSeconds(seconds, ms)

    def setUTCMilliseconds(self, ms: Any) -> float:
        return self.setMilliseconds(ms)

    # ------------------------------------------------------------------
    # Additional string conversion methods
    # ------------------------------------------------------------------

    def toDateString(self) -> str:
        """Return human-readable date portion (JS: e.g. 'Mon Jan 15 2024')."""
        return self._dt.strftime("%a %b %d %Y")

    def toTimeString(self) -> str:
        """Return human-readable time portion (JS: e.g. '10:30:00 GMT+0000')."""
        return self._dt.strftime("%H:%M:%S GMT+0000")

    def toUTCString(self) -> str:
        """Return UTC string (JS: e.g. 'Mon, 15 Jan 2024 10:30:00 GMT')."""
        return self._dt.strftime("%a, %d %b %Y %H:%M:%S GMT")

    def toJSON(self) -> str:
        """Return ISO 8601 string (same as toISOString)."""
        return self.toISOString()

    def toString(self) -> str:
        """Return a human-readable string representation (like JS Date.toString())."""
        return self._dt.strftime("%a %b %d %Y %H:%M:%S GMT+0000")

    def valueOf(self) -> float:
        """Return milliseconds since epoch (same as getTime)."""
        return self.getTime()

    # ------------------------------------------------------------------
    # Comparison operators
    # ------------------------------------------------------------------

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, SpryDate):
            return self._dt < other._dt
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if isinstance(other, SpryDate):
            return self._dt <= other._dt
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, SpryDate):
            return self._dt > other._dt
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, SpryDate):
            return self._dt >= other._dt
        return NotImplemented

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SpryDate):
            return self._dt == other._dt
        return NotImplemented

    def __repr__(self) -> str:
        return self._dt.isoformat()


class _DateNamespace:
    """Date global namespace."""

    def __call__(self, *args: Any) -> "SpryDate":
        """Called as `new Date(...)` from SpryCode."""
        import datetime
        if not args:
            # new Date() → current local time
            now = datetime.datetime.now()
            return SpryDate(now.year, now.month, now.day,
                            now.hour, now.minute, now.second,
                            now.microsecond // 1000)
        if len(args) == 1:
            arg = args[0]
            if isinstance(arg, (int, float)):
                # new Date(ms) → Unix timestamp in milliseconds
                epoch = datetime.datetime(1970, 1, 1)
                dt = epoch + datetime.timedelta(milliseconds=arg)
                return SpryDate(dt.year, dt.month, dt.day,
                                dt.hour, dt.minute, dt.second,
                                dt.microsecond // 1000)
            # new Date(string) → parse ISO/common formats
            formats = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                       "%Y-%m-%d", "%m/%d/%Y"]
            for fmt in formats:
                try:
                    dt = datetime.datetime.strptime(str(arg), fmt)
                    return SpryDate(dt.year, dt.month, dt.day,
                                    dt.hour, dt.minute, dt.second,
                                    dt.microsecond // 1000)
                except ValueError:
                    continue
            return SpryDate(1970, 1, 1, 0, 0, 0, 0)  # fallback NaN-like
        # new Date(year, month, day, ...) — month is 0-indexed in JS
        year = int(args[0])
        month = int(args[1]) + 1 if len(args) > 1 else 1  # JS: 0-indexed
        day = int(args[2]) if len(args) > 2 else 1
        hour = int(args[3]) if len(args) > 3 else 0
        minute = int(args[4]) if len(args) > 4 else 0
        second = int(args[5]) if len(args) > 5 else 0
        ms = int(args[6]) if len(args) > 6 else 0
        return SpryDate(year, month, day, hour, minute, second, ms)

    def now(self) -> float:
        """Return current time as milliseconds since epoch."""
        import time
        return time.time() * 1000

    def new(self, year: Any = None, month: Any = 1, day: Any = 1,
            hour: Any = 0, minute: Any = 0, second: Any = 0,
            millisecond: Any = 0) -> SpryDate:
        """Create a new Date object."""
        if year is None:
            import datetime
            now = datetime.datetime.now()
            return SpryDate(now.year, now.month, now.day,
                           now.hour, now.minute, now.second,
                           now.microsecond // 1000)
        return SpryDate(year, month, day, hour, minute, second, millisecond)

    def parse(self, date_str: str) -> float:
        """Parse a date string and return milliseconds since epoch.

        Returns float('nan') if the string cannot be parsed — matching
        the JS Date.parse() convention of returning NaN for invalid dates.
        Callers can detect failure with: Number.isNaN(Date.parse(s)).
        """
        import datetime
        formats = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                   "%Y-%m-%d", "%m/%d/%Y"]
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(str(date_str), fmt)
                epoch = datetime.datetime(1970, 1, 1)
                return (dt - epoch).total_seconds() * 1000
            except ValueError:
                continue
        return math.nan

    def UTC(self, year: Any, month: Any = 1, day: Any = 1,
            hour: Any = 0, minute: Any = 0, second: Any = 0) -> float:
        """Return UTC time as milliseconds since epoch."""
        import datetime
        dt = datetime.datetime(int(year), int(month), int(day),
                               int(hour), int(minute), int(second))
        epoch = datetime.datetime(1970, 1, 1)
        return (dt - epoch).total_seconds() * 1000

    def __repr__(self) -> str:
        return "Date"


# ---------------------------------------------------------------------------
# Reflect namespace
# ---------------------------------------------------------------------------


class _ReflectNamespace:
    """Reflect global namespace — mirrors JS Reflect API."""

    def __init__(self, interp: Any = None) -> None:
        self._interp = interp
        self._non_extensible: set = set()  # ids of objects that had preventExtensions called

    def ownKeys(self, obj: Any) -> list:
        """Return own enumerable keys of an object."""
        if isinstance(obj, SpryProxy):
            return obj._spry_own_keys()
        if isinstance(obj, dict):
            return [k for k in obj.keys() if not k.startswith("__")]
        if isinstance(obj, SpryInstance):
            return [k for k in obj.fields.keys() if not k.startswith("__")]
        return []

    def has(self, obj: Any, key: Any) -> bool:
        """Return True if obj has the property key."""
        if isinstance(obj, dict):
            return key in obj
        if isinstance(obj, SpryInstance):
            return key in obj.fields
        return False

    def get(self, obj: Any, key: Any, default: Any = None) -> Any:
        """Get a property value from obj."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        if isinstance(obj, SpryInstance):
            return obj.fields.get(key, default)
        return default

    def set(self, obj: Any, key: Any, value: Any) -> bool:
        """Set a property on obj; returns True on success."""
        if isinstance(obj, dict):
            obj[key] = value
            return True
        if isinstance(obj, SpryInstance):
            obj.fields[key] = value
            return True
        return False

    def deleteProperty(self, obj: Any, key: Any) -> bool:
        """Delete a property from obj; returns True if it existed."""
        if isinstance(obj, dict) and key in obj:
            del obj[key]
            return True
        if isinstance(obj, SpryInstance) and key in obj.fields:
            del obj.fields[key]
            return True
        return False

    def apply(self, target: Any, this_arg: Any, args: Any) -> Any:
        """Call target with the given args list."""
        args_list = list(args) if isinstance(args, (list, tuple)) else []
        if self._interp is not None and isinstance(target, SpryFunction):
            if this_arg is not None:
                return self._interp._call_function_with_this(target, args_list, this_arg, None)
            return self._interp._call_function(target, args_list, None)
        if callable(target):
            return target(*args_list)
        return None

    def construct(self, target: Any, args: Any, new_target: Any = None) -> Any:
        """Construct a new instance using target (SpryClass or SpryFunction) with args."""
        args_list = list(args) if isinstance(args, (list, tuple)) else []
        if self._interp is not None:
            if isinstance(target, SpryClass):
                from .ast_nodes import NullLiteral as _NL
                return self._interp._construct_class(target, args_list, _NL())
            if isinstance(target, SpryFunction):
                return self._interp._construct_plain_function(target, args_list, None)
        if callable(target):
            return target(*args_list)
        return None

    def defineProperty(self, obj: Any, key: Any, descriptor: Any) -> bool:
        """Define a property (simplified — just sets value from descriptor)."""
        if isinstance(descriptor, dict) and "value" in descriptor:
            return self.set(obj, key, descriptor["value"])
        return False

    def getPrototypeOf(self, obj: Any) -> Any:
        """Return the prototype of an object."""
        if isinstance(obj, dict):
            return obj.get("__spry_proto__")
        if isinstance(obj, SpryInstance) and obj.cls is not None and obj.cls.superclass is not None:
            return None  # Prototype chain not fully modelled
        return None

    def setPrototypeOf(self, obj: Any, proto: Any) -> bool:
        """Set the prototype of an object."""
        if isinstance(obj, dict):
            if proto is None:
                obj.pop("__spry_proto__", None)
            else:
                obj["__spry_proto__"] = proto
            return True
        return False

    def isExtensible(self, obj: Any) -> bool:
        """Return True if the object has not had preventExtensions called on it."""
        return id(obj) not in self._non_extensible

    def preventExtensions(self, obj: Any) -> Any:
        """Mark the object as non-extensible."""
        self._non_extensible.add(id(obj))
        return obj

    def getOwnPropertyDescriptor(self, obj: Any, key: Any) -> Any:
        """Return a property descriptor dict or None."""
        if isinstance(obj, dict):
            getter_key = f"__getter__{key}"
            if getter_key in obj:
                getter_fn = obj[getter_key]
                setter_key = f"__setter__{key}"
                setter_fn = obj.get(setter_key)
                return {"get": getter_fn, "set": setter_fn, "enumerable": True, "configurable": True}
            if key in obj:
                return {"value": obj[key], "writable": True, "enumerable": True, "configurable": True}
            return None
        if isinstance(obj, SpryInstance):
            getter_key = f"__getter__{key}"
            if getter_key in obj.fields:
                getter_fn = obj.fields[getter_key]
                setter_key = f"__setter__{key}"
                setter_fn = obj.fields.get(setter_key)
                return {"get": getter_fn, "set": setter_fn, "enumerable": True, "configurable": True}
            if key in obj.fields:
                return {"value": obj.fields[key], "writable": True, "enumerable": True, "configurable": True}
            return None
        return None

    def __repr__(self) -> str:
        return "Reflect"


# ---------------------------------------------------------------------------
# console namespace
# ---------------------------------------------------------------------------


class _ConsoleNamespace:
    """console global — console.log, console.warn, console.error, etc."""

    def __init__(self) -> None:
        self._timers: dict = {}
        self._counts: dict = {}

    def log(self, *args: Any) -> None:
        print(*[str(a) if not isinstance(a, str) else a for a in args])

    def warn(self, *args: Any) -> None:
        import sys as _sys
        print("WARNING:", *[str(a) for a in args], file=_sys.stderr)

    def error(self, *args: Any) -> None:
        import sys as _sys
        print("ERROR:", *[str(a) for a in args], file=_sys.stderr)

    def info(self, *args: Any) -> None:
        print("INFO:", *[str(a) for a in args])

    def debug(self, *args: Any) -> None:
        print("DEBUG:", *[str(a) for a in args])

    def assert_(self, condition: Any, *args: Any) -> None:
        if not condition:
            import sys as _sys
            msg = " ".join(str(a) for a in args) if args else "Assertion failed"
            print(f"Assertion failed: {msg}", file=_sys.stderr)

    def dir(self, obj: Any) -> None:
        if isinstance(obj, dict):
            print(obj)
        else:
            print(vars(obj) if hasattr(obj, '__dict__') else repr(obj))

    def table(self, data: Any) -> None:
        if isinstance(data, list) and data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            print("\t".join(str(k) for k in keys))
            for row in data:
                print("\t".join(str(row.get(k, "")) for k in keys))
        else:
            print(repr(data))

    def time(self, label: Any = "default") -> None:
        import time as _time
        self._timers[str(label)] = _time.perf_counter()

    def timeEnd(self, label: Any = "default") -> None:
        import time as _time
        key = str(label)
        if key in self._timers:
            elapsed = (_time.perf_counter() - self._timers.pop(key)) * 1000
            print(f"{key}: {elapsed:.3f}ms")

    def timeLog(self, label: Any = "default") -> None:
        import time as _time
        key = str(label)
        if key in self._timers:
            elapsed = (_time.perf_counter() - self._timers[key]) * 1000
            print(f"{key}: {elapsed:.3f}ms")

    def count(self, label: Any = "default") -> None:
        key = str(label)
        self._counts[key] = self._counts.get(key, 0) + 1
        print(f"{key}: {self._counts[key]}")

    def countReset(self, label: Any = "default") -> None:
        self._counts.pop(str(label), None)

    def group(self, *args: Any) -> None:
        print("  ", *[str(a) for a in args])

    def groupEnd(self) -> None:
        pass

    def groupCollapsed(self, *args: Any) -> None:
        self.group(*args)

    def trace(self, *args: Any) -> None:
        import traceback as _tb
        print("Trace:", *[str(a) for a in args])
        _tb.print_stack(limit=3)

    def clear(self) -> None:
        pass  # no-op in non-terminal contexts

    def __getattr__(self, prop: str) -> Any:
        if prop == "assert":
            return self.assert_
        raise AttributeError(prop)

    def __repr__(self) -> str:
        return "console"


# ---------------------------------------------------------------------------
# crypto namespace
# ---------------------------------------------------------------------------


class _CryptoNamespace:
    """crypto global — randomUUID, randomBytes, getRandomValues."""

    def randomUUID(self) -> str:
        """Return a random UUID v4 string."""
        import uuid as _uuid
        return str(_uuid.uuid4())

    def randomBytes(self, size: Any) -> list:
        """Return a list of `size` random bytes (integers 0-255)."""
        import os as _os
        return list(_os.urandom(int(size)))

    def getRandomValues(self, arr: Any) -> list:
        """Fill a list with random values (similar to Web Crypto getRandomValues)."""
        import os as _os
        n = len(arr) if isinstance(arr, list) else int(arr)
        return list(_os.urandom(n))

    def subtle(self) -> "_SubtleCryptoNamespace":
        """Return the SubtleCrypto namespace."""
        return _SubtleCryptoNamespace()

    def __repr__(self) -> str:
        return "crypto"


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# BigInt
# ---------------------------------------------------------------------------


class _SpryBigInt:
    """Runtime representation of a BigInt value."""

    __slots__ = ("_value",)

    def __init__(self, value: int) -> None:
        self._value = int(value)

    def __repr__(self) -> str:
        return f"{self._value}n"

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, _SpryBigInt):
            return self._value == other._value
        if isinstance(other, (int, float)):
            return self._value == int(other)
        return NotImplemented

    def __lt__(self, other: Any) -> bool:
        v = other._value if isinstance(other, _SpryBigInt) else int(other)
        return self._value < v

    def __le__(self, other: Any) -> bool:
        v = other._value if isinstance(other, _SpryBigInt) else int(other)
        return self._value <= v

    def __add__(self, other: Any) -> "_SpryBigInt":
        v = other._value if isinstance(other, _SpryBigInt) else int(other)
        return _SpryBigInt(self._value + v)

    def __sub__(self, other: Any) -> "_SpryBigInt":
        v = other._value if isinstance(other, _SpryBigInt) else int(other)
        return _SpryBigInt(self._value - v)

    def __mul__(self, other: Any) -> "_SpryBigInt":
        v = other._value if isinstance(other, _SpryBigInt) else int(other)
        return _SpryBigInt(self._value * v)

    def __floordiv__(self, other: Any) -> "_SpryBigInt":
        v = other._value if isinstance(other, _SpryBigInt) else int(other)
        return _SpryBigInt(self._value // v)

    def __mod__(self, other: Any) -> "_SpryBigInt":
        v = other._value if isinstance(other, _SpryBigInt) else int(other)
        return _SpryBigInt(self._value % v)

    def __pow__(self, other: Any) -> "_SpryBigInt":
        v = other._value if isinstance(other, _SpryBigInt) else int(other)
        return _SpryBigInt(self._value ** v)

    def __neg__(self) -> "_SpryBigInt":
        return _SpryBigInt(-self._value)

    def __int__(self) -> int:
        return self._value

    def __float__(self) -> float:
        return float(self._value)

    def __hash__(self) -> int:
        return hash(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)


class _BigIntNamespace:
    """BigInt global — converts numbers and strings to BigInt."""

    def __call__(self, value: Any = 0) -> _SpryBigInt:
        if isinstance(value, _SpryBigInt):
            return value
        try:
            return _SpryBigInt(int(value))
        except (ValueError, TypeError):
            raise SpryRuntimeError(f"Cannot convert {value!r} to BigInt", None)

    def new(self, value: Any = 0) -> _SpryBigInt:
        return self(value)

    def asIntN(self, bits: int, value: Any) -> _SpryBigInt:
        v = value._value if isinstance(value, _SpryBigInt) else int(value)
        n = int(bits)
        mod = 1 << n
        result = v % mod
        if result >= (1 << (n - 1)):
            result -= mod
        return _SpryBigInt(result)

    def asUintN(self, bits: int, value: Any) -> _SpryBigInt:
        v = value._value if isinstance(value, _SpryBigInt) else int(value)
        return _SpryBigInt(v % (1 << int(bits)))

    def __repr__(self) -> str:
        return "BigInt"


# WeakMap / WeakSet
# ---------------------------------------------------------------------------


class SpryWeakMap:
    """WeakMap — object-keyed map using id()-based lookup (Python-level weak semantics)."""

    def __init__(self) -> None:
        self._data: dict = {}

    def set(self, key: Any, value: Any) -> "SpryWeakMap":
        if isinstance(key, (bool, int, float, str, type(None))) or key is SPRY_UNDEFINED:
            raise SpryRuntimeError("WeakMap key must be an object, not a primitive", None)
        self._data[id(key)] = (key, value)
        return self

    def get(self, key: Any, default: Any = None) -> Any:
        entry = self._data.get(id(key))
        return entry[1] if entry is not None else default

    def has(self, key: Any) -> bool:
        return id(key) in self._data

    def delete(self, key: Any) -> bool:
        key_id = id(key)
        if key_id in self._data:
            del self._data[key_id]
            return True
        return False

    def __repr__(self) -> str:
        return f"WeakMap({len(self._data)} entries)"


class _WeakMapNamespace:
    """WeakMap global namespace — WeakMap.new() or new WeakMap()."""

    def __call__(self, iterable: Any = None) -> SpryWeakMap:
        wm = SpryWeakMap()
        if iterable is not None:
            for entry in iterable:
                if hasattr(entry, '__iter__'):
                    pair = list(entry)
                    if len(pair) >= 2:
                        wm.set(pair[0], pair[1])
        return wm

    def new(self, iterable: Any = None) -> SpryWeakMap:
        return self.__call__(iterable)

    def __repr__(self) -> str:
        return "WeakMap"


class SpryWeakSet:
    """WeakSet — object collection using id()-based membership."""

    def __init__(self) -> None:
        self._data: dict = {}

    def add(self, key: Any) -> "SpryWeakSet":
        if isinstance(key, (bool, int, float, str)) or key is None:
            raise SpryRuntimeError("WeakSet values must be objects")
        self._data[id(key)] = key
        return self

    def has(self, key: Any) -> bool:
        return id(key) in self._data

    def delete(self, key: Any) -> bool:
        key_id = id(key)
        if key_id in self._data:
            del self._data[key_id]
            return True
        return False

    def __repr__(self) -> str:
        return f"WeakSet({len(self._data)} entries)"


class _WeakSetNamespace:
    """WeakSet global namespace — WeakSet.new() or new WeakSet()."""

    def __call__(self, iterable: Any = None) -> SpryWeakSet:
        ws = SpryWeakSet()
        if iterable is not None:
            for key in iterable:
                ws.add(key)
        return ws

    def new(self, iterable: Any = None) -> SpryWeakSet:
        return self.__call__(iterable)

    def __repr__(self) -> str:
        return "WeakSet"


# ---------------------------------------------------------------------------
# Intl namespace
# ---------------------------------------------------------------------------


class _IntlNumberFormat:
    """Intl.NumberFormat stub."""

    def __init__(self, locale: str = "en-US", options: Any = None) -> None:
        self._locale = str(locale)
        self._options = options or {}

    def format(self, value: Any) -> str:
        try:
            import locale as _locale
            # Simple formatting with thousands separator
            v = float(value)
            style = self._options.get("style", "decimal") if isinstance(self._options, dict) else "decimal"
            if style == "currency":
                currency = self._options.get("currency", "USD") if isinstance(self._options, dict) else "USD"
                return f"{currency} {v:,.2f}"
            if style == "percent":
                return f"{v * 100:.1f}%"
            # Default decimal
            minimumFractionDigits = self._options.get("minimumFractionDigits", 0) if isinstance(self._options, dict) else 0
            maximumFractionDigits = self._options.get("maximumFractionDigits", 3) if isinstance(self._options, dict) else 3
            if minimumFractionDigits > 0:
                return f"{v:,.{maximumFractionDigits}f}"
            # Return as integer if no fractional part
            if v == int(v):
                return f"{int(v):,}"
            return f"{v:,}"
        except (TypeError, ValueError):
            return str(value)

    def formatRange(self, start: Any, end: Any) -> str:
        return f"{self.format(start)}–{self.format(end)}"

    def resolvedOptions(self) -> dict:
        return {"locale": self._locale}

    def __repr__(self) -> str:
        return f"Intl.NumberFormat({self._locale!r})"


class _IntlDateTimeFormat:
    """Intl.DateTimeFormat stub."""

    def __init__(self, locale: str = "en-US", options: Any = None) -> None:
        self._locale = str(locale)
        self._options = options or {}

    def format(self, date: Any) -> str:
        if isinstance(date, SpryDate):
            return date._dt.strftime("%m/%d/%Y")
        return str(date)

    def formatRange(self, start: Any, end: Any) -> str:
        return f"{self.format(start)} – {self.format(end)}"

    def resolvedOptions(self) -> dict:
        return {"locale": self._locale}

    def __repr__(self) -> str:
        return f"Intl.DateTimeFormat({self._locale!r})"


class _IntlCollator:
    """Intl.Collator stub."""

    def __init__(self, locale: str = "en-US", options: Any = None) -> None:
        self._locale = str(locale)

    def compare(self, a: Any, b: Any) -> int:
        a_s, b_s = str(a), str(b)
        if a_s < b_s:
            return -1
        if a_s > b_s:
            return 1
        return 0

    def resolvedOptions(self) -> dict:
        return {"locale": self._locale}

    def __repr__(self) -> str:
        return f"Intl.Collator({self._locale!r})"


class _IntlPluralRules:
    """Intl.PluralRules stub."""

    def __init__(self, locale: str = "en-US", options: Any = None) -> None:
        self._locale = str(locale)
        self._options = options or {}

    def select(self, n: Any) -> str:
        # English plural rules (simplified)
        v = float(n)
        if v == 1:
            return "one"
        return "other"

    def resolvedOptions(self) -> dict:
        return {"locale": self._locale, "type": "cardinal"}

    def __repr__(self) -> str:
        return f"Intl.PluralRules({self._locale!r})"


class _IntlRelativeTimeFormat:
    """Intl.RelativeTimeFormat stub."""

    def __init__(self, locale: str = "en-US", options: Any = None) -> None:
        self._locale = str(locale)

    def format(self, value: Any, unit: str = "second") -> str:
        v = int(value)
        sign = "" if v >= 0 else ""
        return f"{v} {unit}{'s' if abs(v) != 1 else ''} ago" if v < 0 else f"in {v} {unit}{'s' if abs(v) != 1 else ''}"

    def __repr__(self) -> str:
        return f"Intl.RelativeTimeFormat({self._locale!r})"


class _IntlListFormat:
    """Intl.ListFormat stub."""

    def __init__(self, locale: str = "en-US", options: Any = None) -> None:
        self._locale = str(locale)

    def format(self, lst: Any) -> str:
        items = [str(x) for x in (lst if isinstance(lst, list) else [])]
        if len(items) == 0:
            return ""
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + " and " + items[-1]

    def __repr__(self) -> str:
        return f"Intl.ListFormat({self._locale!r})"


class _IntlSegmenter:
    """Intl.Segmenter — segments text into words/graphemes/sentences."""

    def __init__(self, locale: str = "en-US", options: Any = None) -> None:
        self._locale = locale
        self._granularity = "grapheme"
        if isinstance(options, dict):
            self._granularity = options.get("granularity", "grapheme")

    def segment(self, text: str) -> list:
        """Return list of {segment, index, isWordLike, input} dicts."""
        import re as _re
        text = str(text)
        granularity = self._granularity
        if granularity == "word":
            result = []
            for m in _re.finditer(r"\S+|\s+", text):
                seg = m.group(0)
                is_word = bool(_re.match(r"\S", seg))
                result.append({"segment": seg, "index": m.start(), "isWordLike": is_word, "input": text})
            return result
        elif granularity == "sentence":
            result = []
            for m in _re.finditer(r"[^.!?]*[.!?]*", text):
                seg = m.group(0)
                if seg:
                    result.append({"segment": seg, "index": m.start(), "isWordLike": False, "input": text})
            return result
        else:  # grapheme
            return [{"segment": ch, "index": i, "isWordLike": False, "input": text}
                    for i, ch in enumerate(text)]

    def resolvedOptions(self) -> dict:
        return {"locale": self._locale, "granularity": self._granularity}

    def __repr__(self) -> str:
        return f"Intl.Segmenter({self._locale!r})"


class _IntlSubNamespace:
    """Generic wrapper making an Intl sub-class both callable and having .new()."""
    def __init__(self, cls: type) -> None:
        self._cls = cls

    def __call__(self, locale: Any = "en-US", options: Any = None) -> Any:
        return self._cls(str(locale), options)

    def new(self, locale: Any = "en-US", options: Any = None) -> Any:
        return self._cls(str(locale), options)

    def supportedLocalesOf(self, locales: Any, options: Any = None) -> list:
        if isinstance(locales, list):
            return [str(l) for l in locales]
        return [str(locales)]

    def __repr__(self) -> str:
        return f"Intl.{self._cls.__name__}"


class _IntlNamespace:
    """Intl global namespace."""

    def __init__(self) -> None:
        self.NumberFormat = _IntlSubNamespace(_IntlNumberFormat)
        self.DateTimeFormat = _IntlSubNamespace(_IntlDateTimeFormat)
        self.Collator = _IntlSubNamespace(_IntlCollator)
        self.PluralRules = _IntlSubNamespace(_IntlPluralRules)
        self.RelativeTimeFormat = _IntlSubNamespace(_IntlRelativeTimeFormat)
        self.ListFormat = _IntlSubNamespace(_IntlListFormat)
        self.Segmenter = _IntlSubNamespace(_IntlSegmenter)

    def getCanonicalLocales(self, locales: Any) -> list:
        if isinstance(locales, list):
            return [str(l) for l in locales]
        return [str(locales)]

    def supportedValuesOf(self, key: str) -> list:
        _known: dict = {
            "currency": ["USD", "EUR", "GBP", "JPY"],
            "calendar": ["gregory", "iso8601"],
            "collation": ["default", "standard"],
            "numberingSystem": ["latn"],
            "timeZone": ["UTC"],
            "unit": ["meter", "kilogram", "second"],
        }
        return _known.get(str(key), [])

    def __repr__(self) -> str:
        return "Intl"


# ---------------------------------------------------------------------------
# FinalizationRegistry — stub (no GC hooks in CPython/SpryCode)
# ---------------------------------------------------------------------------


class SpryFinalizationRegistry:
    """FinalizationRegistry — no-op stub (GC callbacks not supported)."""

    def __init__(self, callback: Any) -> None:
        self._callback = callback

    def register(self, target: Any, held_value: Any, token: Any = None) -> None:
        pass  # no-op

    def unregister(self, token: Any) -> bool:
        return False

    def __repr__(self) -> str:
        return "FinalizationRegistry"


class _FinalizationRegistryNamespace:
    """FinalizationRegistry global namespace."""

    def new(self, callback: Any) -> SpryFinalizationRegistry:
        return SpryFinalizationRegistry(callback)

    def __call__(self, callback: Any) -> SpryFinalizationRegistry:
        """Support: new FinalizationRegistry(fn) / FinalizationRegistry(fn) call syntax."""
        return SpryFinalizationRegistry(callback)

    def __repr__(self) -> str:
        return "FinalizationRegistry"


# ---------------------------------------------------------------------------
# Proxy — basic get/set/has/deleteProperty/apply traps
# ---------------------------------------------------------------------------


class SpryProxy:
    """Basic Proxy implementation supporting get, set, has, deleteProperty traps."""

    def __init__(self, target: Any, handler: Any, interp: Any) -> None:
        object.__setattr__(self, '_target', target)
        object.__setattr__(self, '_handler', handler)
        object.__setattr__(self, '_interp', interp)

    def _invoke_trap(self, trap: Any, *args: Any) -> Any:
        """Invoke a trap (SpryMultiLambda, SpryFunction, or plain callable) via interpreter."""
        interp = object.__getattribute__(self, '_interp')
        from sprycode.interpreter import SpryMultiLambda, SpryFunction, SpryLambda
        if isinstance(trap, (SpryMultiLambda,)):
            return interp._apply_multi_lambda(trap, list(args), interp.globals)
        if isinstance(trap, SpryLambda):
            return interp._apply_lambda(trap, args[0] if args else None, interp.globals)
        if isinstance(trap, SpryFunction):
            # Build a fake node for error reporting
            class _FakeNode:
                line = 0
                column = 0
            return interp._call_function(trap, list(args), _FakeNode())
        if callable(trap):
            return trap(*args)
        return None

    def _spry_get_prop(self, prop: str) -> Any:
        target = object.__getattribute__(self, '_target')
        handler = object.__getattribute__(self, '_handler')
        # Check for get trap
        if isinstance(handler, dict) and 'get' in handler:
            trap = handler['get']
            return self._invoke_trap(trap, target, prop)
        # Fall through to target
        if isinstance(target, dict):
            return target.get(prop)
        if isinstance(target, SpryInstance):
            return target.fields.get(prop)
        return None

    def _spry_set_prop(self, prop: str, value: Any) -> None:
        target = object.__getattribute__(self, '_target')
        handler = object.__getattribute__(self, '_handler')
        if isinstance(handler, dict) and 'set' in handler:
            trap = handler['set']
            self._invoke_trap(trap, target, prop, value)
            return
        if isinstance(target, dict):
            target[prop] = value
        elif isinstance(target, SpryInstance):
            target.fields[prop] = value

    def _spry_has_prop(self, prop: str) -> bool:
        target = object.__getattribute__(self, '_target')
        handler = object.__getattribute__(self, '_handler')
        if isinstance(handler, dict) and 'has' in handler:
            trap = handler['has']
            return bool(self._invoke_trap(trap, target, prop))
        if isinstance(target, dict):
            return prop in target
        if isinstance(target, SpryInstance):
            return prop in target.fields
        return False

    def _spry_own_keys(self) -> list:
        """ownKeys trap support."""
        target = object.__getattribute__(self, '_target')
        handler = object.__getattribute__(self, '_handler')
        if isinstance(handler, dict) and 'ownKeys' in handler:
            trap = handler['ownKeys']
            result = self._invoke_trap(trap, target)
            return result if isinstance(result, list) else list(result or [])
        if isinstance(target, dict):
            return [k for k in target.keys() if not k.startswith("__")]
        if isinstance(target, SpryInstance):
            return [k for k in target.fields.keys() if not k.startswith("__")]
        return []

    def _spry_delete_prop(self, prop: str) -> bool:
        """deleteProperty trap support."""
        target = object.__getattribute__(self, '_target')
        handler = object.__getattribute__(self, '_handler')
        if isinstance(handler, dict) and 'deleteProperty' in handler:
            trap = handler['deleteProperty']
            return bool(self._invoke_trap(trap, target, prop))
        if isinstance(target, dict):
            return target.pop(prop, SPRY_UNDEFINED) is not SPRY_UNDEFINED
        if isinstance(target, SpryInstance):
            return target.fields.pop(prop, SPRY_UNDEFINED) is not SPRY_UNDEFINED
        return False

    def _spry_apply(self, this_val: Any, args: list) -> Any:
        """apply trap support — for function proxies."""
        target = object.__getattribute__(self, '_target')
        handler = object.__getattribute__(self, '_handler')
        if isinstance(handler, dict) and 'apply' in handler:
            trap = handler['apply']
            return self._invoke_trap(trap, target, this_val, args)
        # Fallback: call target directly
        return self._invoke_trap(target, *args)

    def __repr__(self) -> str:
        target = object.__getattribute__(self, '_target')
        return f"Proxy({target!r})"

    def __getitem__(self, key: Any) -> Any:
        return self._spry_get_prop(str(key) if not isinstance(key, str) else key)

    def __setitem__(self, key: Any, value: Any) -> None:
        self._spry_set_prop(str(key) if not isinstance(key, str) else key, value)


class _ProxyNamespace:
    """Proxy global namespace — Proxy.new(target, handler)."""

    def __init__(self, interp: Any) -> None:
        self._interp = interp

    def __call__(self, target: Any, handler: Any = None) -> SpryProxy:
        return SpryProxy(target, handler or {}, self._interp)

    def new(self, target: Any, handler: Any = None) -> SpryProxy:
        return SpryProxy(target, handler or {}, self._interp)

    def revocable(self, target: Any, handler: Any = None) -> dict:
        proxy = SpryProxy(target, handler or {}, self._interp)
        return {"proxy": proxy, "revoke": lambda: None}

    def __repr__(self) -> str:
        return "Proxy"


# ---------------------------------------------------------------------------
# performance namespace
# ---------------------------------------------------------------------------

class _PerformanceNamespace:
    """performance namespace with basic mark/measure entry timeline support."""

    def __init__(self) -> None:
        import time as _t
        self._entries: list[dict[str, Any]] = []
        self._marks: dict[str, float] = {}
        perf_now = _t.perf_counter()
        unix_ms = _t.time() * 1000.0
        self._time_origin = unix_ms - (perf_now * 1000.0)
        self._resource_timing_buffer_size = 250

    def now(self) -> float:
        import time as _t
        return _t.perf_counter() * 1000.0

    @property
    def timeOrigin(self) -> float:
        return self._time_origin

    def mark(self, name: Any = None) -> dict[str, Any]:
        mark_name = str(name) if name is not None else "default"
        start_time = self.now()
        self._marks[mark_name] = start_time
        entry = {
            "name": mark_name,
            "entryType": "mark",
            "startTime": start_time,
            "duration": 0.0,
        }
        self._entries.append(entry)
        return entry

    def measure(self, name: Any = None, start: Any = None, end: Any = None) -> dict[str, Any]:
        measure_name = str(name) if name is not None else "measure"
        now = self.now()
        start_time = self._resolve_time(start, 0.0)
        end_time = self._resolve_time(end, now)
        duration = max(0.0, end_time - start_time)
        entry = {
            "name": measure_name,
            "entryType": "measure",
            "startTime": start_time,
            "duration": duration,
        }
        self._entries.append(entry)
        return entry

    def getEntries(self) -> list:
        return list(self._entries)

    def getEntriesByType(self, entry_type: Any = None) -> list:
        if entry_type is None:
            return list(self._entries)
        et = str(entry_type)
        return [e for e in self._entries if e.get("entryType") == et]

    def getEntriesByName(self, name: Any = None, entry_type: Any = None) -> list:
        if name is None:
            return self.getEntriesByType(entry_type)
        n = str(name)
        entries = [e for e in self._entries if e.get("name") == n]
        if entry_type is None:
            return entries
        et = str(entry_type)
        return [e for e in entries if e.get("entryType") == et]

    def clearMarks(self, name: Any = None) -> None:
        if name is None:
            self._marks.clear()
            self._remove_entries("mark")
            return
        n = str(name)
        self._marks.pop(n, None)
        self._remove_entries("mark", n)

    def clearMeasures(self, name: Any = None) -> None:
        if name is None:
            self._remove_entries("measure")
            return
        n = str(name)
        self._remove_entries("measure", n)

    def clearResourceTimings(self) -> None:
        self._remove_entries("resource")

    def setResourceTimingBufferSize(self, max_size: Any) -> None:
        import math as _math
        try:
            v = float(max_size)
            if _math.isnan(v) or _math.isinf(v):
                self._resource_timing_buffer_size = 0
            else:
                self._resource_timing_buffer_size = max(0, int(v))
        except (TypeError, ValueError):
            self._resource_timing_buffer_size = 0

    def _resolve_time(self, value: Any, default: float) -> float:
        """Resolve a measure boundary from number, mark name, or fallback default."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        key = str(value)
        if key in self._marks:
            return self._marks[key]
        return default

    def _remove_entries(self, entry_type: str, name: str | None = None) -> None:
        """Remove timeline entries by type, optionally filtering to a specific name."""
        if name is None:
            self._entries = [e for e in self._entries if e.get("entryType") != entry_type]
            return
        self._entries = [
            e for e in self._entries
            if not (e.get("entryType") == entry_type and e.get("name") == name)
        ]

    def __repr__(self) -> str:
        return "performance"


# ---------------------------------------------------------------------------
# URL global
# ---------------------------------------------------------------------------

class SpryURL:
    """Basic URL object supporting common properties."""

    def __init__(self, href: str) -> None:
        from urllib.parse import urlparse
        self._raw = href
        self._parsed = urlparse(href)
        self._search_params = SpryURLSearchParams(self._parsed.query)

    @property
    def href(self) -> str:
        return self._raw

    @property
    def protocol(self) -> str:
        return (self._parsed.scheme + ":") if self._parsed.scheme else ""

    @property
    def hostname(self) -> str:
        return self._parsed.hostname or ""

    @property
    def port(self) -> str:
        return str(self._parsed.port) if self._parsed.port else ""

    @property
    def pathname(self) -> str:
        return self._parsed.path or "/"

    @property
    def search(self) -> str:
        return ("?" + self._parsed.query) if self._parsed.query else ""

    @property
    def hash(self) -> str:
        return ("#" + self._parsed.fragment) if self._parsed.fragment else ""

    @property
    def origin(self) -> str:
        scheme = self._parsed.scheme
        host = self._parsed.hostname or ""
        port = self._parsed.port
        if port:
            return f"{scheme}://{host}:{port}"
        return f"{scheme}://{host}" if scheme else ""

    @property
    def username(self) -> str:
        return self._parsed.username or ""

    @property
    def password(self) -> str:
        return self._parsed.password or ""

    def toString(self) -> str:
        return self._raw

    def _spry_get_prop(self, prop: str) -> Any:
        mapping = {
            "href": self.href, "protocol": self.protocol,
            "hostname": self.hostname, "port": self.port,
            "pathname": self.pathname, "search": self.search,
            "hash": self.hash, "origin": self.origin,
            "username": self.username, "password": self.password,
            "searchParams": self._search_params,
        }
        if prop in mapping:
            return mapping[prop]
        if prop == "toString":
            return self.toString
        raise SpryRuntimeError(f"URL has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"URL({self._raw!r})"


class _URLNamespace:
    """URL global namespace — URL.new(href) / new URL(href)."""

    def new(self, href: Any) -> SpryURL:
        return SpryURL(str(href))

    def __call__(self, href: Any) -> SpryURL:
        """Support: new URL(href) / URL(href) call syntax."""
        return SpryURL(str(href))

    def canParse(self, href: Any) -> bool:
        try:
            from urllib.parse import urlparse
            result = urlparse(str(href))
            return bool(result.scheme)
        except Exception:
            return False

    def __repr__(self) -> str:
        return "URL"


# ---------------------------------------------------------------------------
# URLSearchParams
# ---------------------------------------------------------------------------

class SpryURLSearchParams:
    """URLSearchParams — parse and manipulate URL query strings."""

    def __init__(self, init: Any = "") -> None:
        self._params: list = []  # list of [key, value] pairs (multi-valued)
        if isinstance(init, str):
            self._parse_string(init.lstrip("?"))
        elif isinstance(init, dict):
            for k, v in init.items():
                self._params.append([str(k), str(v)])
        elif isinstance(init, list):
            for item in init:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    self._params.append([str(item[0]), str(item[1])])

    def _parse_string(self, s: str) -> None:
        if not s:
            return
        from urllib.parse import parse_qsl
        for k, v in parse_qsl(s, keep_blank_values=True):
            self._params.append([k, v])

    def get(self, name: str) -> Any:
        """Return the first value for the given key, or None."""
        for k, v in self._params:
            if k == str(name):
                return v
        return None

    def getAll(self, name: str) -> list:
        """Return all values for the given key."""
        return [v for k, v in self._params if k == str(name)]

    def has(self, name: str) -> bool:
        return any(k == str(name) for k, v in self._params)

    def set(self, name: str, value: Any) -> None:
        """Set a key to a value, replacing all existing entries for that key."""
        name = str(name)
        value = str(value)
        found = False
        new_params = []
        for k, v in self._params:
            if k == name:
                if not found:
                    new_params.append([k, value])
                    found = True
            else:
                new_params.append([k, v])
        if not found:
            new_params.append([name, value])
        self._params = new_params

    def append(self, name: str, value: Any) -> None:
        """Append a new key-value pair."""
        self._params.append([str(name), str(value)])

    def delete(self, name: str) -> None:
        """Remove all entries for the given key."""
        name = str(name)
        self._params = [[k, v] for k, v in self._params if k != name]

    def keys(self) -> "SpryIterator":
        return SpryIterator([k for k, v in self._params])

    def values(self) -> "SpryIterator":
        return SpryIterator([v for k, v in self._params])

    def entries(self) -> "SpryIterator":
        return SpryIterator([[k, v] for k, v in self._params])

    def forEach(self, fn: Any) -> None:
        for k, v in self._params:
            fn(v, k)

    @property
    def size(self) -> int:
        return len(self._params)

    def toString(self) -> str:
        from urllib.parse import urlencode
        return urlencode([(k, v) for k, v in self._params])

    def sort(self) -> None:
        self._params.sort(key=lambda p: p[0])

    def _spry_get_prop(self, prop: str) -> Any:
        mapping = {
            "size": self.size,
            "get": self.get,
            "getAll": self.getAll,
            "has": self.has,
            "set": self.set,
            "append": self.append,
            "delete": self.delete,
            "keys": self.keys,
            "values": self.values,
            "entries": self.entries,
            "forEach": self.forEach,
            "toString": self.toString,
            "sort": self.sort,
        }
        if prop in mapping:
            return mapping[prop]
        raise SpryRuntimeError(f"URLSearchParams has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"URLSearchParams({self.toString()!r})"


class _URLSearchParamsNamespace:
    """URLSearchParams global namespace."""

    def new(self, init: Any = "") -> SpryURLSearchParams:
        return SpryURLSearchParams(init)

    def __call__(self, init: Any = "") -> SpryURLSearchParams:
        return SpryURLSearchParams(init)

    def __repr__(self) -> str:
        return "URLSearchParams"


# ---------------------------------------------------------------------------
# TextEncoder / TextDecoder
# ---------------------------------------------------------------------------

class SpryTextEncoder:
    """TextEncoder — encodes strings to UTF-8 byte arrays."""

    @property
    def encoding(self) -> str:
        return "utf-8"

    def encode(self, text: Any = "") -> list:
        """Encode a string to a list of UTF-8 bytes."""
        return list(str(text).encode("utf-8"))

    def encodeInto(self, text: Any, dest: Any) -> dict:
        """Encode into dest (list); returns {read, written} stats."""
        encoded = str(text).encode("utf-8")
        n = min(len(encoded), len(dest) if isinstance(dest, list) else 0)
        if isinstance(dest, list):
            for i in range(n):
                dest[i] = encoded[i]
        return {"read": len(str(text)), "written": n}

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "encoding":
            return self.encoding
        if prop == "encode":
            return self.encode
        if prop == "encodeInto":
            return self.encodeInto
        raise SpryRuntimeError(f"TextEncoder has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "TextEncoder"


class _TextEncoderNamespace:
    def new(self, encoding: Any = "utf-8") -> SpryTextEncoder:
        return SpryTextEncoder()

    def __call__(self, encoding: Any = "utf-8") -> SpryTextEncoder:
        return SpryTextEncoder()

    def __repr__(self) -> str:
        return "TextEncoder"


class SpryTextDecoder:
    """TextDecoder — decodes byte arrays to strings."""

    def __init__(self, encoding: str = "utf-8") -> None:
        raw = str(encoding).lower().strip()
        # Normalize to WHATWG canonical names: utf8 → utf-8, etc.
        _aliases: dict[str, str] = {
            "utf8": "utf-8", "utf-8": "utf-8",
            "latin1": "iso-8859-1", "iso-8859-1": "iso-8859-1",
            "ascii": "us-ascii", "us-ascii": "us-ascii",
        }
        self._encoding = _aliases.get(raw.replace("_", "").replace("-", ""), raw)
        # Encoding name used for Python's decode() call
        self._py_encoding = raw.replace("-", "")

    @property
    def encoding(self) -> str:
        return self._encoding

    def decode(self, data: Any = None) -> str:
        """Decode a list/bytes of UTF-8 bytes to a string."""
        if data is None:
            return ""
        if isinstance(data, (bytes, bytearray)):
            raw = bytes(data)
        elif isinstance(data, list):
            raw = bytes(int(b) & 0xFF for b in data)
        else:
            return str(data)
        try:
            return raw.decode(self._py_encoding or "utf-8")
        except (UnicodeDecodeError, LookupError):
            return raw.decode("utf-8", errors="replace")

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "encoding":
            return self.encoding
        if prop == "decode":
            return self.decode
        raise SpryRuntimeError(f"TextDecoder has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"TextDecoder({self._encoding!r})"


class _TextDecoderNamespace:
    def new(self, encoding: Any = "utf-8") -> SpryTextDecoder:
        return SpryTextDecoder(str(encoding))

    def __call__(self, encoding: Any = "utf-8") -> SpryTextDecoder:
        return SpryTextDecoder(str(encoding))

    def __repr__(self) -> str:
        return "TextDecoder"


# ---------------------------------------------------------------------------
# AbortController / AbortSignal
# ---------------------------------------------------------------------------

class SpryAbortSignal:
    """AbortSignal — reflects the abort state of an AbortController."""

    def __init__(self) -> None:
        self._aborted = False
        self._reason: Any = None
        self._listeners: list = []

    @property
    def aborted(self) -> bool:
        return self._aborted

    @property
    def reason(self) -> Any:
        return self._reason

    def addEventListener(self, event_type: str, listener: Any) -> None:
        if str(event_type) == "abort":
            self._listeners.append(listener)

    def removeEventListener(self, event_type: str, listener: Any) -> None:
        if str(event_type) == "abort" and listener in self._listeners:
            self._listeners.remove(listener)

    def _abort(self, reason: Any = None) -> None:
        if not self._aborted:
            self._aborted = True
            self._reason = reason
            for cb in list(self._listeners):
                try:
                    if callable(cb):
                        cb()
                except Exception:
                    pass

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "aborted":
            return self.aborted
        if prop == "reason":
            return self.reason
        if prop == "addEventListener":
            return self.addEventListener
        if prop == "removeEventListener":
            return self.removeEventListener
        raise SpryRuntimeError(f"AbortSignal has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"AbortSignal(aborted={self._aborted})"


class SpryAbortController:
    """AbortController — allows aborting async operations via a signal."""

    def __init__(self) -> None:
        self._signal = SpryAbortSignal()

    @property
    def signal(self) -> SpryAbortSignal:
        return self._signal

    def abort(self, reason: Any = "AbortError") -> None:
        self._signal._abort(reason)

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "signal":
            return self.signal
        if prop == "abort":
            return self.abort
        raise SpryRuntimeError(f"AbortController has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "AbortController"


class _AbortControllerNamespace:
    """AbortController global namespace."""

    def new(self) -> SpryAbortController:
        return SpryAbortController()

    def __call__(self) -> SpryAbortController:
        return SpryAbortController()

    def __repr__(self) -> str:
        return "AbortController"


class _AbortSignalNamespace:
    """AbortSignal static methods namespace."""

    def abort(self, reason: Any = "AbortError") -> SpryAbortSignal:
        sig = SpryAbortSignal()
        sig._abort(reason)
        return sig

    def timeout(self, ms: Any) -> SpryAbortSignal:
        """Return a non-aborted signal (synchronous stub — no actual timeout)."""
        return SpryAbortSignal()

    def any(self, signals: Any) -> SpryAbortSignal:
        """Return aborted if any of the signals is aborted."""
        if isinstance(signals, list):
            for sig in signals:
                if isinstance(sig, SpryAbortSignal) and sig.aborted:
                    new_sig = SpryAbortSignal()
                    new_sig._abort(sig.reason)
                    return new_sig
        return SpryAbortSignal()

    def __repr__(self) -> str:
        return "AbortSignal"


# ---------------------------------------------------------------------------
# ArrayBuffer and TypedArrays
# ---------------------------------------------------------------------------

class SpryArrayBuffer:
    """Fixed-size binary data buffer."""

    def __init__(self, byte_length: int) -> None:
        self._data = bytearray(int(byte_length))

    @property
    def byteLength(self) -> int:
        return len(self._data)

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "byteLength":
            return self.byteLength
        raise SpryRuntimeError(f"ArrayBuffer has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"ArrayBuffer({self.byteLength})"


class _ArrayBufferNamespace:
    def new(self, byte_length: Any) -> SpryArrayBuffer:
        return SpryArrayBuffer(int(byte_length))

    def __call__(self, byte_length: Any = 0) -> SpryArrayBuffer:
        return SpryArrayBuffer(int(byte_length))

    def isView(self, obj: Any) -> bool:
        return isinstance(obj, (SpryTypedArray, SpryDataView))

    def __repr__(self) -> str:
        return "ArrayBuffer"


# ---------------------------------------------------------------------------
# SharedArrayBuffer
# ---------------------------------------------------------------------------

class SprySharedArrayBuffer:
    """SharedArrayBuffer — like ArrayBuffer but intended for shared use across agents.
    In SpryCode's single-threaded interpreter, this is functionally equivalent to
    ArrayBuffer."""

    def __init__(self, byte_length: int) -> None:
        self._data = bytearray(int(byte_length))

    @property
    def byteLength(self) -> int:
        return len(self._data)

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "byteLength":
            return self.byteLength
        raise SpryRuntimeError(f"SharedArrayBuffer has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"SharedArrayBuffer({self.byteLength})"


class _SharedArrayBufferNamespace:
    def new(self, byte_length: Any) -> SprySharedArrayBuffer:
        return SprySharedArrayBuffer(int(byte_length))

    def __call__(self, byte_length: Any = 0) -> SprySharedArrayBuffer:
        return SprySharedArrayBuffer(int(byte_length))

    def __repr__(self) -> str:
        return "SharedArrayBuffer"


# ---------------------------------------------------------------------------
# DataView
# ---------------------------------------------------------------------------

import struct as _struct_mod


class SpryDataView:
    """DataView — read/write typed data at byte offsets in an ArrayBuffer."""

    def __init__(self, buffer: Any, byte_offset: Any = 0, byte_length: Any = None) -> None:
        if not isinstance(buffer, (SpryArrayBuffer, SprySharedArrayBuffer)):
            raise SpryRuntimeError("DataView requires an ArrayBuffer or SharedArrayBuffer", None)
        self._buffer = buffer
        self._byte_offset = int(byte_offset)
        buf_len = len(buffer._data)
        if byte_length is None:
            self._byte_length = buf_len - self._byte_offset
        else:
            self._byte_length = int(byte_length)

    @property
    def buffer(self) -> Any:
        return self._buffer

    @property
    def byteOffset(self) -> int:
        return self._byte_offset

    @property
    def byteLength(self) -> int:
        return self._byte_length

    def _read(self, fmt: str, byte_offset: Any, little_endian: Any = False) -> Any:
        off = self._byte_offset + int(byte_offset)
        size = _struct_mod.calcsize(fmt)
        raw = bytes(self._buffer._data[off:off + size])
        order = "<" if little_endian else ">"
        return _struct_mod.unpack(order + fmt, raw)[0]

    def _write(self, fmt: str, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        off = self._byte_offset + int(byte_offset)
        size = _struct_mod.calcsize(fmt)
        order = "<" if little_endian else ">"
        raw = _struct_mod.pack(order + fmt, value)
        self._buffer._data[off:off + size] = raw

    def getInt8(self, byte_offset: Any) -> int:
        return self._read("b", byte_offset)

    def getUint8(self, byte_offset: Any) -> int:
        return self._read("B", byte_offset)

    def getInt16(self, byte_offset: Any, little_endian: Any = False) -> int:
        return self._read("h", byte_offset, little_endian)

    def getUint16(self, byte_offset: Any, little_endian: Any = False) -> int:
        return self._read("H", byte_offset, little_endian)

    def getInt32(self, byte_offset: Any, little_endian: Any = False) -> int:
        return self._read("i", byte_offset, little_endian)

    def getUint32(self, byte_offset: Any, little_endian: Any = False) -> int:
        return self._read("I", byte_offset, little_endian)

    def getFloat32(self, byte_offset: Any, little_endian: Any = False) -> float:
        return float(self._read("f", byte_offset, little_endian))

    def getFloat64(self, byte_offset: Any, little_endian: Any = False) -> float:
        return float(self._read("d", byte_offset, little_endian))

    def getBigInt64(self, byte_offset: Any, little_endian: Any = False) -> int:
        return self._read("q", byte_offset, little_endian)

    def getBigUint64(self, byte_offset: Any, little_endian: Any = False) -> int:
        return self._read("Q", byte_offset, little_endian)

    def setInt8(self, byte_offset: Any, value: Any) -> None:
        self._write("b", byte_offset, int(value))

    def setUint8(self, byte_offset: Any, value: Any) -> None:
        self._write("B", byte_offset, int(value) & 0xFF)

    def setInt16(self, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        self._write("h", byte_offset, int(value), little_endian)

    def setUint16(self, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        self._write("H", byte_offset, int(value) & 0xFFFF, little_endian)

    def setInt32(self, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        self._write("i", byte_offset, int(value), little_endian)

    def setUint32(self, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        self._write("I", byte_offset, int(value) & 0xFFFFFFFF, little_endian)

    def setFloat32(self, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        self._write("f", byte_offset, float(value), little_endian)

    def setFloat64(self, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        self._write("d", byte_offset, float(value), little_endian)

    def setBigInt64(self, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        self._write("q", byte_offset, int(value), little_endian)

    def setBigUint64(self, byte_offset: Any, value: Any, little_endian: Any = False) -> None:
        self._write("Q", byte_offset, int(value), little_endian)

    def _spry_get_prop(self, prop: str) -> Any:
        _methods = {
            "buffer": self.buffer, "byteOffset": self.byteOffset, "byteLength": self.byteLength,
            "getInt8": self.getInt8, "getUint8": self.getUint8,
            "getInt16": self.getInt16, "getUint16": self.getUint16,
            "getInt32": self.getInt32, "getUint32": self.getUint32,
            "getFloat32": self.getFloat32, "getFloat64": self.getFloat64,
            "getBigInt64": self.getBigInt64, "getBigUint64": self.getBigUint64,
            "setInt8": self.setInt8, "setUint8": self.setUint8,
            "setInt16": self.setInt16, "setUint16": self.setUint16,
            "setInt32": self.setInt32, "setUint32": self.setUint32,
            "setFloat32": self.setFloat32, "setFloat64": self.setFloat64,
            "setBigInt64": self.setBigInt64, "setBigUint64": self.setBigUint64,
        }
        if prop in _methods:
            return _methods[prop]
        raise SpryRuntimeError(f"DataView has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"DataView(byteLength={self._byte_length})"


class _DataViewNamespace:
    """DataView global namespace."""

    def new(self, buffer: Any, byte_offset: Any = 0, byte_length: Any = None) -> SpryDataView:
        return SpryDataView(buffer, byte_offset, byte_length)

    def __call__(self, buffer: Any, byte_offset: Any = 0, byte_length: Any = None) -> SpryDataView:
        return SpryDataView(buffer, byte_offset, byte_length)

    def __repr__(self) -> str:
        return "DataView"


# ---------------------------------------------------------------------------
# Atomics
# ---------------------------------------------------------------------------

class _AtomicsNamespace:
    """Atomics — atomic operations on integer TypedArrays.
    In SpryCode's single-threaded interpreter, these are synchronous."""

    def load(self, arr: Any, index: Any) -> Any:
        return arr.get(index)

    def store(self, arr: Any, index: Any, value: Any) -> Any:
        arr.set(index, value)
        return value

    def add(self, arr: Any, index: Any, value: Any) -> Any:
        old = arr.get(index)
        arr.set(index, int(old) + int(value))
        return old

    def sub(self, arr: Any, index: Any, value: Any) -> Any:
        old = arr.get(index)
        arr.set(index, int(old) - int(value))
        return old

    def and_(self, arr: Any, index: Any, value: Any) -> Any:
        old = arr.get(index)
        arr.set(index, int(old) & int(value))
        return old

    def or_(self, arr: Any, index: Any, value: Any) -> Any:
        old = arr.get(index)
        arr.set(index, int(old) | int(value))
        return old

    def xor(self, arr: Any, index: Any, value: Any) -> Any:
        old = arr.get(index)
        arr.set(index, int(old) ^ int(value))
        return old

    def exchange(self, arr: Any, index: Any, value: Any) -> Any:
        old = arr.get(index)
        arr.set(index, value)
        return old

    def compareExchange(self, arr: Any, index: Any, expected_value: Any, replacement_value: Any) -> Any:
        current = arr.get(index)
        if current == expected_value:
            arr.set(index, replacement_value)
        return current

    def isLockFree(self, size: Any) -> bool:
        return int(size) in (1, 2, 4, 8)

    def wait(self, arr: Any, index: Any, value: Any, timeout: Any = None) -> str:
        """Stub — returns 'not-equal' if value doesn't match, 'ok' otherwise."""
        current = arr.get(index)
        if current != value:
            return "not-equal"
        return "ok"

    def notify(self, arr: Any, index: Any, count: Any = None) -> int:
        """Stub — returns 0 (no waiting agents in single-threaded environment)."""
        return 0

    def _spry_get_prop(self, prop: str) -> Any:
        _map = {
            "load": self.load, "store": self.store,
            "add": self.add, "sub": self.sub,
            "and": self.and_, "or": self.or_, "xor": self.xor,
            "exchange": self.exchange, "compareExchange": self.compareExchange,
            "isLockFree": self.isLockFree, "wait": self.wait, "notify": self.notify,
        }
        if prop in _map:
            return _map[prop]
        try:
            return getattr(self, prop)
        except AttributeError:
            raise SpryRuntimeError(f"Atomics has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "Atomics"


class SpryTypedArray:
    """Fixed-size typed array."""

    def __init__(self, type_name: str, element_size: int, length_or_buffer: Any,
                 byte_offset: int = 0, _buffer: Any = None) -> None:
        self._type_name = type_name
        self._element_size = element_size
        self._byte_offset = byte_offset
        self._backing_buffer: Any = _buffer  # SpryArrayBuffer or None
        if isinstance(length_or_buffer, (SpryArrayBuffer, SprySharedArrayBuffer)):
            length = len(length_or_buffer._data) // element_size
            self._backing_buffer = length_or_buffer
        elif isinstance(length_or_buffer, list):
            length = len(length_or_buffer)
        else:
            length = int(length_or_buffer)
        self._data: list = [0] * length
        if isinstance(length_or_buffer, list):
            for i, v in enumerate(length_or_buffer):
                if i < length:
                    self._data[i] = self._coerce(v)

    def _coerce(self, v: Any) -> Any:
        """Coerce a value for storage (clamped arrays override this)."""
        return v

    @property
    def length(self) -> int:
        return len(self._data)

    @property
    def byteLength(self) -> int:
        return len(self._data) * self._element_size

    @property
    def byteOffset(self) -> int:
        return self._byte_offset

    @property
    def buffer(self) -> Any:
        if self._backing_buffer is not None:
            return self._backing_buffer
        # Create a synthetic buffer on demand
        buf = SpryArrayBuffer(self.byteLength)
        return buf

    def get(self, index: Any) -> Any:
        return self._data[int(index)]

    def set(self, index_or_array: Any, value_or_offset: Any = 0) -> None:
        if isinstance(index_or_array, (list, SpryTypedArray)):
            # Bulk copy: set(array, offset)
            offset = int(value_or_offset)
            src = list(index_or_array)
            for i, v in enumerate(src):
                self._data[offset + i] = self._coerce(v)
        else:
            self._data[int(index_or_array)] = self._coerce(value_or_offset)

    def slice(self, start: Any = 0, end: Any = None) -> "SpryTypedArray":
        s = int(start)
        e = len(self._data) if end is None else int(end)
        result = SpryTypedArray(self._type_name, self._element_size, e - s)
        result._data = list(self._data[s:e])
        return result

    def __getitem__(self, index: Any) -> Any:
        return self._data[int(index)]

    def __setitem__(self, index: Any, value: Any) -> None:
        self._data[int(index)] = self._coerce(value)

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def toList(self) -> list:
        return list(self._data)

    def fill(self, value: Any, start: Any = 0, end: Any = None) -> "SpryTypedArray":
        s = int(start)
        e = len(self._data) if end is None else int(end)
        cv = self._coerce(value)
        for i in range(s, e):
            self._data[i] = cv
        return self

    def subarray(self, start: Any = 0, end: Any = None) -> "SpryTypedArray":
        s = int(start)
        e = len(self._data) if end is None else int(end)
        result = SpryTypedArray(self._type_name, self._element_size, e - s,
                                byte_offset=self._byte_offset + s * self._element_size,
                                _buffer=self._backing_buffer)
        result._data = self._data[s:e]
        return result

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "length":
            return self.length
        if prop == "byteLength":
            return self.byteLength
        if prop == "byteOffset":
            return self.byteOffset
        if prop == "buffer":
            return self.buffer
        if prop == "BYTES_PER_ELEMENT":
            return self._element_size
        if prop == "get":
            return self.get
        if prop == "set":
            return self.set
        if prop == "toList":
            return self.toList
        if prop == "fill":
            return self.fill
        if prop == "subarray":
            return self.subarray
        if prop == "slice":
            return self.slice
        if prop == "reverse":
            def _ta_reverse(_arr: "SpryTypedArray" = self) -> "SpryTypedArray":
                _arr._data.reverse()
                return _arr
            return _ta_reverse
        if prop == "copyWithin":
            def _ta_copyWithin(target: Any, start: Any = 0, end: Any = None,
                               _arr: "SpryTypedArray" = self) -> "SpryTypedArray":
                t = int(target)
                s = int(start)
                e = len(_arr._data) if end is None else int(end)
                src = list(_arr._data[s:e])
                for i, v in enumerate(src):
                    pos = t + i
                    if 0 <= pos < len(_arr._data):
                        _arr._data[pos] = v
                return _arr
            return _ta_copyWithin
        if prop == "join":
            def _ta_join(sep: Any = ",", _arr: "SpryTypedArray" = self) -> str:
                return str(sep).join(str(v) for v in _arr._data)
            return _ta_join
        if prop == "includes":
            return lambda v, _arr=self: v in _arr._data
        if prop == "indexOf":
            def _ta_indexOf(v: Any, from_idx: Any = 0,
                            _arr: "SpryTypedArray" = self) -> int:
                try:
                    return _arr._data.index(v, int(from_idx))
                except ValueError:
                    return -1
            return _ta_indexOf
        if prop == "lastIndexOf":
            def _ta_lastIndexOf(v: Any, _arr: "SpryTypedArray" = self) -> int:
                for i in range(len(_arr._data) - 1, -1, -1):
                    if _arr._data[i] == v:
                        return i
                return -1
            return _ta_lastIndexOf
        if prop == "at":
            def _ta_at(n: Any, _arr: "SpryTypedArray" = self) -> Any:
                i = int(n)
                if -len(_arr._data) <= i < len(_arr._data):
                    return _arr._data[i]
                return None
            return _ta_at
        if prop == "entries":
            return SpryIterator([[i, v] for i, v in enumerate(self._data)])
        if prop == "keys":
            return SpryIterator(list(range(len(self._data))))
        if prop == "values":
            return SpryIterator(list(self._data))
        if prop == "toReversed":
            def _ta_toReversed(_arr: "SpryTypedArray" = self) -> "SpryTypedArray":
                result = SpryTypedArray(_arr._type_name, _arr._element_size, len(_arr._data))
                result._data = list(reversed(_arr._data))
                return result
            return _ta_toReversed
        if prop == "toSorted":
            def _ta_toSorted(_arr: "SpryTypedArray" = self) -> "SpryTypedArray":
                result = SpryTypedArray(_arr._type_name, _arr._element_size, len(_arr._data))
                result._data = sorted(_arr._data)
                return result
            return _ta_toSorted
        # Uint8Array / Uint8ClampedArray binary encoding methods (TC39 Stage 4)
        if self._type_name in ("Uint8Array", "Uint8ClampedArray") and prop == "toBase64":
            def _ta_toBase64(options: Any = None, _arr: "SpryTypedArray" = self) -> str:
                import base64 as _b64
                alphabet = "base64"
                if isinstance(options, dict) and options.get("alphabet") == "base64url":
                    alphabet = "base64url"
                omit_pad = isinstance(options, dict) and bool(options.get("omitPadding", False))
                raw = bytes(int(v) & 0xFF for v in _arr._data)
                if alphabet == "base64url":
                    encoded = _b64.urlsafe_b64encode(raw).decode("ascii")
                else:
                    encoded = _b64.b64encode(raw).decode("ascii")
                if omit_pad:
                    encoded = encoded.rstrip("=")
                return encoded
            return _ta_toBase64
        if self._type_name in ("Uint8Array", "Uint8ClampedArray") and prop == "toHex":
            def _ta_toHex(_arr: "SpryTypedArray" = self) -> str:
                return "".join(f"{int(v) & 0xFF:02x}" for v in _arr._data)
            return _ta_toHex
        raise SpryRuntimeError(f"{self._type_name} has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"{self._type_name}({self._data!r})"


class SpryUint8ClampedArray(SpryTypedArray):
    """Uint8ClampedArray — clamps values to [0, 255]."""

    def __init__(self, length_or_buffer: Any, byte_offset: int = 0, _buffer: Any = None) -> None:
        super().__init__("Uint8ClampedArray", 1, length_or_buffer,
                         byte_offset=byte_offset, _buffer=_buffer)

    def _coerce(self, v: Any) -> int:
        n = round(v) if isinstance(v, float) else int(v)
        return max(0, min(255, n))

    def subarray(self, start: Any = 0, end: Any = None) -> "SpryUint8ClampedArray":
        s = int(start)
        e = len(self._data) if end is None else int(end)
        result = SpryUint8ClampedArray(e - s,
                                       byte_offset=self._byte_offset + s,
                                       _buffer=self._backing_buffer)
        result._data = self._data[s:e]
        return result


class _TypedArrayNamespace:
    def __init__(self, type_name: str, element_size: int) -> None:
        self._type_name = type_name
        self._element_size = element_size

    @property
    def BYTES_PER_ELEMENT(self) -> int:
        return self._element_size

    def new(self, length_or_buffer: Any = 0) -> SpryTypedArray:
        return SpryTypedArray(self._type_name, self._element_size, length_or_buffer)

    def __call__(self, length_or_buffer: Any = 0) -> SpryTypedArray:
        return SpryTypedArray(self._type_name, self._element_size, length_or_buffer)

    def from_(self, iterable: Any) -> SpryTypedArray:
        items = list(iterable)
        arr = SpryTypedArray(self._type_name, self._element_size, items)
        return arr

    def of(self, *args: Any) -> SpryTypedArray:
        return SpryTypedArray(self._type_name, self._element_size, list(args))

    def fromBase64(self, encoded: Any, options: Any = None) -> SpryTypedArray:
        """Uint8Array.fromBase64(str) — decode a base64 string into a Uint8Array."""
        import base64 as _b64
        s = str(encoded).strip()
        alphabet = "base64"
        if isinstance(options, dict) and options.get("alphabet") == "base64url":
            alphabet = "base64url"
        if alphabet == "base64url":
            # Restore padding if missing
            pad = 4 - len(s) % 4
            if pad < 4:
                s += "=" * pad
            raw = _b64.urlsafe_b64decode(s)
        else:
            pad = 4 - len(s) % 4
            if pad < 4:
                s += "=" * pad
            raw = _b64.b64decode(s)
        return SpryTypedArray(self._type_name, self._element_size, list(raw))

    def fromHex(self, hex_str: Any) -> SpryTypedArray:
        """Uint8Array.fromHex(str) — decode a hex string into a Uint8Array."""
        s = str(hex_str)
        raw = bytes.fromhex(s)
        return SpryTypedArray(self._type_name, self._element_size, list(raw))

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "BYTES_PER_ELEMENT":
            return self._element_size
        # Expose fromBase64 and fromHex only for Uint8Array
        if self._type_name in ("Uint8Array", "Uint8ClampedArray"):
            if prop == "fromBase64":
                return self.fromBase64
            if prop == "fromHex":
                return self.fromHex
        try:
            return getattr(self, prop)
        except AttributeError:
            raise SpryRuntimeError(f"{self._type_name} has no property {prop!r}", None)

    def __getattr__(self, prop: str) -> Any:
        if prop == "from":
            return self.from_
        raise AttributeError(prop)

    def __repr__(self) -> str:
        return self._type_name


class _Uint8ClampedArrayNamespace:
    """Uint8ClampedArray global namespace."""

    BYTES_PER_ELEMENT: int = 1

    def new(self, length_or_buffer: Any = 0) -> SpryUint8ClampedArray:
        return SpryUint8ClampedArray(length_or_buffer)

    def from_(self, iterable: Any) -> SpryUint8ClampedArray:
        items = list(iterable)
        arr = SpryUint8ClampedArray(len(items))
        for i, v in enumerate(items):
            arr.set(i, v)
        return arr

    def of(self, *args: Any) -> SpryUint8ClampedArray:
        arr = SpryUint8ClampedArray(len(args))
        for i, v in enumerate(args):
            arr.set(i, v)
        return arr

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "BYTES_PER_ELEMENT":
            return 1
        raise AttributeError(prop)

    def __getattr__(self, prop: str) -> Any:
        if prop == "from":
            return self.from_
        raise AttributeError(prop)

    def __repr__(self) -> str:
        return "Uint8ClampedArray"


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class SpryErrorObject:
    """A structured error object with message, name, optional stack, and optional cause."""

    def __init__(self, name: str, message: str, cause: Any = None) -> None:
        self.name = name
        self.message = str(message)
        self.stack = f"{name}: {message}"
        self.cause = cause

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "name":
            return self.name
        if prop == "message":
            return self.message
        if prop == "stack":
            return self.stack
        if prop == "cause":
            return self.cause
        if prop == "constructor":
            # JS: err.constructor.name === error type name
            return {"name": self.name}
        if prop == "toString":
            return lambda: f"{self.name}: {self.message}"
        raise SpryRuntimeError(f"Error has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"{self.name}: {self.message}"

    def __str__(self) -> str:
        return self.__repr__()


class _ErrorNamespace:
    """Error global — Error.new(message), also callable as Error(message)."""

    stackTraceLimit: int = 10  # class-level attribute

    def __init__(self, name: str) -> None:
        self._name = name

    def __call__(self, message: Any = "", options: Any = None) -> SpryErrorObject:
        cause = None
        if isinstance(options, dict) and "cause" in options:
            cause = options["cause"]
        return SpryErrorObject(self._name, str(message), cause=cause)

    def new(self, message: Any = "", options: Any = None) -> SpryErrorObject:
        cause = None
        if isinstance(options, dict) and "cause" in options:
            cause = options["cause"]
        return SpryErrorObject(self._name, str(message), cause=cause)

    def isError(self, val: Any) -> bool:
        """Return True if val is a SpryErrorObject."""
        return isinstance(val, SpryErrorObject)

    def captureStackTrace(self, obj: Any, constructor: Any = None) -> None:
        """Stub — adds .stack = '' to the object."""
        if isinstance(obj, dict):
            obj["stack"] = ""
        elif isinstance(obj, SpryInstance):
            obj.fields["stack"] = ""
        elif isinstance(obj, SpryErrorObject):
            obj.stack = ""

    def __getattr__(self, prop: str) -> Any:
        if prop == "stackTraceLimit":
            return _ErrorNamespace.stackTraceLimit
        raise AttributeError(prop)

    def __setattr__(self, prop: str, value: Any) -> None:
        if prop == "stackTraceLimit":
            _ErrorNamespace.stackTraceLimit = value
        else:
            object.__setattr__(self, prop, value)

    def __repr__(self) -> str:
        return self._name


# ---------------------------------------------------------------------------
# AggregateError
# ---------------------------------------------------------------------------

class SpryAggregateError(SpryErrorObject):
    """AggregateError — an error that wraps multiple errors."""

    def __init__(self, errors: list, message: str = "", cause: Any = None) -> None:
        super().__init__("AggregateError", message, cause=cause)
        self.errors = errors if isinstance(errors, list) else list(errors)

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "errors":
            return self.errors
        return super()._spry_get_prop(prop)

    def __repr__(self) -> str:
        return f"AggregateError: {self.message} ({len(self.errors)} error(s))"


class _AggregateErrorNamespace:
    """AggregateError global."""

    def __call__(self, errors: Any = None, message: Any = "", options: Any = None) -> SpryAggregateError:
        errs = list(errors) if errors is not None else []
        cause = None
        if isinstance(options, dict) and "cause" in options:
            cause = options["cause"]
        return SpryAggregateError(errs, str(message), cause=cause)

    def new(self, errors: Any = None, message: Any = "", options: Any = None) -> SpryAggregateError:
        errs = list(errors) if errors is not None else []
        cause = None
        if isinstance(options, dict) and "cause" in options:
            cause = options["cause"]
        return SpryAggregateError(errs, str(message), cause=cause)

    def __repr__(self) -> str:
        return "AggregateError"


# ---------------------------------------------------------------------------
# SuppressedError (TC39 Explicit Resource Management)
# ---------------------------------------------------------------------------

class SprySuppressedError(SpryErrorObject):
    """SuppressedError — wraps an outer error alongside the suppressed inner error."""

    def __init__(self, error: Any, suppressed: Any, message: str = "",
                 cause: Any = None) -> None:
        super().__init__("SuppressedError", str(message), cause=cause)
        self.error = error
        self.suppressed = suppressed

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "error":
            return self.error
        if prop == "suppressed":
            return self.suppressed
        return super()._spry_get_prop(prop)

    def __repr__(self) -> str:
        return f"SuppressedError: {self.message}"


class _SuppressedErrorNamespace:
    """SuppressedError global — SuppressedError(error, suppressed[, message]) or new SuppressedError(...)."""

    def __call__(self, error: Any = None, suppressed: Any = None,
                 message: Any = "", options: Any = None) -> SprySuppressedError:
        cause = None
        if isinstance(options, dict) and "cause" in options:
            cause = options["cause"]
        return SprySuppressedError(error, suppressed, str(message), cause=cause)

    def new(self, error: Any = None, suppressed: Any = None,
            message: Any = "", options: Any = None) -> SprySuppressedError:
        cause = None
        if isinstance(options, dict) and "cause" in options:
            cause = options["cause"]
        return SprySuppressedError(error, suppressed, str(message), cause=cause)

    def __repr__(self) -> str:
        return "SuppressedError"

# ---------------------------------------------------------------------------
# crypto.subtle — SubtleCrypto
# ---------------------------------------------------------------------------

class _SubtleCryptoNamespace:
    """SubtleCrypto — synchronous wrappers around hashlib-based operations."""

    _HASH_MAP = {
        "SHA-1": "sha1", "SHA-256": "sha256",
        "SHA-384": "sha384", "SHA-512": "sha512",
        "sha-1": "sha1", "sha-256": "sha256",
        "sha-384": "sha384", "sha-512": "sha512",
    }

    def _to_bytes(self, data: Any) -> bytes:
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, (SpryArrayBuffer, SprySharedArrayBuffer)):
            return bytes(data._data)
        if isinstance(data, SpryTypedArray):
            return bytes(int(x) & 0xFF for x in data._data)
        if isinstance(data, list):
            return bytes(int(x) & 0xFF for x in data)
        if isinstance(data, str):
            return data.encode("utf-8")
        return str(data).encode("utf-8")

    def digest(self, algorithm: Any, data: Any) -> list:
        """Hash data with the given algorithm. Returns a list of bytes."""
        import hashlib as _hl
        alg = self._HASH_MAP.get(str(algorithm), "sha256")
        raw = self._to_bytes(data)
        return list(_hl.new(alg, raw).digest())

    def generateKey(self, algorithm: Any, extractable: Any = True, key_usages: Any = None) -> dict:
        """Stub — generate a key object."""
        alg_name = algorithm.get("name", str(algorithm)) if isinstance(algorithm, dict) else str(algorithm)
        return {"type": "secret", "algorithm": alg_name, "extractable": bool(extractable)}

    def importKey(self, fmt: Any, key_data: Any, algorithm: Any,
                  extractable: Any = True, key_usages: Any = None) -> dict:
        """Stub — import a key."""
        alg_name = algorithm.get("name", str(algorithm)) if isinstance(algorithm, dict) else str(algorithm)
        return {"type": "secret", "algorithm": alg_name, "extractable": bool(extractable)}

    def exportKey(self, fmt: Any, key: Any) -> Any:
        """Stub — export a key."""
        return key

    def sign(self, algorithm: Any, key: Any, data: Any) -> list:
        """Stub — HMAC-SHA256 sign. Requires key.raw to contain the key bytes."""
        import hashlib as _hl
        import hmac as _hmac
        raw = self._to_bytes(data)
        if not isinstance(key, dict) or "raw" not in key:
            raise SpryRuntimeError(
                "SubtleCrypto.sign: key must be a dict with a 'raw' property (bytes/list)", None
            )
        key_bytes = self._to_bytes(key["raw"])
        return list(_hmac.new(key_bytes, raw, _hl.sha256).digest())

    def verify(self, algorithm: Any, key: Any, signature: Any, data: Any) -> bool:
        """Stub — constant-time HMAC-SHA256 verify. Requires key.raw."""
        import hashlib as _hl
        import hmac as _hmac
        if not isinstance(key, dict) or "raw" not in key:
            return False
        raw = self._to_bytes(data)
        key_bytes = self._to_bytes(key["raw"])
        expected = _hmac.new(key_bytes, raw, _hl.sha256).digest()
        sig_bytes = bytes(self._to_bytes(signature))
        return _hmac.compare_digest(expected, sig_bytes)

    def encrypt(self, algorithm: Any, key: Any, data: Any) -> list:
        """Stub — encryption not implemented; raises to avoid false sense of security."""
        raise SpryRuntimeError(
            "SubtleCrypto.encrypt: encryption is not implemented in SpryCode", None
        )

    def decrypt(self, algorithm: Any, key: Any, data: Any) -> list:
        """Stub — decryption not implemented; raises to avoid false sense of security."""
        raise SpryRuntimeError(
            "SubtleCrypto.decrypt: decryption is not implemented in SpryCode", None
        )

    def deriveBits(self, algorithm: Any, key: Any, length: Any) -> list:
        """Stub — returns zero bytes of length bits."""
        return [0] * (int(length) // 8)

    def deriveKey(self, algorithm: Any, base_key: Any, derived_algorithm: Any,
                  extractable: Any = True, key_usages: Any = None) -> dict:
        """Stub — return a derived key placeholder."""
        return {"type": "secret", "algorithm": str(derived_algorithm), "extractable": bool(extractable)}

    def wrapKey(self, fmt: Any, key: Any, wrapping_key: Any, wrapping_algorithm: Any) -> list:
        """Stub — returns empty list."""
        return []

    def unwrapKey(self, fmt: Any, wrapped_key: Any, unwrapping_key: Any, unwrapping_algorithm: Any,
                  unwrapped_key_algorithm: Any, extractable: Any = True, key_usages: Any = None) -> dict:
        """Stub — return a key placeholder."""
        return {"type": "secret"}

    def _spry_get_prop(self, prop: str) -> Any:
        try:
            return getattr(self, prop)
        except AttributeError:
            raise SpryRuntimeError(f"SubtleCrypto has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "SubtleCrypto"


# ---------------------------------------------------------------------------
# Blob / File
# ---------------------------------------------------------------------------

class SpryBlob:
    """Blob — immutable, raw binary data with an optional MIME type."""

    def __init__(self, parts: Any = None, options: Any = None) -> None:
        self._type = ""
        if isinstance(options, dict):
            self._type = str(options.get("type", ""))
        raw: list = []
        if parts is not None:
            for p in (parts if isinstance(parts, list) else [parts]):
                if isinstance(p, (bytes, bytearray)):
                    raw.append(bytes(p))
                elif isinstance(p, SpryBlob):
                    raw.append(p._data)
                elif isinstance(p, SpryArrayBuffer):
                    raw.append(bytes(p._data))
                elif isinstance(p, SpryTypedArray):
                    raw.append(bytes(int(x) & 0xFF for x in p._data))
                else:
                    raw.append(str(p).encode("utf-8"))
        self._data = b"".join(raw)

    @property
    def size(self) -> int:
        return len(self._data)

    @property
    def type(self) -> str:
        return self._type

    def text(self) -> str:
        return self._data.decode("utf-8", errors="replace")

    def arrayBuffer(self) -> "SpryArrayBuffer":
        buf = SpryArrayBuffer(len(self._data))
        buf._data = bytearray(self._data)
        return buf

    def bytes(self) -> list:
        return list(self._data)

    def slice(self, start: Any = 0, end: Any = None, content_type: Any = "") -> "SpryBlob":
        s = int(start)
        e = len(self._data) if end is None else int(end)
        b = SpryBlob()
        b._data = self._data[s:e]
        b._type = str(content_type) if content_type else self._type
        return b

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "size": self.size, "type": self.type,
            "text": self.text, "arrayBuffer": self.arrayBuffer,
            "bytes": self.bytes, "slice": self.slice,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"Blob has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"Blob(size={self.size}, type={self._type!r})"


class _BlobNamespace:
    """Blob global namespace."""

    def new(self, parts: Any = None, options: Any = None) -> SpryBlob:
        return SpryBlob(parts, options)

    def __call__(self, parts: Any = None, options: Any = None) -> SpryBlob:
        return SpryBlob(parts, options)

    def __repr__(self) -> str:
        return "Blob"


class SpryFile(SpryBlob):
    """File — Blob with a filename and lastModified timestamp."""

    def __init__(self, parts: Any = None, name: Any = "", options: Any = None) -> None:
        super().__init__(parts, options)
        self._name = str(name) if name else ""
        import time as _time
        self._last_modified = int(
            options.get("lastModified", _time.time() * 1000)
            if isinstance(options, dict) else _time.time() * 1000
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def lastModified(self) -> int:
        return self._last_modified

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "name":
            return self.name
        if prop == "lastModified":
            return self.lastModified
        return super()._spry_get_prop(prop)

    def __repr__(self) -> str:
        return f"File(name={self._name!r}, size={self.size})"


class _FileNamespace:
    """File global namespace."""

    def new(self, parts: Any = None, name: Any = "", options: Any = None) -> SpryFile:
        return SpryFile(parts, name, options)

    def __call__(self, parts: Any = None, name: Any = "", options: Any = None) -> SpryFile:
        return SpryFile(parts, name, options)

    def __repr__(self) -> str:
        return "File"


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

class SpryHeaders:
    """HTTP Headers — case-insensitive name map, allows multiple values per key."""

    def __init__(self, init: Any = None) -> None:
        self._map: dict = {}
        if isinstance(init, dict):
            for k, v in init.items():
                self.set(k, v)
        elif isinstance(init, list):
            for pair in init:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    self.append(pair[0], pair[1])
        elif isinstance(init, SpryHeaders):
            for k, vs in init._map.items():
                self._map[k] = list(vs)

    def _normalize(self, name: Any) -> str:
        return str(name).lower()

    def get(self, name: Any) -> Any:
        vs = self._map.get(self._normalize(name))
        return ", ".join(vs) if vs else None

    def getAll(self, name: Any) -> list:
        return list(self._map.get(self._normalize(name), []))

    def set(self, name: Any, value: Any) -> None:
        self._map[self._normalize(name)] = [str(value)]

    def append(self, name: Any, value: Any) -> None:
        k = self._normalize(name)
        self._map.setdefault(k, []).append(str(value))

    def has(self, name: Any) -> bool:
        return self._normalize(name) in self._map

    def delete(self, name: Any) -> None:
        self._map.pop(self._normalize(name), None)

    def keys(self) -> list:
        return list(self._map.keys())

    def values(self) -> list:
        return [", ".join(vs) for vs in self._map.values()]

    def entries(self) -> list:
        return [[k, ", ".join(vs)] for k, vs in self._map.items()]

    def forEach(self, fn: Any) -> None:
        for k, vs in self._map.items():
            fn(", ".join(vs), k)

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "get": self.get, "getAll": self.getAll, "set": self.set,
            "append": self.append, "has": self.has, "delete": self.delete,
            "keys": self.keys, "values": self.values, "entries": self.entries,
            "forEach": self.forEach,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"Headers has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"Headers({dict(self._map)!r})"


class _HeadersNamespace:
    def new(self, init: Any = None) -> SpryHeaders:
        return SpryHeaders(init)

    def __call__(self, init: Any = None) -> SpryHeaders:
        return SpryHeaders(init)

    def __repr__(self) -> str:
        return "Headers"


# ---------------------------------------------------------------------------
# FormData
# ---------------------------------------------------------------------------

class SpryFormData:
    """FormData — key/value pairs for form submission."""

    def __init__(self, init: Any = None) -> None:
        self._entries: list = []
        if isinstance(init, dict):
            for k, v in init.items():
                self.append(k, v)

    def append(self, name: Any, value: Any, filename: Any = None) -> None:
        self._entries.append((str(name), value))

    def set(self, name: Any, value: Any) -> None:
        key = str(name)
        self._entries = [(k, v) for k, v in self._entries if k != key]
        self._entries.append((key, value))

    def get(self, name: Any) -> Any:
        key = str(name)
        for k, v in self._entries:
            if k == key:
                return v
        return None

    def getAll(self, name: Any) -> list:
        key = str(name)
        return [v for k, v in self._entries if k == key]

    def has(self, name: Any) -> bool:
        key = str(name)
        return any(k == key for k, _ in self._entries)

    def delete(self, name: Any) -> None:
        key = str(name)
        self._entries = [(k, v) for k, v in self._entries if k != key]

    def keys(self) -> list:
        seen: list = []
        for k, _ in self._entries:
            if k not in seen:
                seen.append(k)
        return seen

    def values(self) -> list:
        return [v for _, v in self._entries]

    def entries(self) -> list:
        return [[k, v] for k, v in self._entries]

    def forEach(self, fn: Any) -> None:
        for k, v in self._entries:
            fn(v, k)

    @property
    def size(self) -> int:
        return len(self._entries)

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "append": self.append, "set": self.set, "get": self.get,
            "getAll": self.getAll, "has": self.has, "delete": self.delete,
            "keys": self.keys, "values": self.values, "entries": self.entries,
            "forEach": self.forEach, "size": self.size,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"FormData has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"FormData({self._entries!r})"


class _FormDataNamespace:
    def new(self, init: Any = None) -> SpryFormData:
        return SpryFormData(init)

    def __call__(self, init: Any = None) -> SpryFormData:
        return SpryFormData(init)

    def __repr__(self) -> str:
        return "FormData"


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------

class SpryRequest:
    """HTTP Request object (Fetch API)."""

    def __init__(self, url: Any, init: Any = None) -> None:
        self._url = str(url)
        self._method = "GET"
        self._headers = SpryHeaders()
        self._body: Any = None
        if isinstance(init, dict):
            self._method = str(init.get("method", "GET")).upper()
            if "headers" in init:
                h = init["headers"]
                self._headers = h if isinstance(h, SpryHeaders) else SpryHeaders(h)
            if "body" in init:
                self._body = init["body"]

    @property
    def url(self) -> str:
        return self._url

    @property
    def method(self) -> str:
        return self._method

    @property
    def headers(self) -> SpryHeaders:
        return self._headers

    @property
    def body(self) -> Any:
        return self._body

    def text(self) -> str:
        if self._body is None:
            return ""
        if isinstance(self._body, SpryBlob):
            return self._body.text()
        return str(self._body)

    def json(self) -> Any:
        import json as _json
        return _json.loads(self.text())

    def clone(self) -> "SpryRequest":
        r = SpryRequest(self._url)
        r._method = self._method
        r._headers = SpryHeaders(self._headers)
        r._body = self._body
        return r

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "url": self.url, "method": self.method, "headers": self.headers,
            "body": self.body, "text": self.text, "json": self.json, "clone": self.clone,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"Request has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"Request({self._url!r}, method={self._method!r})"


class SpryResponse:
    """HTTP Response object (Fetch API)."""

    def __init__(self, body: Any = None, init: Any = None) -> None:
        self._body = body
        self._status = 200
        self._status_text = "OK"
        self._headers = SpryHeaders()
        if isinstance(init, dict):
            self._status = int(init.get("status", 200))
            self._status_text = str(init.get("statusText", "OK"))
            if "headers" in init:
                h = init["headers"]
                self._headers = h if isinstance(h, SpryHeaders) else SpryHeaders(h)

    @property
    def ok(self) -> bool:
        return 200 <= self._status < 300

    @property
    def status(self) -> int:
        return self._status

    @property
    def statusText(self) -> str:
        return self._status_text

    @property
    def headers(self) -> SpryHeaders:
        return self._headers

    @property
    def body(self) -> Any:
        return self._body

    def _body_text(self) -> str:
        if self._body is None:
            return ""
        if isinstance(self._body, SpryBlob):
            return self._body.text()
        if isinstance(self._body, dict):
            import json as _json
            return _json.dumps(self._body)
        return str(self._body)

    def text(self) -> str:
        return self._body_text()

    def json(self) -> Any:
        import json as _json
        return _json.loads(self._body_text())

    def blob(self) -> SpryBlob:
        return SpryBlob([self._body_text()])

    def arrayBuffer(self) -> SpryArrayBuffer:
        raw = self._body_text().encode("utf-8")
        buf = SpryArrayBuffer(len(raw))
        buf._data = bytearray(raw)
        return buf

    def bytes(self) -> list:
        return list(self._body_text().encode("utf-8"))

    def clone(self) -> "SpryResponse":
        r = SpryResponse(self._body, {"status": self._status, "statusText": self._status_text})
        r._headers = SpryHeaders(self._headers)
        return r

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "ok": self.ok, "status": self.status, "statusText": self.statusText,
            "headers": self.headers, "body": self.body,
            "text": self.text, "json": self.json, "blob": self.blob,
            "arrayBuffer": self.arrayBuffer, "bytes": self.bytes, "clone": self.clone,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"Response has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"Response(status={self._status})"


class _RequestNamespace:
    def new(self, url: Any, init: Any = None) -> SpryRequest:
        return SpryRequest(url, init)

    def __call__(self, url: Any, init: Any = None) -> SpryRequest:
        return SpryRequest(url, init)

    def __repr__(self) -> str:
        return "Request"


class _ResponseNamespace:
    def new(self, body: Any = None, init: Any = None) -> SpryResponse:
        return SpryResponse(body, init)

    def __call__(self, body: Any = None, init: Any = None) -> SpryResponse:
        return SpryResponse(body, init)

    def error(self) -> SpryResponse:
        return SpryResponse(None, {"status": 0, "statusText": "Network Error"})

    def redirect(self, url: Any, status: Any = 302) -> SpryResponse:
        r = SpryResponse(None, {"status": int(status), "statusText": "Found"})
        r._headers.set("Location", str(url))
        return r

    def json(self, data: Any, init: Any = None) -> SpryResponse:
        import json as _json
        body = _json.dumps(data)
        r = SpryResponse(body, init)
        r._headers.set("Content-Type", "application/json")
        return r

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {"error": self.error, "redirect": self.redirect, "json": self.json}
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"Response has no static property {prop!r}", None)

    def __repr__(self) -> str:
        return "Response"


def _make_fetch_fn(permissions: Any) -> Any:
    """Return a fetch(url, options?) function that wraps the http helper."""
    http_helper = _HttpHelper(permissions)

    def _fetch(url: Any, options: Any = None) -> SpryResponse:
        url_str = str(url)
        method = "GET"
        body = None
        if isinstance(options, dict):
            method = str(options.get("method", "GET")).upper()
            body = options.get("body")
        try:
            if method in ("POST", "PUT", "PATCH"):
                result = http_helper.post(url_str, body)
            else:
                result = http_helper.get(url_str)
            if isinstance(result, dict):
                status = result.get("status", 200)
                resp_body = result.get("body", "")
                return SpryResponse(resp_body, {"status": status})
            return SpryResponse(str(result), {"status": 200})
        except Exception as exc:
            return SpryResponse(str(exc), {"status": 0, "statusText": "Network Error"})

    return _fetch


# ---------------------------------------------------------------------------
# EventTarget / Event / CustomEvent
# ---------------------------------------------------------------------------

class SpryEvent:
    """DOM Event object."""

    def __init__(self, event_type: str, init: Any = None) -> None:
        self._type = str(event_type)
        self._bubbles = False
        self._cancelable = False
        self._composed = False
        self._target: Any = None
        self._default_prevented = False
        if isinstance(init, dict):
            self._bubbles = bool(init.get("bubbles", False))
            self._cancelable = bool(init.get("cancelable", False))
            self._composed = bool(init.get("composed", False))

    @property
    def type(self) -> str:
        return self._type

    @property
    def bubbles(self) -> bool:
        return self._bubbles

    @property
    def cancelable(self) -> bool:
        return self._cancelable

    @property
    def composed(self) -> bool:
        return self._composed

    @property
    def target(self) -> Any:
        return self._target

    @property
    def defaultPrevented(self) -> bool:
        return self._default_prevented

    def preventDefault(self) -> None:
        if self._cancelable:
            self._default_prevented = True

    def stopPropagation(self) -> None:
        pass

    def stopImmediatePropagation(self) -> None:
        pass

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "type": self.type, "bubbles": self.bubbles, "cancelable": self.cancelable,
            "composed": self.composed, "target": self.target,
            "defaultPrevented": self.defaultPrevented,
            "preventDefault": self.preventDefault,
            "stopPropagation": self.stopPropagation,
            "stopImmediatePropagation": self.stopImmediatePropagation,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"Event has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"Event(type={self._type!r})"


class SpryCustomEvent(SpryEvent):
    """CustomEvent — Event with a detail payload."""

    def __init__(self, event_type: str, init: Any = None) -> None:
        super().__init__(event_type, init)
        self._detail = init.get("detail") if isinstance(init, dict) else None

    @property
    def detail(self) -> Any:
        return self._detail

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "detail":
            return self.detail
        return super()._spry_get_prop(prop)

    def __repr__(self) -> str:
        return f"CustomEvent(type={self._type!r}, detail={self._detail!r})"


class SpryEventTarget:
    """EventTarget — addEventListener / removeEventListener / dispatchEvent."""

    def __init__(self, call_fn: Any = None) -> None:
        self._listeners: dict = {}
        self._call_fn = call_fn

    def _invoke(self, fn: Any, args: list) -> Any:
        if callable(fn):
            return fn(*args)
        if self._call_fn is not None:
            return self._call_fn(fn, args)
        return None

    def addEventListener(self, event_type: Any, listener: Any, options: Any = None) -> None:
        key = str(event_type)
        self._listeners.setdefault(key, [])
        if listener not in self._listeners[key]:
            self._listeners[key].append(listener)
    addEventListener._spry_raw_args = True  # type: ignore[attr-defined]

    def removeEventListener(self, event_type: Any, listener: Any, options: Any = None) -> None:
        key = str(event_type)
        lst = self._listeners.get(key, [])
        if listener in lst:
            lst.remove(listener)
    removeEventListener._spry_raw_args = True  # type: ignore[attr-defined]

    def dispatchEvent(self, event: Any) -> bool:
        if isinstance(event, SpryEvent):
            event._target = self
            key = event.type
        else:
            key = str(event)
        for listener in list(self._listeners.get(key, [])):
            try:
                self._invoke(listener, [event])
            except Exception:
                pass
        return not (isinstance(event, SpryEvent) and event.defaultPrevented)

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "addEventListener": self.addEventListener,
            "removeEventListener": self.removeEventListener,
            "dispatchEvent": self.dispatchEvent,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"EventTarget has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "EventTarget"


class _EventNamespace:
    def new(self, event_type: Any, init: Any = None) -> SpryEvent:
        return SpryEvent(str(event_type), init)

    def __call__(self, event_type: Any, init: Any = None) -> SpryEvent:
        return SpryEvent(str(event_type), init)

    def __repr__(self) -> str:
        return "Event"


class _CustomEventNamespace:
    def new(self, event_type: Any, init: Any = None) -> SpryCustomEvent:
        return SpryCustomEvent(str(event_type), init)

    def __call__(self, event_type: Any, init: Any = None) -> SpryCustomEvent:
        return SpryCustomEvent(str(event_type), init)

    def __repr__(self) -> str:
        return "CustomEvent"


class _EventTargetNamespace:
    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn

    def new(self) -> SpryEventTarget:
        return SpryEventTarget(call_fn=self._call_fn)

    def __call__(self) -> SpryEventTarget:
        return SpryEventTarget(call_fn=self._call_fn)

    def __repr__(self) -> str:
        return "EventTarget"


# ---------------------------------------------------------------------------
# ReadableStream / WritableStream / TransformStream
# ---------------------------------------------------------------------------

class _ReadableStreamController:
    """Controller for ReadableStream."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream

    def enqueue(self, chunk: Any) -> None:
        self._stream._chunks.append(chunk)

    def close(self) -> None:
        self._stream._closed = True

    def error(self, reason: Any = None) -> None:
        self._stream._closed = True

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {"enqueue": self.enqueue, "close": self.close, "error": self.error}
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"ReadableStreamController has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "ReadableStreamDefaultController"


class _ReadableStreamDefaultReader:
    """Default reader for ReadableStream."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._index = 0

    def read(self) -> dict:
        if self._index < len(self._stream._chunks):
            chunk = self._stream._chunks[self._index]
            self._index += 1
            return {"value": chunk, "done": False}
        return {"value": None, "done": True}

    def releaseLock(self) -> None:
        self._stream._locked = False

    def cancel(self, reason: Any = None) -> None:
        self._stream._closed = True
        self.releaseLock()

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {"read": self.read, "releaseLock": self.releaseLock, "cancel": self.cancel}
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"ReadableStreamDefaultReader has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "ReadableStreamDefaultReader"


class _TransformStreamDefaultController:
    """Controller for TransformStream."""

    def __init__(self, readable: Any) -> None:
        self._readable = readable

    def enqueue(self, chunk: Any) -> None:
        self._readable._chunks.append(chunk)

    def terminate(self) -> None:
        self._readable._closed = True

    def error(self, reason: Any = None) -> None:
        self._readable._closed = True

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {"enqueue": self.enqueue, "terminate": self.terminate, "error": self.error}
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"TransformStreamDefaultController has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "TransformStreamDefaultController"


class _WritableStreamDefaultWriter:
    """Default writer for WritableStream."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream

    def write(self, chunk: Any) -> None:
        self._stream._chunks.append(chunk)
        if self._stream._sink and isinstance(self._stream._sink, dict):
            write_fn = self._stream._sink.get("write")
            if callable(write_fn):
                write_fn(chunk)

    def close(self) -> None:
        self._stream._closed = True

    def abort(self, reason: Any = None) -> None:
        self._stream._closed = True

    def releaseLock(self) -> None:
        self._stream._locked = False

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "write": self.write, "close": self.close,
            "abort": self.abort, "releaseLock": self.releaseLock,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"WritableStreamDefaultWriter has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "WritableStreamDefaultWriter"


class SpryReadableStream:
    """ReadableStream — pull-based byte stream."""

    def __init__(self, source: Any = None, _call_fn: Any = None) -> None:
        self._source = source
        self._chunks: list = []
        self._closed = False
        self._locked = False
        self._call_fn = _call_fn
        if isinstance(source, dict):
            start_fn = source.get("start")
            if start_fn is not None:
                controller = _ReadableStreamController(self)
                if callable(start_fn):
                    start_fn(controller)
                elif _call_fn is not None:
                    _call_fn(start_fn, [controller])

    def _invoke(self, fn: Any, args: list) -> Any:
        if callable(fn):
            return fn(*args)
        if self._call_fn is not None:
            return self._call_fn(fn, args)
        return None

    @property
    def locked(self) -> bool:
        return self._locked

    def getReader(self) -> _ReadableStreamDefaultReader:
        self._locked = True
        return _ReadableStreamDefaultReader(self)

    def pipeThrough(self, transform: Any) -> "SpryReadableStream":
        if isinstance(transform, SpryTransformStream):
            ctrl = _TransformStreamDefaultController(transform._readable)
            for chunk in self._chunks:
                xfm = transform._transformer.get("transform")
                if xfm is not None:
                    transform._invoke(xfm, [chunk, ctrl])
            transform._readable._closed = True
            return transform._readable
        return self

    def pipeTo(self, dest: Any) -> None:
        if isinstance(dest, SpryWritableStream):
            for chunk in self._chunks:
                dest._chunks.append(chunk)

    def tee(self) -> list:
        s1 = SpryReadableStream()
        s2 = SpryReadableStream()
        s1._chunks = list(self._chunks)
        s2._chunks = list(self._chunks)
        return [s1, s2]

    def cancel(self, reason: Any = None) -> None:
        self._closed = True

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "locked": self.locked, "getReader": self.getReader,
            "pipeThrough": self.pipeThrough, "pipeTo": self.pipeTo,
            "tee": self.tee, "cancel": self.cancel,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"ReadableStream has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "ReadableStream"


class SpryWritableStream:
    """WritableStream — push-based byte stream."""

    def __init__(self, sink: Any = None) -> None:
        self._sink = sink
        self._chunks: list = []
        self._closed = False
        self._locked = False

    @property
    def locked(self) -> bool:
        return self._locked

    def getWriter(self) -> _WritableStreamDefaultWriter:
        self._locked = True
        return _WritableStreamDefaultWriter(self)

    def close(self) -> None:
        self._closed = True

    def abort(self, reason: Any = None) -> None:
        self._closed = True

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "locked": self.locked, "getWriter": self.getWriter,
            "close": self.close, "abort": self.abort,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"WritableStream has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "WritableStream"


class SpryTransformStream:
    """TransformStream — readable + writable pair."""

    def __init__(self, transformer: Any = None, _call_fn: Any = None) -> None:
        self._transformer = transformer if isinstance(transformer, dict) else {}
        self._call_fn = _call_fn
        self._readable = SpryReadableStream(_call_fn=_call_fn)
        self._writable = SpryWritableStream()
        start_fn = self._transformer.get("start")
        if start_fn is not None:
            ctrl = _TransformStreamDefaultController(self._readable)
            if callable(start_fn):
                start_fn(ctrl)
            elif _call_fn is not None:
                _call_fn(start_fn, [ctrl])

    def _invoke(self, fn: Any, args: list) -> Any:
        if callable(fn):
            return fn(*args)
        if self._call_fn is not None:
            return self._call_fn(fn, args)
        return None

    @property
    def readable(self) -> SpryReadableStream:
        return self._readable

    @property
    def writable(self) -> SpryWritableStream:
        return self._writable

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {"readable": self.readable, "writable": self.writable}
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"TransformStream has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "TransformStream"


class _ReadableStreamNamespace:
    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn

    def new(self, source: Any = None) -> SpryReadableStream:
        return SpryReadableStream(source, _call_fn=self._call_fn)

    def __call__(self, source: Any = None) -> SpryReadableStream:
        return SpryReadableStream(source, _call_fn=self._call_fn)

    def from_(self, iterable: Any) -> SpryReadableStream:
        s = SpryReadableStream(_call_fn=self._call_fn)
        s._chunks = list(iterable) if hasattr(iterable, "__iter__") else [iterable]
        return s

    def __getattr__(self, prop: str) -> Any:
        if prop == "from":
            return self.from_
        raise AttributeError(prop)

    def __repr__(self) -> str:
        return "ReadableStream"


class _WritableStreamNamespace:
    def new(self, sink: Any = None) -> SpryWritableStream:
        return SpryWritableStream(sink)

    def __call__(self, sink: Any = None) -> SpryWritableStream:
        return SpryWritableStream(sink)

    def __repr__(self) -> str:
        return "WritableStream"


class _TransformStreamNamespace:
    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn

    def new(self, transformer: Any = None) -> SpryTransformStream:
        return SpryTransformStream(transformer, _call_fn=self._call_fn)

    def __call__(self, transformer: Any = None) -> SpryTransformStream:
        return SpryTransformStream(transformer, _call_fn=self._call_fn)

    def __repr__(self) -> str:
        return "TransformStream"


# ---------------------------------------------------------------------------
# CompressionStream / DecompressionStream
# ---------------------------------------------------------------------------

class _CompressionStreamImpl:
    """CompressionStream / DecompressionStream."""

    def __init__(self, format_name: str, decompress: bool = False) -> None:
        self._format = format_name
        self._decompress = decompress
        self._readable = SpryReadableStream()
        self._writable = SpryWritableStream()

    @property
    def readable(self) -> SpryReadableStream:
        return self._readable

    @property
    def writable(self) -> SpryWritableStream:
        return self._writable

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {"readable": self.readable, "writable": self.writable}
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"CompressionStream has no property {prop!r}", None)

    def __repr__(self) -> str:
        label = "Decompression" if self._decompress else "Compression"
        return f"{label}Stream({self._format!r})"


class _CompressionStreamNamespace:
    def new(self, fmt: Any = "gzip") -> _CompressionStreamImpl:
        return _CompressionStreamImpl(str(fmt), decompress=False)

    def __call__(self, fmt: Any = "gzip") -> _CompressionStreamImpl:
        return _CompressionStreamImpl(str(fmt), decompress=False)

    def __repr__(self) -> str:
        return "CompressionStream"


class _DecompressionStreamNamespace:
    def new(self, fmt: Any = "gzip") -> _CompressionStreamImpl:
        return _CompressionStreamImpl(str(fmt), decompress=True)

    def __call__(self, fmt: Any = "gzip") -> _CompressionStreamImpl:
        return _CompressionStreamImpl(str(fmt), decompress=True)

    def __repr__(self) -> str:
        return "DecompressionStream"


# ---------------------------------------------------------------------------
# BroadcastChannel / MessageChannel / MessagePort / MessageEvent
# ---------------------------------------------------------------------------

_broadcast_channels: dict = {}  # name → list of SpryBroadcastChannel instances


class SpryMessageEvent(SpryEvent):
    """MessageEvent — event with a data payload."""

    def __init__(self, event_type: str, init: Any = None) -> None:
        super().__init__(event_type, init)
        self._data = init.get("data") if isinstance(init, dict) else None
        self._origin = str(init.get("origin", "")) if isinstance(init, dict) else ""
        self._ports: list = []

    @property
    def data(self) -> Any:
        return self._data

    @property
    def origin(self) -> str:
        return self._origin

    @property
    def ports(self) -> list:
        return self._ports

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "data":
            return self.data
        if prop == "origin":
            return self.origin
        if prop == "ports":
            return self.ports
        return super()._spry_get_prop(prop)

    def __repr__(self) -> str:
        return f"MessageEvent(data={self._data!r})"


class SpryBroadcastChannel:
    """BroadcastChannel — pub/sub between channels with the same name."""

    def __init__(self, name: str, call_fn: Any = None) -> None:
        self._name = str(name)
        self._closed = False
        self._message_handler: Any = None
        self._call_fn = call_fn
        _broadcast_channels.setdefault(self._name, []).append(self)

    def _invoke(self, fn: Any, args: list) -> Any:
        if callable(fn):
            return fn(*args)
        if self._call_fn is not None:
            return self._call_fn(fn, args)
        return None

    @property
    def name(self) -> str:
        return self._name

    def postMessage(self, message: Any) -> None:
        if self._closed:
            raise SpryRuntimeError("BroadcastChannel is closed", None)
        event = SpryMessageEvent("message", {"data": message})
        for ch in list(_broadcast_channels.get(self._name, [])):
            if ch is not self and not ch._closed and ch._message_handler is not None:
                try:
                    ch._invoke(ch._message_handler, [event])
                except Exception:
                    pass

    def close(self) -> None:
        self._closed = True
        lst = _broadcast_channels.get(self._name, [])
        if self in lst:
            lst.remove(self)

    def addEventListener(self, event_type: Any, listener: Any, options: Any = None) -> None:
        if str(event_type) == "message":
            self._message_handler = listener

    def removeEventListener(self, event_type: Any, listener: Any, options: Any = None) -> None:
        if str(event_type) == "message" and self._message_handler is listener:
            self._message_handler = None

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "onmessage":
            return self._message_handler
        _m: dict = {
            "name": self.name, "postMessage": self.postMessage, "close": self.close,
            "addEventListener": self.addEventListener,
            "removeEventListener": self.removeEventListener,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"BroadcastChannel has no property {prop!r}", None)

    def _spry_set_prop(self, prop: str, value: Any) -> None:
        if prop == "onmessage":
            self._message_handler = value
        else:
            raise SpryRuntimeError(f"BroadcastChannel.{prop} is not settable", None)

    def __repr__(self) -> str:
        return f"BroadcastChannel({self._name!r})"


class _BroadcastChannelNamespace:
    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn

    def new(self, name: Any) -> SpryBroadcastChannel:
        return SpryBroadcastChannel(str(name), call_fn=self._call_fn)

    def __call__(self, name: Any) -> SpryBroadcastChannel:
        return SpryBroadcastChannel(str(name), call_fn=self._call_fn)

    def __repr__(self) -> str:
        return "BroadcastChannel"


class SpryMessagePort(SpryEventTarget):
    """MessagePort — one end of a MessageChannel."""

    def __init__(self, call_fn: Any = None) -> None:
        super().__init__(call_fn=call_fn)
        self._other: Any = None
        self._started = False

    def postMessage(self, message: Any, transfer: Any = None) -> None:
        if self._other is not None:
            event = SpryMessageEvent("message", {"data": message})
            self._other.dispatchEvent(event)

    def start(self) -> None:
        self._started = True

    def close(self) -> None:
        self._other = None

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {"postMessage": self.postMessage, "start": self.start, "close": self.close}
        if prop in _m:
            return _m[prop]
        return super()._spry_get_prop(prop)

    def __repr__(self) -> str:
        return "MessagePort"


class SpryMessageChannel:
    """MessageChannel — two connected MessagePorts."""

    def __init__(self, call_fn: Any = None) -> None:
        self.port1 = SpryMessagePort(call_fn=call_fn)
        self.port2 = SpryMessagePort(call_fn=call_fn)
        self.port1._other = self.port2
        self.port2._other = self.port1

    def _spry_get_prop(self, prop: str) -> Any:
        if prop == "port1":
            return self.port1
        if prop == "port2":
            return self.port2
        raise SpryRuntimeError(f"MessageChannel has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "MessageChannel"


class _MessageChannelNamespace:
    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn

    def new(self) -> SpryMessageChannel:
        return SpryMessageChannel(call_fn=self._call_fn)

    def __call__(self) -> SpryMessageChannel:
        return SpryMessageChannel(call_fn=self._call_fn)

    def __repr__(self) -> str:
        return "MessageChannel"


# ---------------------------------------------------------------------------
# navigator
# ---------------------------------------------------------------------------

class _NavigatorNamespace:
    """navigator global — basic runtime environment info."""

    @property
    def userAgent(self) -> str:
        import platform as _p
        return f"SpryCode/1.0 ({_p.system()}; {_p.machine()})"

    @property
    def language(self) -> str:
        import locale as _l
        try:
            loc = _l.getlocale()[0] or "en-US"
        except Exception:
            loc = "en-US"
        return loc.replace("_", "-")

    @property
    def languages(self) -> list:
        return [self.language, "en"]

    @property
    def onLine(self) -> bool:
        return True

    @property
    def hardwareConcurrency(self) -> int:
        import os as _os
        return _os.cpu_count() or 1

    @property
    def platform(self) -> str:
        import platform as _p
        return _p.system()

    @property
    def cookieEnabled(self) -> bool:
        return False

    def _spry_get_prop(self, prop: str) -> Any:
        try:
            return getattr(self, prop)
        except AttributeError:
            raise SpryRuntimeError(f"navigator has no property {prop!r}", None)

    def __repr__(self) -> str:
        return "Navigator"


# ---------------------------------------------------------------------------
# Phase 110 — Microservice runtime classes
# ---------------------------------------------------------------------------

class SpryQueue:
    """Queue — FIFO data structure for microservice message passing."""

    def __init__(self) -> None:
        self._items: list = []

    # ---- core operations ----
    def enqueue(self, item: Any) -> None:
        self._items.append(item)

    def dequeue(self) -> Any:
        if not self._items:
            raise SpryRuntimeError("Queue is empty", None)
        return self._items.pop(0)

    def peek(self) -> Any:
        if not self._items:
            return SPRY_UNDEFINED
        return self._items[0]

    def isEmpty(self) -> bool:
        return len(self._items) == 0

    def clear(self) -> None:
        self._items.clear()

    @property
    def size(self) -> int:
        return len(self._items)

    def toArray(self) -> list:
        return list(self._items)

    # ---- SpryCode property protocol ----
    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "enqueue": self.enqueue,
            "dequeue": self.dequeue,
            "peek": self.peek,
            "isEmpty": self.isEmpty,
            "clear": self.clear,
            "size": self.size,
            "toArray": self.toArray,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"Queue has no property {prop!r}", None)

    def _spry_set_prop(self, prop: str, value: Any) -> None:
        raise SpryRuntimeError(f"Queue.{prop} is not settable", None)

    def __repr__(self) -> str:
        return f"Queue({self._items!r})"


class _SpryQueueNamespace:
    def __call__(self, *args: Any) -> SpryQueue:
        q = SpryQueue()
        for a in args:
            if isinstance(a, list):
                for item in a:
                    q.enqueue(item)
        return q

    def new(self, *args: Any) -> SpryQueue:
        return self(*args)

    def __repr__(self) -> str:
        return "Queue"


class SpryChannel:
    """Channel — buffered or unbuffered channel for service-to-service messaging."""

    def __init__(self, capacity: int = 0) -> None:
        self._capacity = int(capacity) if capacity else 0  # 0 = unbounded
        self._buf: list = []
        self._closed = False

    def send(self, value: Any) -> None:
        if self._closed:
            raise SpryRuntimeError("Cannot send on a closed Channel", None)
        if self._capacity > 0 and len(self._buf) >= self._capacity:
            raise SpryRuntimeError("Channel buffer is full", None)
        self._buf.append(value)

    def receive(self) -> Any:
        if not self._buf:
            raise SpryRuntimeError("Channel is empty", None)
        return self._buf.pop(0)

    def tryReceive(self) -> Any:
        """Returns {value, ok} object; ok=false if channel is empty."""
        if not self._buf:
            return {"value": SPRY_UNDEFINED, "ok": False}
        return {"value": self._buf.pop(0), "ok": True}

    def close(self) -> None:
        self._closed = True

    @property
    def size(self) -> int:
        return len(self._buf)

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def capacity(self) -> int:
        return self._capacity

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "send": self.send,
            "receive": self.receive,
            "tryReceive": self.tryReceive,
            "close": self.close,
            "size": self.size,
            "closed": self.closed,
            "capacity": self.capacity,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"Channel has no property {prop!r}", None)

    def _spry_set_prop(self, prop: str, value: Any) -> None:
        raise SpryRuntimeError(f"Channel.{prop} is not settable", None)

    def __repr__(self) -> str:
        return f"Channel(capacity={self._capacity}, size={self.size})"


class _SpryChannelNamespace:
    def __call__(self, capacity: Any = 0) -> SpryChannel:
        return SpryChannel(int(capacity) if capacity else 0)

    def new(self, capacity: Any = 0) -> SpryChannel:
        return self(capacity)

    def __repr__(self) -> str:
        return "Channel"


# Circuit Breaker states
_CB_CLOSED = "closed"        # normal operation
_CB_OPEN = "open"            # failing — reject fast
_CB_HALF_OPEN = "half-open"  # probe — allow one call through


class SpryCircuitBreaker:
    """CircuitBreaker — wraps a callable with fault-tolerance circuit breaker pattern."""

    def __init__(self, options: Any = None, call_fn: Any = None) -> None:
        import time as _time
        self._time = _time
        self._call_fn = call_fn
        opts: dict = {}
        if isinstance(options, dict):
            opts = options
        elif hasattr(options, "_data"):
            opts = options._data
        self._threshold: int = int(opts.get("threshold", 3))
        self._timeout_ms: float = float(opts.get("timeout", 5000))
        self._state: str = _CB_CLOSED
        self._failures: int = 0
        self._opened_at: float = 0.0
        self._successes: int = 0
        self._half_open_threshold: int = int(opts.get("halfOpenThreshold", 1))

    def _call_value(self, fn: Any, args: list) -> Any:
        if callable(fn):
            return fn(*args)
        if self._call_fn is not None:
            return self._call_fn(fn, args)
        raise SpryRuntimeError("CircuitBreaker: called value is not callable", None)

    def call(self, fn: Any, *args: Any) -> Any:
        import time as _time
        now = _time.time() * 1000  # ms

        if self._state == _CB_OPEN:
            elapsed = now - self._opened_at
            if elapsed >= self._timeout_ms:
                self._state = _CB_HALF_OPEN
                self._successes = 0
            else:
                raise SpryRuntimeError(
                    f"CircuitBreaker is OPEN (next attempt in {int(self._timeout_ms - elapsed)}ms)",
                    None,
                )

        try:
            result = self._call_value(fn, list(args))
            # success path
            if self._state == _CB_HALF_OPEN:
                self._successes += 1
                if self._successes >= self._half_open_threshold:
                    self._state = _CB_CLOSED
                    self._failures = 0
            else:
                self._failures = 0
            return result
        except Exception as exc:
            self._failures += 1
            if self._state == _CB_HALF_OPEN or self._failures >= self._threshold:
                self._state = _CB_OPEN
                self._opened_at = now
                self._failures = self._threshold
            raise

    def reset(self) -> None:
        self._state = _CB_CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at = 0.0

    @property
    def state(self) -> str:
        return self._state

    @property
    def failures(self) -> int:
        return self._failures

    @property
    def threshold(self) -> int:
        return self._threshold

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {
            "call": self.call,
            "reset": self.reset,
            "state": self.state,
            "failures": self.failures,
            "threshold": self.threshold,
        }
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"CircuitBreaker has no property {prop!r}", None)

    def _spry_set_prop(self, prop: str, value: Any) -> None:
        raise SpryRuntimeError(f"CircuitBreaker.{prop} is not settable", None)

    def __repr__(self) -> str:
        return f"CircuitBreaker(state={self._state!r}, failures={self._failures})"


class _SpryCircuitBreakerNamespace:
    def __init__(self, call_fn: Any = None) -> None:
        self._call_fn = call_fn

    def __call__(self, options: Any = None) -> SpryCircuitBreaker:
        return SpryCircuitBreaker(options, call_fn=self._call_fn)

    def new(self, options: Any = None) -> SpryCircuitBreaker:
        return self(options)

    def __repr__(self) -> str:
        return "CircuitBreaker"


def _make_object(d: dict) -> Any:
    """Create a simple SpryCode-accessible object from a Python dict."""
    class _Obj:
        def __init__(self, data: dict) -> None:
            self._data = data
        def _spry_get_prop(self, prop: str) -> Any:
            if prop in self._data:
                return self._data[prop]
            raise SpryRuntimeError(f"object has no property {prop!r}", None)
        def _spry_set_prop(self, prop: str, value: Any) -> None:
            self._data[prop] = value
        def __repr__(self) -> str:
            return repr(self._data)
    return _Obj(d)


class SpryThrottledFn:
    """Throttled function — at most once per <interval_ms> milliseconds."""

    def __init__(self, fn: Any, interval_ms: float, call_fn: Any = None) -> None:
        self._fn = fn
        self._interval_ms = float(interval_ms)
        self._call_fn = call_fn
        self._last_call: float = -float("inf")
        self._last_result: Any = SPRY_UNDEFINED

    def _invoke(self, args: list) -> Any:
        if callable(self._fn):
            return self._fn(*args)
        if self._call_fn is not None:
            return self._call_fn(self._fn, args)
        return SPRY_UNDEFINED

    def __call__(self, *args: Any) -> Any:
        import time as _time
        now = _time.time() * 1000
        if now - self._last_call >= self._interval_ms:
            self._last_call = now
            self._last_result = self._invoke(list(args))
        return self._last_result

    def __repr__(self) -> str:
        return f"throttle(fn, {self._interval_ms}ms)"


class SpryDebouncedFn:
    """Debounced function — resets timer on every call; fires after <delay_ms> of silence."""

    def __init__(self, fn: Any, delay_ms: float, call_fn: Any = None) -> None:
        self._fn = fn
        self._delay_ms = float(delay_ms)
        self._call_fn = call_fn
        self._last_called: float = -float("inf")
        self._pending_args: "list | None" = None  # None = no pending call
        self._last_result: Any = SPRY_UNDEFINED

    def _invoke(self, args: list) -> Any:
        if callable(self._fn):
            return self._fn(*args)
        if self._call_fn is not None:
            return self._call_fn(self._fn, args)
        return SPRY_UNDEFINED

    def __call__(self, *args: Any) -> Any:
        import time as _time
        now = _time.time() * 1000
        self._pending_args = list(args)
        self._last_called = now
        return SPRY_UNDEFINED  # synchronous: result not yet available

    def flush(self) -> Any:
        """Force immediate execution of the pending call."""
        if self._pending_args is not None:
            self._last_result = self._invoke(self._pending_args)
            self._pending_args = None
        return self._last_result

    def cancel(self) -> None:
        """Cancel the pending debounced call."""
        self._pending_args = None

    def _spry_get_prop(self, prop: str) -> Any:
        _m: dict = {"flush": self.flush, "cancel": self.cancel}
        if prop in _m:
            return _m[prop]
        raise SpryRuntimeError(f"debounce has no property {prop!r}", None)

    def __repr__(self) -> str:
        return f"debounce(fn, {self._delay_ms}ms)"
