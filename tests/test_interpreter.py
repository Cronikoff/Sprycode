"""
Tests for the SpryCode Interpreter.
"""

import os
import tempfile
from pathlib import Path

import pytest
from sprycode.interpreter import (
    Environment,
    Interpreter,
    SpryFunction,
    SpryRuntimeError,
)
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.permissions import PermissionSet
from sprycode.runtime.stdlib import SpryLogger, SpryResult, SprySecret


def run(source: str, permissions: PermissionSet | None = None, log_output: list | None = None) -> Interpreter:
    """Helper: parse and run SpryCode source, return the interpreter."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    log_out = log_output if log_output is not None else []
    logger = SpryLogger(output=log_out)
    perms = permissions or PermissionSet()
    interp = Interpreter(logger=logger, permissions=perms)
    interp.run(program)
    return interp


def eval_expr(source: str) -> object:
    """Helper: parse and evaluate a single expression, return its value."""
    full = f"let __result = {source}"
    interp = run(full)
    return interp.globals.get("__result")


class TestEnvironment:
    def test_define_and_get(self):
        env = Environment()
        env.define("x", 42)
        assert env.get("x") == 42

    def test_mutable_assignment(self):
        env = Environment()
        env.define("x", 1, mutable=True)
        env.set("x", 2)
        assert env.get("x") == 2

    def test_immutable_assignment_raises(self):
        env = Environment()
        env.define("x", 1, mutable=False)
        with pytest.raises(SpryRuntimeError):
            env.set("x", 2)

    def test_undefined_raises(self):
        env = Environment()
        with pytest.raises(SpryRuntimeError):
            env.get("undefined_var")

    def test_parent_scope_lookup(self):
        parent = Environment()
        parent.define("x", 10)
        child = parent.child()
        assert child.get("x") == 10

    def test_shadowing(self):
        parent = Environment()
        parent.define("x", 1)
        child = parent.child()
        child.define("x", 2)
        assert child.get("x") == 2
        assert parent.get("x") == 1


class TestVariables:
    def test_let_string(self):
        interp = run('let name = "SpryCode"')
        assert interp.globals.get("name") == "SpryCode"

    def test_let_number(self):
        interp = run("let x = 42")
        assert interp.globals.get("x") == 42

    def test_let_bool_true(self):
        interp = run("let flag = true")
        assert interp.globals.get("flag") is True

    def test_let_bool_false(self):
        interp = run("let flag = false")
        assert interp.globals.get("flag") is False

    def test_var_mutable(self):
        interp = run("var count = 0\ncount = count + 1")
        assert interp.globals.get("count") == 1

    def test_let_immutable_reassign_fails(self):
        with pytest.raises(Exception):
            run("let x = 1\nx = 2")

    def test_let_with_expression(self):
        interp = run("let sum = 3 + 4")
        assert interp.globals.get("sum") == 7


class TestArithmetic:
    def test_addition(self):
        assert eval_expr("1 + 2") == 3

    def test_subtraction(self):
        assert eval_expr("10 - 3") == 7

    def test_multiplication(self):
        assert eval_expr("4 * 5") == 20

    def test_division(self):
        assert eval_expr("10 / 2") == 5.0

    def test_modulo(self):
        assert eval_expr("10 % 3") == 1

    def test_string_concat(self):
        assert eval_expr('"Hello, " + "World"') == "Hello, World"

    def test_operator_precedence(self):
        assert eval_expr("2 + 3 * 4") == 14

    def test_parentheses(self):
        assert eval_expr("(2 + 3) * 4") == 20

    def test_division_by_zero(self):
        # JS-like: 1/0 → Infinity (not an error)
        import math
        result = eval_expr("1 / 0")
        assert math.isinf(result) and result > 0


class TestComparisons:
    def test_eq(self):
        assert eval_expr("1 == 1") is True
        assert eval_expr("1 == 2") is False

    def test_ne(self):
        assert eval_expr("1 != 2") is True

    def test_lt(self):
        assert eval_expr("1 < 2") is True
        assert eval_expr("2 < 1") is False

    def test_gt(self):
        assert eval_expr("2 > 1") is True

    def test_le(self):
        assert eval_expr("1 <= 1") is True
        assert eval_expr("2 <= 1") is False

    def test_ge(self):
        assert eval_expr("1 >= 1") is True

    def test_string_equality(self):
        assert eval_expr('"hello" == "hello"') is True
        assert eval_expr('"hello" == "world"') is False


class TestBooleanLogic:
    def test_and_true(self):
        assert eval_expr("true && true") is True

    def test_and_false(self):
        assert eval_expr("true && false") is False

    def test_or_true(self):
        assert eval_expr("false || true") is True

    def test_or_false(self):
        assert eval_expr("false || false") is False

    def test_not(self):
        assert eval_expr("!true") is False
        assert eval_expr("!false") is True


class TestFunctions:
    def test_simple_function(self):
        source = """
