"""Phase 33 feature tests.

Covers:
- SprySet member access: .size, .has(), .add(), .delete(), .clear(), .toList(),
  .union(), .intersection(), .difference(), .symmetricDifference(),
  .isSubsetOf(), .isSupersetOf(), .isDisjointFrom(), .values(), .forEach()
- Proxy: new Proxy(target, handler) — passthrough and get/set trap
- `log` as a regular identifier (variable, function name, parameter name)
  while `log "message"` log-statement syntax is preserved
"""

from __future__ import annotations

from typing import Any

import io

import pytest

from sprycode.interpreter import Interpreter, SpryLogger
from sprycode.lexer import Lexer
from sprycode.parser import Parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(source_or_interp: Any, name: str = "v") -> Any:
    if isinstance(source_or_interp, str):
        return run(source_or_interp).globals.get(name)
    return source_or_interp.globals.get(name)


class _MockLogger:
    """Logger that captures all log calls."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []

    def info(self, msg: str) -> None:
        self.entries.append(("info", msg))

    def warn(self, msg: str) -> None:
        self.entries.append(("warn", msg))

    def error(self, msg: str) -> None:
        self.entries.append(("error", msg))

    def debug(self, msg: str) -> None:
        self.entries.append(("debug", msg))


def run_logged(source: str) -> tuple[Interpreter, _MockLogger]:
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    logger = _MockLogger()
    i = Interpreter()
    i.logger = logger
    i.run(prog)
    return i, logger


# ---------------------------------------------------------------------------
# SprySet member access
# ---------------------------------------------------------------------------


class TestSprySetMemberAccess:
    def test_size(self) -> None:
        assert val("let s = Set.new([1,2,3]); let v = s.size") == 3

    def test_size_deduplicates(self) -> None:
        assert val("let s = Set.new([1,2,3,2,1]); let v = s.size") == 3

    def test_size_empty(self) -> None:
        assert val("let s = Set.new([]); let v = s.size") == 0

    def test_has_present(self) -> None:
        assert val("let s = Set.new([1,2,3]); let v = s.has(2)") is True

    def test_has_absent(self) -> None:
        assert val("let s = Set.new([1,2,3]); let v = s.has(99)") is False

    def test_add_new_item(self) -> None:
        assert val("let s = Set.new([1,2]); s.add(3); let v = s.size") == 3

    def test_add_duplicate_no_op(self) -> None:
        assert val("let s = Set.new([1,2]); s.add(1); let v = s.size") == 2

    def test_delete_present(self) -> None:
        assert val("let s = Set.new([1,2,3]); s.delete(2); let v = s.size") == 2

    def test_delete_absent_returns_false(self) -> None:
        assert val("let s = Set.new([1,2,3]); let v = s.delete(99)") is False

    def test_delete_present_returns_true(self) -> None:
        assert val("let s = Set.new([1,2,3]); let v = s.delete(2)") is True

    def test_clear(self) -> None:
        assert val("let s = Set.new([1,2,3]); s.clear(); let v = s.size") == 0

    def test_to_list(self) -> None:
        assert val("let s = Set.new([3,1,2]); let v = s.toList()") == [3, 1, 2]

    def test_to_list_empty(self) -> None:
        assert val("let s = Set.new([]); let v = s.toList()") == []

    def test_union(self) -> None:
        assert val(
            "let a = Set.new([1,2,3]); let b = Set.new([3,4,5]); let v = a.union(b).toList()"
        ) == [1, 2, 3, 4, 5]

    def test_intersection(self) -> None:
        assert val(
            "let a = Set.new([1,2,3]); let b = Set.new([2,3,4]); let v = a.intersection(b).toList()"
        ) == [2, 3]

    def test_difference(self) -> None:
        assert val(
            "let a = Set.new([1,2,3]); let b = Set.new([2,3,4]); let v = a.difference(b).toList()"
        ) == [1]

    def test_symmetric_difference(self) -> None:
        i = run("let a = Set.new([1,2,3]); let b = Set.new([3,4,5]); let v = a.symmetricDifference(b).toList()")
        result = sorted(val(i))
        assert result == [1, 2, 4, 5]

    def test_is_subset_of_true(self) -> None:
        assert val(
            "let a = Set.new([2,3]); let b = Set.new([1,2,3,4]); let v = a.isSubsetOf(b)"
        ) is True

    def test_is_subset_of_false(self) -> None:
        assert val(
            "let a = Set.new([1,5]); let b = Set.new([1,2,3]); let v = a.isSubsetOf(b)"
        ) is False

    def test_is_superset_of_true(self) -> None:
        assert val(
            "let a = Set.new([1,2,3,4]); let b = Set.new([2,3]); let v = a.isSupersetOf(b)"
        ) is True

    def test_is_disjoint_from_true(self) -> None:
        assert val(
            "let a = Set.new([1,2]); let b = Set.new([3,4]); let v = a.isDisjointFrom(b)"
        ) is True

    def test_is_disjoint_from_false(self) -> None:
        assert val(
            "let a = Set.new([1,2]); let b = Set.new([2,3]); let v = a.isDisjointFrom(b)"
        ) is False

    def test_foreach(self) -> None:
        i = run("let s = Set.new([1,2,3]); var sum = 0; s.forEach(x => { sum += x }); let v = sum")
        assert val(i) == 6

    def test_values_iterable(self) -> None:
        i = run("let s = Set.new([10,20,30]); let v = Array.from(s.values())")
        assert val(i) == [10, 20, 30]

    def test_add_returns_set(self) -> None:
        i = run("let s = Set.new([1]); s.add(2).add(3); let v = s.size")
        assert val(i) == 3

    def test_sprySet_new_size(self) -> None:
        assert val("let s = SprySet.new([1,2,3]); let v = s.size") == 3


# ---------------------------------------------------------------------------
# Proxy: new Proxy(target, handler)
# ---------------------------------------------------------------------------


class TestProxyNew:
    def test_passthrough_property(self) -> None:
        assert val("let p = new Proxy({x: 1}, {}); let v = p.x") == 1

    def test_passthrough_index(self) -> None:
        assert val('let p = new Proxy({x: 1}, {}); let v = p["x"]') == 1

    def test_get_trap_multiplies(self) -> None:
        i = run("""
