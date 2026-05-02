"""
SpryCode Interpreter

Tree-walking interpreter for SpryCode AST nodes.
"""

from __future__ import annotations

import json
import math
import os
import time
from decimal import Decimal
from typing import Any

_SENTINEL = object()  # Used as a default "not provided" sentinel

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
    BoolLiteral,
    BreakStatement,
    CallExpression,
    ClassDeclaration,
    CompensateStatement,
    CompoundAssignment,
    CompoundMemberAssignment,
    CompressStatement,
    ConnectorDeclaration,
    ContinueStatement,
    CopyStatement,
    CreateStatement,
    DeleteStatement,
    DenyStatement,
    EnumDeclaration,
    ExpectStatement,
    ExtractStatement,
    ForStatement,
    FraudCheckStatement,
    FStringExpression,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    ImportStatement,
    IndexAssignment,
    InExpression,
    IndexExpression,
    InterfaceDeclaration,
    LambdaExpression,
    LetDeclaration,
    ListDestructure,
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
    ParseStatement,
    PipelineExpression,
    PrivateDataDeclaration,
    Program,
    ReadStatement,
    RedactStatement,
    RepeatUntilStatement,
    ReturnStatement,
    ScheduleStatement,
    SecretLiteral,
    SensitiveDataDeclaration,
    SleepStatement,
    SpreadElement,
    StopStatement,
    StreamStatement,
    StringLiteral,
    StructDeclaration,
    SyncStatement,
    TaskDeclaration,
    TernaryExpression,
    TestBlock,
    ThrowStatement,
    TransactionStatement,
    TryCatchStatement,
    UnaryExpression,
    UseStatement,
    ValidateStatement,
    VarDeclaration,
    WatchStatement,
    WhileStatement,
    WriteStatement,
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


class ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class StopSignal(Exception):
    pass


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


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
    ) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.defaults: dict = defaults or {}
        self.rest_param: str | None = rest_param

    def __repr__(self) -> str:
        return f"<fn {self.name}>"


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
        self.operation: str | None = None  # used by pipeline stages

    def __repr__(self) -> str:
        return f"<lambda {self.param}>"


