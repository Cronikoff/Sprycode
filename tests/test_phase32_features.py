"""Phase 32 feature tests.

Covers:
- Comma operator: (a, b, c) — evaluates each expression left-to-right, returns last
- void operator: void <expr> — evaluates expression, always returns null/None
- switch no-fallthrough: only the first matching case body executes (break exits early)
"""

from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import Interpreter
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


# ---------------------------------------------------------------------------
# Comma operator: (a, b, c) → returns last value
# ---------------------------------------------------------------------------


class TestCommaOperator:
    def test_two_literals_returns_last(self) -> None:
        assert val("let v = (1, 2)") == 2

    def test_three_literals_returns_last(self) -> None:
        assert val("let v = (1, 2, 3)") == 3

    def test_returns_last_string(self) -> None:
        assert val('let v = ("a", "b", "c")') == "c"

    def test_returns_last_bool(self) -> None:
        assert val("let v = (true, false, true)") is True

    def test_side_effects_preserved(self) -> None:
        i = run("var x = 0; let v = (x = 5, x * 2)")
        assert val(i) == 10
        assert i.globals.get("x") == 5

    def test_all_exprs_evaluated(self) -> None:
        i = run("var calls = []; fn f(x) { calls.push(x) }; (f(1), f(2), f(3)); let v = calls")
        assert val(i) == [1, 2, 3]

    def test_assignment_side_effects(self) -> None:
        i = run("var a = 0; var b = 0; let v = (a = 10, b = 20, a + b)")
        assert val(i) == 30
        assert i.globals.get("a") == 10
        assert i.globals.get("b") == 20

    def test_nested_comma(self) -> None:
        assert val("let v = ((1, 2), 3)") == 3

    def test_two_assignments_last_wins(self) -> None:
        i = run("var x = 0; var v = (x = 1, x = 2, x)")
        assert val(i) == 2

    def test_statement_context(self) -> None:
        i = run("var s = 0; (s = 1, s = 2); let v = s")
        assert val(i) == 2

    def test_arithmetic_exprs(self) -> None:
        assert val("let v = (1 + 1, 2 + 2)") == 4

    def test_two_zeros(self) -> None:
        assert val("let v = (0, 0)") == 0

    def test_large_chain(self) -> None:
        assert val("let v = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)") == 10


# ---------------------------------------------------------------------------
# void operator: always returns null regardless of expression
# ---------------------------------------------------------------------------


class TestVoidOperator:
    def test_void_number(self) -> None:
        assert val("let v = void 42") is None

    def test_void_zero(self) -> None:
        assert val("let v = void 0") is None

    def test_void_string(self) -> None:
        assert val('let v = void "hello"') is None

    def test_void_null(self) -> None:
        assert val("let v = void null") is None

    def test_void_true(self) -> None:
        assert val("let v = void true") is None

    def test_void_expression(self) -> None:
        assert val("let v = void (1 + 2)") is None

    def test_void_from_function(self) -> None:
        i = run("fn f() { return void 0 }; let v = f()")
        assert val(i) is None

    def test_void_evaluates_side_effects(self) -> None:
        i = run("var x = 0; fn inc() { x = x + 1; return x }; let v = void inc(); let s = x")
        assert val(i) is None
        assert i.globals.get("s") == 1

    def test_void_in_ternary(self) -> None:
        assert val("let v = true ? void 1 : 2") is None


# ---------------------------------------------------------------------------
# switch: only first matching case executes (no fall-through)
# ---------------------------------------------------------------------------


class TestSwitchNoFallthrough:
    def test_first_match_only(self) -> None:
        i = run("""
var r = 0
switch 1 {
    case 1: r = 10
    case 2: r = 20
}
let v = r
""")
        assert val(i) == 10

    def test_only_matching_case_runs(self) -> None:
        i = run("""
var r = []
switch 2 {
    case 1: r.push(1)
    case 2: r.push(2)
    case 3: r.push(3)
}
let v = r
""")
        assert val(i) == [2]

    def test_default_only_when_no_match(self) -> None:
        i = run("""
var r = 0
switch 99 {
    case 1: r = 1
    case 2: r = 2
    default: r = 99
}
let v = r
""")
        assert val(i) == 99

    def test_break_exits_case(self) -> None:
        i = run("""
var r = 0
switch 1 {
    case 1: {
        r = 10
        break
        r = 99
    }
    case 2: r = 20
}
let v = r
""")
        assert val(i) == 10

    def test_string_match(self) -> None:
        i = run("""
var r = ""
switch "b" {
    case "a": r = "got-a"
    case "b": r = "got-b"
    case "c": r = "got-c"
}
let v = r
""")
        assert val(i) == "got-b"

    def test_no_match_no_default(self) -> None:
        i = run("""
var r = 0
switch 9 {
    case 1: r = 1
    case 2: r = 2
}
let v = r
""")
        assert val(i) == 0