let p = new Proxy({x: 2}, {
    get(target, prop) { return target[prop] * 10 }
})
let v = p.x
""")
        assert val(i) == 20

    def test_get_trap_multiple_props(self) -> None:
        i = run("""
let p = new Proxy({a: 1, b: 2}, {
    get(target, prop) { return target[prop] + 100 }
})
let va = p.a
let vb = p.b
""")
        assert i.globals.get("va") == 101
        assert i.globals.get("vb") == 102

    def test_proxy_new_equals_proxy_dot_new(self) -> None:
        i1 = run("let p = Proxy.new({x: 1}, {}); let v = p.x")
        i2 = run("let p = new Proxy({x: 1}, {}); let v = p.x")
        assert val(i1) == val(i2)


# ---------------------------------------------------------------------------
# `log` as an identifier
# ---------------------------------------------------------------------------


class TestLogAsIdentifier:
    def test_log_as_variable(self) -> None:
        assert val("var log = 42; let v = log") == 42

    def test_log_as_let_binding(self) -> None:
        assert val("let log = 5; let v = log + 1") == 6

    def test_log_as_function_name(self) -> None:
        assert val('fn log() { return "logged" }; let v = log()') == "logged"

    def test_log_as_parameter_name(self) -> None:
        assert val("fn doLog(log) { return log }; let v = doLog(99)") == 99

    def test_log_as_method_name(self) -> None:
        assert val("class Foo { fn log(x) { return x } }; let v = Foo.new().log(5)") == 5

    def test_log_list_append(self) -> None:
        assert val("var log = []; log.push(1); log.push(2); let v = log") == [1, 2]

    def test_log_as_lambda_param(self) -> None:
        assert val("let v = [1,2,3].map(log => log * 2)") == [2, 4, 6]

    def test_log_arithmetic(self) -> None:
        assert val("let log = 10; let v = log * 3") == 30

    def test_log_member_access(self) -> None:
        assert val("var log = {level: 'info'}; let v = log.level") == "info"

    def test_log_statement_string_still_works(self) -> None:
        _, logger = run_logged('log "hello world"')
        assert logger.entries == [("info", "hello world")]

    def test_log_info_level_still_works(self) -> None:
        _, logger = run_logged('log info "info msg"')
        assert logger.entries == [("info", "info msg")]

    def test_log_warn_level_still_works(self) -> None:
        _, logger = run_logged('log warn "warn msg"')
        assert logger.entries == [("warn", "warn msg")]

    def test_log_error_level_still_works(self) -> None:
        _, logger = run_logged('log error "err msg"')
        assert logger.entries == [("error", "err msg")]

    def test_log_variable_still_works(self) -> None:
        _, logger = run_logged("let x = 42; log x")
        assert logger.entries == [("info", "42")]

    def test_log_number_still_works(self) -> None:
        _, logger = run_logged("log 99")
        assert logger.entries == [("info", "99")]