class SpryMultiLambda:
    """An anonymous multi-param lambda with a captured closure environment."""

    def __init__(self, params: list[str], body: Any, closure: Environment) -> None:
        self.params = params
        self.body = body
        self.closure = closure
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

    def __repr__(self) -> str:
        return f"<class {self.name}>"


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
        self._app_name: str = ""
        self._app_version: str = ""

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
        env.define("math", _MathHelper())

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

        # Constants
        env.define("ok", SPRY_OK)
        env.define("true", True)
        env.define("false", False)
        env.define("null", None)

        # Environment and formatting
        env.define("env", lambda key, default=None: os.environ.get(str(key), default))
        env.define("format", lambda template, *args: self._builtin_format(template, *args))

        # Money helper
        env.define("money", _MoneyHelper())

        # HTTP helper
        env.define("http", _HttpHelper(self.permissions))

        # SQL adapter
        env.define("sql", self._sql)

        # Audit logger
        env.define("audit", self.audit)

        return env

    def _eval_fstring(self, template: str, env: "Environment") -> str:
        """Evaluate an f-string template by substituting {expr} with evaluated values."""
        import re
        result = ""
        last = 0
        for m in re.finditer(r"\{([^}]+)\}", template):
            result += template[last:m.start()]
            expr_src = m.group(1)
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
            last = m.end()
        result += template[last:]
        return result

    @staticmethod
    def _builtin_str(value: Any) -> str:
        """Convert any SpryCode value to a string."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
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

    @staticmethod
    def _builtin_format(template: str, *args: Any) -> str:
        """Simple positional string formatting: format("Hello {}", name)"""
        try:
            return template.format(*args)
        except (IndexError, KeyError, ValueError):
            return template

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
        for stmt in block.body:
            result = self._exec(stmt, env)
        return result

    def _exec(self, node: Node, env: Environment) -> Any:  # noqa: C901
        if isinstance(node, Program):
            return self._exec_block_stmts(node.body, env)

        if isinstance(node, AppDeclaration):
            self._app_name = node.name
            self._app_version = node.version
            return None

        if isinstance(node, LetDeclaration):
            value = self._eval(node.value, env) if node.value is not None else None
            env.define(node.name, value, mutable=False)
            return None

        if isinstance(node, VarDeclaration):
            value = self._eval(node.value, env) if node.value is not None else None
            env.define(node.name, value, mutable=True)
            return None

        if isinstance(node, Assignment):
            value = self._eval(node.value, env) if node.value is not None else None
            env.set(node.name, value)
            return None

        if isinstance(node, MemberAssignment):
            obj = self._eval(node.object, env)
            value = self._eval(node.value, env)
            if isinstance(obj, SpryInstance):
                obj.set(node.property, value)
            elif isinstance(obj, dict):
                obj[node.property] = value
            else:
                raise SpryRuntimeError(
                    f"Cannot assign property {node.property!r} on {type(obj).__name__}", node
                )
            return None

        if isinstance(node, CompoundMemberAssignment):
            obj = self._eval(node.object, env)
            rhs = self._eval(node.value, env)
            if isinstance(obj, SpryInstance):
                current = obj.fields.get(node.property)
            elif isinstance(obj, dict):
                current = obj.get(node.property)
            else:
                raise SpryRuntimeError(
                    f"Cannot compound-assign property {node.property!r} on {type(obj).__name__}", node
                )
            if node.op == "+":
                new_val = current + rhs
            elif node.op == "-":
                new_val = current - rhs
            elif node.op == "*":
                new_val = current * rhs
            elif node.op == "/":
                if rhs == 0:
                    raise SpryRuntimeError("Division by zero", node)
                new_val = current / rhs
            else:
                raise SpryRuntimeError(f"Unknown compound operator: {node.op!r}", node)
            if isinstance(obj, SpryInstance):
                obj.set(node.property, new_val)
            else:
                obj[node.property] = new_val
            return None

        if isinstance(node, IndexAssignment):
            obj = self._eval(node.object, env)
            idx = self._eval(node.index, env)
            value = self._eval(node.value, env)
            try:
                obj[idx] = value
            except (TypeError, KeyError, IndexError) as e:
                raise SpryRuntimeError(f"Index assignment error: {e}", node)
            return None

        if isinstance(node, CompoundAssignment):
            current = env.get(node.name)
            rhs = self._eval(node.value, env)
            if node.op == "+":
                new_val = current + rhs
            elif node.op == "-":
                new_val = current - rhs
            elif node.op == "*":
                new_val = current * rhs
            elif node.op == "/":
                if rhs == 0:
                    raise SpryRuntimeError("Division by zero", node)
                new_val = current / rhs
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
            try:
                child = env.child()
                return self._exec_block(node.body, child)
            except SpryUserError as ue:
                child = env.child()
                # Bind the raw thrown value directly; dicts get their message field added
                err_val = ue.value
                if isinstance(err_val, dict) and "message" not in err_val:
                    err_val = {**err_val, "message": ue.message}
                child.define(node.error_name, err_val, mutable=False)
                return self._exec_block(node.handler, child)
            except (SpryRuntimeError, Exception) as e:
                child = env.child()
                result = SpryResult(ok=False, error=str(e))
                child.define(node.error_name, result, mutable=False)
                return self._exec_block(node.handler, child)

        if isinstance(node, AtomicStatement):
            return self._exec_atomic(node, env)

        if isinstance(node, TransactionStatement):
            return self._exec_transaction(node, env)

        if isinstance(node, CompensateStatement):
            # Compensate blocks are handled by the transaction executor
            return None

        if isinstance(node, ForStatement):
            return self._exec_for(node, env)

        if isinstance(node, WhileStatement):
            return self._exec_while(node, env)

        if isinstance(node, BreakStatement):
            raise BreakSignal()

        if isinstance(node, ContinueStatement):
            raise ContinueSignal()

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

        if isinstance(node, RepeatUntilStatement):
            return self._exec_repeat_until(node, env)

        if isinstance(node, AssertStatement):
            return self._exec_assert(node, env)

        if isinstance(node, ImportStatement):
            return self._exec_import(node, env)

        if isinstance(node, ThrowStatement):
            value = self._eval(node.value, env)
            raise SpryUserError(value)

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

        if isinstance(node, ObjectDestructure):
            return self._exec_object_destructure(node, env)

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

        if isinstance(node, ObjectLiteral):
            result: dict[str, Any] = {}
            # If entries list is populated (spread present), use it
            if node.entries:
                for key_or_none, val_node in node.entries:
                    if key_or_none is None:
                        # Spread element
                        spread_val = self._eval(val_node.expr, env)  # type: ignore[union-attr]
                        if isinstance(spread_val, dict):
                            result.update(spread_val)
                        else:
                            raise SpryRuntimeError("Object spread requires an object", node)
                    else:
                        result[key_or_none] = self._eval(val_node, env)
            else:
                for k, v in node.pairs.items():
                    result[k] = self._eval(v, env)
            return result

        if isinstance(node, ArrayLiteral):
            result_list: list[Any] = []
            for item in node.items:
                if isinstance(item, SpreadElement):
                    spread_val = self._eval(item.expr, env)
                    if isinstance(spread_val, (list, tuple)):
                        result_list.extend(spread_val)
                    else:
                        raise SpryRuntimeError("Spread operator requires a list", item)
                else:
                    result_list.append(self._eval(item, env))
            return result_list

        if isinstance(node, BinaryExpression):
            return self._eval_binary(node, env)

        if isinstance(node, UnaryExpression):
            return self._eval_unary(node, env)

        if isinstance(node, CallExpression):
            return self._eval_call(node, env)

        if isinstance(node, MemberExpression):
            return self._eval_member(node, env)

        if isinstance(node, OptionalMemberExpression):
            obj = self._eval(node.object, env)
            if obj is None:
                return None
            return self._eval_member_on(obj, node.property, node)

        if isinstance(node, IndexExpression):
            obj = self._eval(node.object, env)
            idx = self._eval(node.index, env)
            try:
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
            if left_val is not None:
                return left_val
            return self._eval(node.right, env)

        if isinstance(node, InExpression):
            item_val = self._eval(node.item, env)
            coll_val = self._eval(node.collection, env)
            if isinstance(coll_val, (list, tuple)):
                return item_val in coll_val
            if isinstance(coll_val, dict):
                return item_val in coll_val
            if isinstance(coll_val, str):
                return str(item_val) in coll_val
            raise SpryRuntimeError(f"'in' requires a list, object, or string, got {type(coll_val).__name__}", node)

        if isinstance(node, FStringExpression):
            return self._eval_fstring(node.raw_template, env)

        if isinstance(node, PipelineExpression):
            return self._eval_pipeline(node, env)

        if isinstance(node, ParseStatement):
            data = self._eval(node.data, env)
            return self._parse(node.format, str(data))

        if isinstance(node, ReadStatement):
            return self._exec_read(node, env)

        if isinstance(node, WriteStatement):
            return self._exec_write(node, env)

        # Fall through — try executing as a statement
        return self._exec(node, env)

    def _eval_binary(self, node: BinaryExpression, env: Environment) -> Any:
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)
        op = node.op

        if op == "+":
            if isinstance(left, (SpryMoney,)) and isinstance(right, (SpryMoney,)):
                return left + right
            return left + right
        if op == "-":
            if isinstance(left, SpryMoney) and isinstance(right, SpryMoney):
                return left - right
            return left - right
        if op == "*":
            if isinstance(left, SpryMoney):
                return left * right
            return left * right
        if op == "/":
            if right == 0:
                raise SpryRuntimeError("Division by zero", node)
            return left / right
        if op == "%":
            return left % right
        if op == "**":
            return left ** right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        if op == "&&":
            return self._truthy(left) and self._truthy(right)
        if op == "||":
            return self._truthy(left) or self._truthy(right)
        raise SpryRuntimeError(f"Unknown operator: {op!r}", node)

    def _eval_unary(self, node: UnaryExpression, env: Environment) -> Any:
        operand = self._eval(node.operand, env)
        if node.op in ("!", "not"):
            return not self._truthy(operand)
        if node.op == "-":
            return -operand
        raise SpryRuntimeError(f"Unknown unary operator: {node.op!r}", node)

    def _eval_call(self, node: CallExpression, env: Environment) -> Any:
        callee = self._eval(node.callee, env)
        # Evaluate args, expanding any SpreadElements
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
        # Wrap any lambda/function args so Python-level closures (e.g. list.map) can call them
        py_args = [self._to_py_callable(a, env) for a in args]

        if isinstance(callee, SpryClass):
            return self._construct_class(callee, args, node)

        if isinstance(callee, SpryStruct):
            return callee.create(args)

        if callable(callee) and not isinstance(callee, (SpryFunction, SpryTask)):
            try:
                return callee(*py_args)
            except Exception as e:
                raise SpryRuntimeError(str(e), node)

        if isinstance(callee, BoundMethod):
            return self._call_bound_method(callee, args, node)

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
        # fn.params contains positional params (rest_param is stored separately, never in fn.params)
        # Count required params: those with no default value and not dict-destructured
        required = [
            p for p, _ in fn.params
            if p not in fn.defaults and not p.startswith("__destruct__")
        ]
        total_positional = len(fn.params)

        if len(args) < len(required):
            raise SpryRuntimeError(
                f"Function {fn.name!r} expects at least {len(required)} args, got {len(args)}", node
            )
        if fn.rest_param is None and len(args) > total_positional:
            raise SpryRuntimeError(
                f"Function {fn.name!r} expects at most {total_positional} args, got {len(args)}", node
            )

        child = fn.closure.child()

        for i, (pname, _ptype) in enumerate(fn.params):
            # Dict destructuring param: __destruct__:a,b
            if pname.startswith("__destruct__:"):
                field_names = pname[len("__destruct__:"):].split(",")
                arg_val = args[i] if i < len(args) else {}
                if not isinstance(arg_val, dict):
                    raise SpryRuntimeError(
                        f"Function {fn.name!r} expects an object for destructured param, got {type(arg_val).__name__}", node
                    )
                for fname in field_names:
                    child.define(fname.strip(), arg_val.get(fname.strip()), mutable=False)
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
            return r.value
        return None

    def _call_task(self, task: SpryTask) -> Any:
        child = task.closure.child()
        try:
            return self._exec_block(task.body, child)
        except ReturnSignal as r:
            return r.value
        except StopSignal:
            return None

    def _eval_member(self, node: MemberExpression, env: Environment) -> Any:
        obj = self._eval(node.object, env)
        prop = node.property

        if obj is None:
            raise SpryRuntimeError(f"Cannot access property {prop!r} on null", node)

        return self._eval_member_on(obj, prop, node)

    def _eval_member_on(self, obj: Any, prop: str, node: Node) -> Any:
        """Look up `prop` on `obj`. Used by both MemberExpression and OptionalMemberExpression."""

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
            # Instance field or method lookup
            if prop in obj.fields:
                v = obj.fields[prop]
                if isinstance(v, SpryFunction):
                    # Bind self to method
                    return BoundMethod(instance=obj, fn=v)
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
            if prop in obj:
                return obj[prop]
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
            raise SpryRuntimeError(f"Key {prop!r} not found in object", node)

        if isinstance(obj, list):
            if prop == "length":
                return len(obj)
            if prop == "first":
                return obj[0] if obj else None
            if prop == "last":
                return obj[-1] if obj else None
            if prop == "isEmpty":
                return len(obj) == 0
            if prop == "push":
                return lambda item: obj.append(item)
            if prop == "pop":
                return lambda: obj.pop() if obj else None
            if prop == "includes":
                return lambda item: item in obj
            if prop == "join":
                return lambda sep="": sep.join(str(i) for i in obj)
            if prop == "slice":
                return lambda start, end=None: obj[start:end]
            if prop == "reverse":
                return list(reversed(obj))
            if prop == "sort":
                return sorted(obj)
            if prop == "sorted":
                return sorted(obj)
            if prop == "indexOf":
                return lambda item: obj.index(item) if item in obj else -1
            if prop == "find":
                return lambda pred: next((x for x in obj if self._truthy(pred(x))), None)
            if prop == "filter":
                return lambda pred: [x for x in obj if self._truthy(pred(x))]
            if prop == "map":
                return lambda fn: [fn(x) for x in obj]
            if prop in ("every", "all"):
                return lambda pred: all(self._truthy(pred(x)) for x in obj)
            if prop in ("some", "any"):
                return lambda pred: any(self._truthy(pred(x)) for x in obj)
            if prop == "reduce":
                def _list_reduce(first_arg: Any, second_arg: Any = _SENTINEL) -> Any:
                    # Support both:
                    #   reduce(fn)        — no init, use first element as seed
                    #   reduce(fn, init)  — fn first, init second (JS/SpryCode convention)
                    #   reduce(init, fn)  — init first, fn second (legacy convention)
                    if second_arg is _SENTINEL:
                        # Single arg must be the function
                        _fn = first_arg
                        if not obj:
                            return None
                        acc = obj[0]
                        for _item in obj[1:]:
                            acc = _fn(acc, _item)
                        return acc
                    # Two args: detect which is fn by callability
                    if callable(first_arg) and not callable(second_arg):
                        # reduce(fn, init) — fn first
                        _fn2 = first_arg
                        acc = second_arg
                    elif callable(second_arg) and not callable(first_arg):
                        # reduce(init, fn) — init first (legacy)
                        _fn2 = second_arg
                        acc = first_arg
                    else:
                        # Both callable: assume (fn, init) convention
                        _fn2 = first_arg
                        acc = second_arg
                    for _item in obj:
                        acc = _fn2(acc, _item)
                    return acc
                return _list_reduce
            if prop == "findIndex":
                return lambda pred: next((i for i, x in enumerate(obj) if self._truthy(pred(x))), -1)
            if prop == "concat":
                return lambda other: obj + (other if isinstance(other, list) else [other])
            if prop == "unshift":
                def _list_unshift(item: Any) -> int:
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
            if prop == "zip":
                return lambda other: [[a, b] for a, b in zip(obj, other)]
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
            if prop == "flat":
                return [x for sublist in obj for x in (sublist if isinstance(sublist, list) else [sublist])]
            if prop == "sum":
                return sum(obj)
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
            if prop == "split":
                return lambda sep=" ": obj.split(sep)
            if prop == "contains":
                return lambda sub: sub in obj
            if prop == "includes":
                return lambda sub: sub in obj
            if prop == "startsWith":
                return lambda prefix: obj.startswith(prefix)
            if prop == "endsWith":
                return lambda suffix: obj.endswith(suffix)
            if prop == "replace":
                return lambda old, new: obj.replace(old, new)
            if prop == "replaceAll":
                return lambda old, new: obj.replace(old, new)
            if prop == "slice":
                return lambda start, end=None: obj[start:end]
            if prop == "isEmpty":
                return len(obj) == 0
            if prop == "isNotEmpty":
                return len(obj) > 0
            if prop == "indexOf":
                return lambda sub: obj.find(sub)
            if prop == "lastIndexOf":
                return lambda sub: obj.rfind(sub)
            if prop == "at":
                return lambda n: obj[int(n)] if -len(obj) <= int(n) < len(obj) else None
            if prop == "charAt":
                return lambda n: obj[int(n)] if 0 <= int(n) < len(obj) else ""
            if prop in ("padStart", "padLeft"):
                return lambda width, ch=" ": obj.rjust(width, ch)
            if prop in ("padEnd", "padRight"):
                return lambda width, ch=" ": obj.ljust(width, ch)
            if prop == "repeat":
                return lambda n: obj * n
            if prop == "chars":
                return list(obj)
            if prop == "lines":
                return obj.splitlines()
            if prop in ("substring", "substr"):
                return lambda start, end=None: obj[int(start):int(end)] if end is not None else obj[int(start):]
            if prop == "match":
                import re as _re
                return lambda pattern: _re.findall(pattern, obj) or None
            if prop == "matchAll":
                import re as _re
                return lambda pattern: [[m.group(), *m.groups()] for m in _re.finditer(pattern, obj)]
            if prop == "search":
                import re as _re
                return lambda pattern: (m.start() if (m := _re.search(pattern, obj)) else -1)
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

        if isinstance(obj, (int, float)):
            if prop in ("toFixed", "toFixed"):
                return lambda digits=2: f"{obj:.{digits}f}"
            if prop in ("toStr", "toString"):
                return str(int(obj)) if isinstance(obj, float) and obj == int(obj) else str(obj)
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

            # Single-param lambda stages (filter, map, each)
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
                else:  # "map"
                    if isinstance(value, list):
                        value = [self._apply_lambda(stage, item, env) for item in value]
                    else:
                        value = self._apply_lambda(stage, value, env)
                continue

            if isinstance(stage, Identifier):
                # Named function/operation call
                fn = env.get(stage.name)
                if isinstance(fn, SpryFunction):
                    value = self._call_function(fn, [value], stage)
                elif isinstance(fn, (SpryLambda, LambdaExpression)):
                    value = self._apply_lambda(fn, value, env)
                elif callable(fn):
                    value = fn(value)
                else:
                    raise SpryRuntimeError(f"Cannot use {stage.name!r} as pipeline stage", stage)
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
            return self._eval(lam.body, child)
        # Fallback for raw LambdaExpression nodes (pipeline stages)
        child = env.child()
        child.define(lam.param, item, mutable=False)
        return self._eval(lam.body, child)

    def _apply_multi_lambda(self, lam: "MultiParamLambda | SpryMultiLambda", args: list[Any], env: Environment) -> Any:
        if isinstance(lam, SpryMultiLambda):
            child = lam.closure.child()
        else:
            child = env.child()
        for i, param in enumerate(lam.params):
            child.define(param, args[i] if i < len(args) else None, mutable=False)
        return self._eval(lam.body, child)

    def _to_py_callable(self, fn: Any, env: Environment) -> Any:
        """Wrap a SpryCode callable as a Python callable for use in method closures."""
        if isinstance(fn, SpryLambda):
            return lambda *args: self._apply_lambda(fn, args[0] if args else None, env)
        if isinstance(fn, SpryMultiLambda):
            return lambda *args: self._apply_multi_lambda(fn, list(args), env)
        if isinstance(fn, LambdaExpression):
            return lambda *args: self._apply_lambda(fn, args[0] if args else None, env)
        if isinstance(fn, MultiParamLambda):
            return lambda *args: self._apply_multi_lambda(fn, list(args), env)
        if isinstance(fn, SpryFunction):
            return lambda *args: self._call_function(fn, list(args), fn)
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

    def _exec_for(self, node: ForStatement, env: Environment) -> Any:
        # Range shorthand: for i in start..end (BinaryExpression with op="..")
        if isinstance(node.iterable, BinaryExpression) and node.iterable.op == "..":
            start = int(self._eval(node.iterable.left, env))
            end = int(self._eval(node.iterable.right, env))
            iterable: Any = range(start, end)
        else:
            iterable = self._eval(node.iterable, env)

        # Allow iterating over dict keys
        if isinstance(iterable, dict):
            iterable = list(iterable.keys())
        if not isinstance(iterable, (list, tuple, str, range)):
            raise SpryRuntimeError(
                f"'for' loop requires a list or object, got {type(iterable).__name__}", node
            )

        # Destructured loop: for i, v in enumerate(list)
        multi_vars = node.vars if node.vars else [node.var]
        destructured = len(multi_vars) > 1

        for item in iterable:
            child = env.child()
            if destructured:
                # item should be a list/tuple: [index, value]
                if isinstance(item, (list, tuple)):
                    for idx, vname in enumerate(multi_vars):
                        child.define(vname, item[idx] if idx < len(item) else None, mutable=False)
                else:
                    # fallback: bind first var to item
                    child.define(multi_vars[0], item, mutable=False)
            else:
                child.define(node.var, item, mutable=False)
            try:
                self._exec_block(node.body, child)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return None

    def _exec_while(self, node: WhileStatement, env: Environment) -> Any:
        max_iterations = 100_000  # safety limit
        count = 0
        while self._truthy(self._eval(node.condition, env)):
            child = env.child()
            try:
                self._exec_block(node.body, child)
            except BreakSignal:
                break
            except ContinueSignal:
                pass
            count += 1
            if count >= max_iterations:
                raise SpryRuntimeError("While loop exceeded maximum iteration limit (100,000)", node)
        return None

    def _exec_repeat_until(self, node: RepeatUntilStatement, env: Environment) -> Any:
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
                child = env.child()
                return self._exec_block(arm.body, child)
            pattern_val = self._eval(arm.pattern, env)
            if arm.range_end is not None:
                # Range arm: pattern_val..range_end_val (inclusive)
                range_end_val = self._eval(arm.range_end, env)
                try:
                    if pattern_val <= subject_val <= range_end_val:
                        child = env.child()
                        return self._exec_block(arm.body, child)
                except TypeError:
                    pass
            elif subject_val == pattern_val:
                child = env.child()
                return self._exec_block(arm.body, child)
        return None

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
        val = self._eval(node.value, env)
        if not isinstance(val, (list, tuple)):
            raise SpryRuntimeError(
                f"List destructuring requires a list, got {type(val).__name__}", node
            )
        for i, name in enumerate(node.names):
            item = val[i] if i < len(val) else None
            env.define(name, item, mutable=node.mutable)
        if node.rest_name is not None:
            rest = list(val[len(node.names):])
            env.define(node.rest_name, rest, mutable=node.mutable)
        return None

    def _exec_object_destructure(self, node: ObjectDestructure, env: Environment) -> Any:
        val = self._eval(node.value, env)
        if not isinstance(val, dict):
            raise SpryRuntimeError(
                f"Object destructuring requires an object, got {type(val).__name__}", node
            )
        for name in node.names:
            alias = node.aliases.get(name, name)
            item = val.get(name)
            env.define(alias, item, mutable=node.mutable)
        return None

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
        if node.superclass is not None:
            try:
                sc = env.get(node.superclass)
                if isinstance(sc, SpryClass):
                    superclass = sc
            except SpryRuntimeError:
                pass
        cls = SpryClass(name=node.name, body=node.body, closure=env, superclass=superclass)
        env.define(node.name, cls, mutable=False)
        return None

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

        # Execute the class body to pick up var/fn declarations (subclass overrides superclass)
        for stmt in cls.body.body:  # type: ignore[union-attr]
            if isinstance(stmt, VarDeclaration):
                val = self._eval(stmt.value, instance_env) if stmt.value is not None else None
                fields[stmt.name] = val
                instance_env.define(stmt.name, val, mutable=True)
            elif isinstance(stmt, FunctionDeclaration):
                fn = SpryFunction(
                    name=stmt.name,
                    params=stmt.params,
                    body=stmt.body,  # type: ignore
                    closure=instance_env,
                    defaults=stmt.defaults,
                    rest_param=stmt.rest_param,
                )
                fields[stmt.name] = fn
                instance_env.define(stmt.name, fn, mutable=False)
            elif isinstance(stmt, LetDeclaration):
                val = self._eval(stmt.value, instance_env) if stmt.value is not None else None
                fields[stmt.name] = val
                instance_env.define(stmt.name, val, mutable=False)

        instance = SpryInstance(cls=cls, fields=fields)

        # Bind "self" so methods can use it
        instance_env.define("self", instance, mutable=False)

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
                )
                fields[fname] = new_fn
                instance.fields[fname] = new_fn

        # Call init() if defined (skip when building inheritance field structure)
        if not _for_inheritance:
            if "init" in fields and isinstance(fields["init"], SpryFunction):
                self._call_bound_method(BoundMethod(instance=instance, fn=fields["init"]), args, node)
            elif args:
                # Positional-field constructor: Counter(10) → counter.count = 10
                field_vars = [k for k, v in fields.items() if not callable(v) and not isinstance(v, SpryFunction)]
                for i, arg in enumerate(args):
                    if i < len(field_vars):
                        instance.set(field_vars[i], arg)

        return instance

    def _call_bound_method(self, bm: BoundMethod, args: list[Any], node: Node) -> Any:
        """Call a method on an instance, binding `self` in the execution environment."""
        fn = bm.fn
        child = fn.closure.child()
        # Bind self so methods can do self.field = val
        child.define("self", bm.instance, mutable=False)
        # Also expose instance fields as direct mutable vars (for count += 1 style),
        # recording their initial values so we can sync back only what changed directly.
        initial_field_values: dict[str, Any] = {}
        for fname, fval in bm.instance.fields.items():
            if not child.has(fname):
                child.define(fname, fval, mutable=True)
                initial_field_values[fname] = fval

        required = [
            p for p, _ in fn.params
            if p not in fn.defaults and not p.startswith("__destruct__")
        ]
        if len(args) < len(required):
            raise SpryRuntimeError(
                f"Method {fn.name!r} expects at least {len(required)} args, got {len(args)}", node
            )

        for i, (pname, _ptype) in enumerate(fn.params):
            if pname.startswith("__destruct__:"):
                field_names = pname[len("__destruct__:"):].split(",")
                arg_val = args[i] if i < len(args) else {}
                if not isinstance(arg_val, dict):
                    raise SpryRuntimeError(
                        f"Method {fn.name!r} expects an object for destructured param, got {type(arg_val).__name__}", node
                    )
                for fname in field_names:
                    child.define(fname.strip(), arg_val.get(fname.strip()), mutable=False)
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
        for fname, initial in initial_field_values.items():
            try:
                child_val = child.get(fname)
            except SpryRuntimeError:
                continue
            if child_val != initial:
                bm.instance.fields[fname] = child_val

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

    # ── min / max ─────────────────────────────────────────────────────────────

    def min(self, *args: Any) -> Any:
        if len(args) == 1:
            # Single argument must be a numeric iterable (e.g. a list of numbers)
            if not hasattr(args[0], "__iter__") or isinstance(args[0], str):
                raise TypeError(f"math.min() requires at least 2 arguments or a numeric iterable, got {type(args[0]).__name__}")
            return min(args[0])
        return min(*args)

    def max(self, *args: Any) -> Any:
        if len(args) == 1:
            if not hasattr(args[0], "__iter__") or isinstance(args[0], str):
                raise TypeError(f"math.max() requires at least 2 arguments or a numeric iterable, got {type(args[0]).__name__}")
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

    def stringify(self, value: Any, indent: int | None = None) -> str:
        import json
        try:
            return json.dumps(value, indent=indent, default=str)
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