fn greet(name: Text) -> Text {
    return "Hello, " + name
}
let result = greet("World")
"""
        interp = run(source)
        assert interp.globals.get("result") == "Hello, World"

    def test_short_form_function(self):
        source = """
fn double(x: Number) => x * 2
let result = double(5)
"""
        interp = run(source)
        assert interp.globals.get("result") == 10

    def test_multi_param_function(self):
        source = """
fn add(a: Number, b: Number) -> Number {
    return a + b
}
let result = add(3, 4)
"""
        interp = run(source)
        assert interp.globals.get("result") == 7

    def test_function_no_return(self):
        source = """
fn noReturn() {
    let x = 1
}
let r = noReturn()
"""
        interp = run(source)
        assert interp.globals.get("r") is None

    def test_recursive_function(self):
        source = """
fn factorial(n: Number) -> Number {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}
let result = factorial(5)
"""
        interp = run(source)
        assert interp.globals.get("result") == 120


class TestTasks:
    def test_simple_task_run(self):
        log_output = []
        source = """
task hello {
    log info "Hello from SpryCode"
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        logger = SpryLogger(output=log_output)
        interp = Interpreter(logger=logger)
        interp.run_task(program, "hello")
        assert any("Hello from SpryCode" in line for line in log_output)

    def test_task_with_let(self):
        log_output = []
        source = """
task compute {
    let x = 10
    let y = 20
    let sum = x + y
    log info sum
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        logger = SpryLogger(output=log_output)
        interp = Interpreter(logger=logger)
        interp.run_task(program, "compute")
        assert any("30" in line for line in log_output)


class TestIfStatement:
    def test_if_true(self):
        interp = run("var result = 0\nif true { result = 1 }")
        assert interp.globals.get("result") == 1

    def test_if_false(self):
        interp = run("var result = 0\nif false { result = 1 }")
        assert interp.globals.get("result") == 0

    def test_if_else(self):
        interp = run("var result = 0\nif false { result = 1 } else { result = 2 }")
        assert interp.globals.get("result") == 2

    def test_if_condition(self):
        interp = run("let x = 5\nvar result = 0\nif x > 3 { result = 1 }")
        assert interp.globals.get("result") == 1

    def test_if_failed(self):
        """Test the 'result failed' pattern."""
        source = """
let val = 42
var status = "ok"
if val == 99 {
    status = "changed"
}
"""
        interp = run(source)
        assert interp.globals.get("status") == "ok"


class TestTryCatch:
    def test_catch_error(self):
        log_output = []
        source = """
var caught = false
try {
    throw "oops"
} catch err {
    caught = true
}
"""
        interp = run(source, log_output=log_output)
        assert interp.globals.get("caught") is True

    def test_try_success(self):
        source = """
var result = 0
try {
    result = 42
} catch err {
    result = -1
}
"""
        interp = run(source)
        assert interp.globals.get("result") == 42


class TestLogging:
    def test_log_info(self):
        log_output = []
        run('log info "test message"', log_output=log_output)
        assert any("[INFO]" in line and "test message" in line for line in log_output)

    def test_log_warn(self):
        log_output = []
        run('log warn "warning"', log_output=log_output)
        assert any("[WARN]" in line for line in log_output)

    def test_log_error(self):
        log_output = []
        run('log error "an error"', log_output=log_output)
        assert any("[ERROR]" in line for line in log_output)

    def test_secret_redacted_in_log(self):
        """Secrets should not appear in log output."""
        log_output = []
        perms = PermissionSet()
        perms.add_allow("secret.read", "MY_SECRET")
        source = """
allow secret.read "MY_SECRET"
let key = secret "MY_SECRET"
log info key
"""
        os.environ["MY_SECRET"] = "super-secret-value"
        try:
            run(source, permissions=perms, log_output=log_output)
        finally:
            del os.environ["MY_SECRET"]

        # The actual secret value should NOT appear in logs
        assert not any("super-secret-value" in line for line in log_output)


class TestPermissions:
    def test_permission_required_in_secure_mode(self):
        from sprycode.permissions import PermissionError
        perms = PermissionSet()
        perms.enable_secure_mode()

        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "a.txt"
            f.write_text("hello")
            source = f'read file "{f}"'
            with pytest.raises((SpryRuntimeError, PermissionError, Exception)):
                run(source, permissions=perms)

    def test_permission_grant_allows_operation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.txt"
            f.write_text("hello world")
            source = f"""
allow filesystem.read "{tmpdir}"
let result = read file "{f}"
"""
            interp = run(source)
            result = interp.globals.get("result")
            assert isinstance(result, SpryResult)
            assert result.ok
            assert result.value == "hello world"

    def test_deny_prevents_operation(self):
        from sprycode.permissions import PermissionError
        perms = PermissionSet()
        perms.add_allow("filesystem.read")  # Allow all reads
        perms.add_deny("filesystem.read", "/secret")  # But deny this one

        with pytest.raises((SpryRuntimeError, PermissionError, Exception)):
            from sprycode.runtime.stdlib import FilesystemOps
            fs = FilesystemOps(perms)
            fs.read_file("/secret/file.txt")


class TestFileOperations:
    def test_write_and_read_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = str(Path(tmpdir) / "test.txt")
            source = f"""
allow filesystem.write "{tmpdir}"
allow filesystem.read "{tmpdir}"
write file "{filepath}" with "hello"
let result = read file "{filepath}"
"""
            interp = run(source)
            result = interp.globals.get("result")
            assert isinstance(result, SpryResult)
            assert result.ok
            assert result.value == "hello"

    def test_move_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.txt"
            dst = Path(tmpdir) / "dest.txt"
            src.write_text("content")
            source = f"""
allow filesystem.read "{tmpdir}"
allow filesystem.write "{tmpdir}"
move file "{src}" to "{dst}"
"""
            run(source)
            assert not src.exists()
            assert dst.exists()
            assert dst.read_text() == "content"

    def test_copy_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.txt"
            dst = Path(tmpdir) / "copy.txt"
            src.write_text("original")
            source = f"""
allow filesystem.read "{tmpdir}"
allow filesystem.write "{tmpdir}"
copy file "{src}" to "{dst}"
"""
            run(source)
            assert src.exists()
            assert dst.exists()
            assert dst.read_text() == "original"

    def test_delete_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "toDelete.txt"
            f.write_text("bye")
            source = f"""
allow filesystem.write "{tmpdir}"
delete file "{f}"
"""
            run(source)
            assert not f.exists()

    def test_read_nonexistent_file_returns_failed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = f"""
allow filesystem.read "{tmpdir}"
let result = read file "{tmpdir}/nonexistent.txt"
"""
            interp = run(source)
            result = interp.globals.get("result")
            assert isinstance(result, SpryResult)
            assert not result.ok
            assert result.failed is True


class TestObjectLiterals:
    def test_object_creation(self):
        interp = run('let obj = { name: "Alice", age: 30 }')
        obj = interp.globals.get("obj")
        assert obj["name"] == "Alice"
        assert obj["age"] == 30

    def test_object_member_access(self):
        interp = run('let obj = { x: 42 }\nlet val = obj.x')
        assert interp.globals.get("val") == 42

    def test_nested_object(self):
        interp = run('let obj = { a: { b: 99 } }\nlet val = obj.a.b')
        assert interp.globals.get("val") == 99


class TestBuiltinFunctions:
    def test_uuid_generates_string(self):
        interp = run("let id = uuid()")
        val = interp.globals.get("id")
        assert isinstance(val, str)
        assert len(val) == 36

    def test_now_returns_string(self):
        interp = run("let ts = now()")
        val = interp.globals.get("ts")
        assert isinstance(val, str)
        assert "T" in val  # ISO format

    def test_len_builtin(self):
        assert eval_expr('len("hello")') == 5

    def test_str_builtin(self):
        assert eval_expr("str(42)") == "42"


class TestTransactions:
    def test_transaction_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "in.txt"
            src.write_text("data")
            dst = Path(tmpdir) / "out.txt"
            source = f"""
allow filesystem.read "{tmpdir}"
allow filesystem.write "{tmpdir}"
transaction filesystem {{
    copy file "{src}" to "{dst}"
}}
"""
            run(source)
            assert dst.exists()


class TestAtomicOperations:
    def test_atomic_block(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "in.txt"
            src.write_text("atomic")
            dst = Path(tmpdir) / "out.txt"
            source = f"""
allow filesystem.read "{tmpdir}"
allow filesystem.write "{tmpdir}"
atomic {{
    copy file "{src}" to "{dst}"
}}
"""
            run(source)
            assert dst.exists()
