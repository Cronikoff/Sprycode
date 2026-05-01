"""
SpryCode Interpreter

Tree-walking interpreter for SpryCode AST nodes.
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any

from .ast_nodes import (
    AdapterDeclaration,
    AllowStatement,
    AppDeclaration,
    ArrayLiteral,
    Assignment,
    AtomicStatement,
    BinaryExpression,
    Block,
    BoolLiteral,
    CallExpression,
    CompensateStatement,
    ConnectorDeclaration,
    CopyStatement,
    DeleteStatement,
    DenyStatement,
    FraudCheckStatement,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    IndexExpression,
    LambdaExpression,
    LetDeclaration,
    LogStatement,
    MemberExpression,
    MoveStatement,
    Node,
    NullLiteral,
    NumberLiteral,
    ObjectLiteral,
    ParseStatement,
    PipelineExpression,
    PrivateDataDeclaration,
    Program,
    ReadStatement,
    RedactStatement,
    ReturnStatement,
    SecretLiteral,
    SensitiveDataDeclaration,
    StopStatement,
    StreamStatement,
    StringLiteral,
    SyncStatement,
    TaskDeclaration,
    TransactionStatement,
    TryCatchStatement,
    UnaryExpression,
    UseStatement,
    ValidateStatement,
    VarDeclaration,
    WatchStatement,
    WriteStatement,
)
from .permissions import PermissionSet
from .runtime.stdlib import (
    SPRY_OK,
    FilesystemOps,
    SecretManager,
    SpryFile,
    SpryFolder,
    SpryLogger,
    SpryMoney,
    SpryResult,
    SprySecret,
    _builtin_checksum,
    _builtin_decode_base64,
    _builtin_encode_base64,
    _builtin_encode_json,
    _builtin_hash_text,
    _builtin_now,
    _builtin_parse_csv,
    _builtin_parse_json,
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
    ) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure

    def __repr__(self) -> str:
        return f"<fn {self.name}>"


class SpryTask:
    def __init__(self, name: str, body: "Block", closure: Environment) -> None:
        self.name = name
        self.body = body
        self.closure = closure

    def __repr__(self) -> str:
        return f"<task {self.name}>"


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
    ) -> None:
        self.logger = logger or SpryLogger()
        self.permissions = permissions or PermissionSet()
        self.secrets = secret_manager or SecretManager()
        self.fs = FilesystemOps(self.permissions)
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
        env.define("encode", lambda fmt, val: self._encode(fmt, val))
        env.define("decode", lambda fmt, val: self._decode(fmt, val))
        env.define("parse", lambda fmt, val: self._parse(fmt, val))

        # Math
        env.define("abs", abs)
        env.define("min", min)
        env.define("max", max)
        env.define("round", round)
        env.define("len", len)
        env.define("str", str)
        env.define("int", int)
        env.define("float", float)

        # Constants
        env.define("ok", SPRY_OK)
        env.define("true", True)
        env.define("false", False)
        env.define("null", None)

        # Money helper
        env.define("money", _MoneyHelper())

        # HTTP helper (stub)
        env.define("http", _HttpHelper(self.permissions))

        return env

    def _encode(self, fmt: str, val: Any) -> Any:
        if fmt in ("json",):
            return _builtin_encode_json(val)
        if fmt in ("base64",):
            return _builtin_encode_base64(str(val))
        return str(val)

    def _decode(self, fmt: str, val: str) -> Any:
        if fmt in ("base64",):
            return _builtin_decode_base64(val)
        return val

    def _parse(self, fmt: str, val: str) -> Any:
        if fmt in ("json",):
            return _builtin_parse_json(val)
        if fmt in ("csv",):
            return _builtin_parse_csv(val)
        return val

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, program: Program) -> Any:
        """Execute a full program."""
        return self._exec_block_stmts(program.body, self.globals)

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
                # Only register declarations (tasks, functions, connectors)
                if isinstance(stmt, (TaskDeclaration, FunctionDeclaration, ConnectorDeclaration)):
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

        if isinstance(node, FunctionDeclaration):
            fn = SpryFunction(
                name=node.name,
                params=node.params,
                body=node.body,  # type: ignore
                closure=env,
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

        if isinstance(node, ReturnStatement):
            value = self._eval(node.value, env) if node.value is not None else None
            raise ReturnSignal(value)

        if isinstance(node, StopStatement):
            raise StopSignal()

        if isinstance(node, LogStatement):
            msg = self._eval(node.message, env)
            level = node.level.lower()
            if level == "info":
                self.logger.info(msg)
            elif level in ("warn", "warning"):
                self.logger.warn(msg)
            elif level == "error":
                self.logger.error(msg)
            else:
                self.logger.info(msg)
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
            # Adapter loading — log but don't fail
            self.logger.info(f"Adapter '{node.name}' registered")
            return None

        if isinstance(node, AdapterDeclaration):
            return None

        if isinstance(node, ConnectorDeclaration):
            env.define(node.name, {"name": node.name, "type": "connector"}, mutable=False)
            return None

        if isinstance(node, FraudCheckStatement):
            return self._exec_fraud_check(node, env)

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
            for k, v in node.pairs.items():
                result[k] = self._eval(v, env)
            return result

        if isinstance(node, ArrayLiteral):
            return [self._eval(item, env) for item in node.items]

        if isinstance(node, BinaryExpression):
            return self._eval_binary(node, env)

        if isinstance(node, UnaryExpression):
            return self._eval_unary(node, env)

        if isinstance(node, CallExpression):
            return self._eval_call(node, env)

        if isinstance(node, MemberExpression):
            return self._eval_member(node, env)

        if isinstance(node, IndexExpression):
            obj = self._eval(node.object, env)
            idx = self._eval(node.index, env)
            try:
                return obj[idx]
            except (KeyError, IndexError, TypeError) as e:
                raise SpryRuntimeError(f"Index error: {e}", node)

        if isinstance(node, LambdaExpression):
            return node  # Lambda is evaluated lazily

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
        args = [self._eval(a, env) for a in node.args]

        if callable(callee) and not isinstance(callee, (SpryFunction, SpryTask)):
            try:
                return callee(*args)
            except Exception as e:
                raise SpryRuntimeError(str(e), node)

        if isinstance(callee, SpryFunction):
            return self._call_function(callee, args, node)

        if isinstance(callee, SpryTask):
            return self._call_task(callee)

        raise SpryRuntimeError(
            f"Cannot call {type(callee).__name__} (value: {callee!r})", node
        )

    def _call_function(self, fn: SpryFunction, args: list[Any], node: Node) -> Any:
        if len(args) != len(fn.params):
            raise SpryRuntimeError(
                f"Function {fn.name!r} expects {len(fn.params)} args, got {len(args)}", node
            )
        child = fn.closure.child()
        for (pname, _ptype), arg in zip(fn.params, args):
            child.define(pname, arg, mutable=False)
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

        if isinstance(obj, SpryResult):
            if prop == "ok":
                return obj.ok
            if prop == "failed":
                return obj.failed
            if prop in ("error", "message"):
                return obj.error
            if prop == "value":
                return obj.value

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
            raise SpryRuntimeError(f"Key {prop!r} not found in object", node)

        if isinstance(obj, list):
            if prop == "length":
                return len(obj)
            if prop == "first":
                return obj[0] if obj else None
            if prop == "last":
                return obj[-1] if obj else None

        if isinstance(obj, str):
            if prop == "length":
                return len(obj)
            if prop == "upper":
                return obj.upper()
            if prop == "lower":
                return obj.lower()
            if prop == "trim":
                return obj.strip()

        # Try attribute access
        try:
            return getattr(obj, prop)
        except AttributeError:
            raise SpryRuntimeError(f"Property {prop!r} not found on {type(obj).__name__}", node)

    def _eval_pipeline(self, node: PipelineExpression, env: Environment) -> Any:
        """Evaluate a pipeline: val |> filter x => ... |> map x => ... |> write file ..."""
        value = self._eval(node.stages[0], env)

        for stage in node.stages[1:]:
            if isinstance(stage, LambdaExpression):
                # Apply lambda to each item (implicit map)
                if isinstance(value, list):
                    value = [self._apply_lambda(stage, item, env) for item in value]
                else:
                    value = self._apply_lambda(stage, value, env)

            elif isinstance(stage, Identifier):
                # Named function/operation call
                fn = env.get(stage.name)
                if isinstance(fn, SpryFunction):
                    value = self._call_function(fn, [value], stage)
                elif callable(fn):
                    value = fn(value)
                else:
                    raise SpryRuntimeError(f"Cannot use {stage.name!r} as pipeline stage", stage)

            elif isinstance(stage, ParseStatement):
                value = self._parse(stage.format, str(value))

            elif isinstance(stage, WriteStatement):
                path = self._eval(stage.path, env)
                # Write the accumulated value
                if isinstance(value, list):
                    data = "\n".join(str(item) for item in value)
                else:
                    data = str(value)
                result = self.fs.write_file(str(path), data)
                value = result

            else:
                # Try to apply as a call
                result = self._eval(stage, env)
                if callable(result):
                    value = result(value)
                elif isinstance(result, LambdaExpression):
                    value = self._apply_lambda(result, value, env)

        return value

    def _apply_lambda(self, lam: LambdaExpression, item: Any, env: Environment) -> Any:
        child = env.child()
        child.define(lam.param, item, mutable=False)
        return self._eval(lam.body, child)

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
    """Stub HTTP client."""

    def __init__(self, permissions: PermissionSet) -> None:
        self._perms = permissions

    def get(self, url: str) -> SpryResult:
        self._perms.check("network.request", url)
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return SpryResult(ok=True, value={"status": resp.status, "body": body})
        except Exception as e:
            return SpryResult(ok=False, error=str(e))

    def post(self, url: str, body: Any = None) -> SpryResult:
        self._perms.check("network.request", url)
        try:
            import json as _json
            import urllib.request
            data = _json.dumps(body).encode("utf-8") if body is not None else b""
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read().decode("utf-8")
                return SpryResult(ok=True, value={"status": resp.status, "body": resp_body})
        except Exception as e:
            return SpryResult(ok=False, error=str(e))
