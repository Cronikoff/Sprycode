"""Phase 41 feature tests.

Covers:
- C-style ``for`` with empty init: ``for(;;)``, ``for(;cond;update)``, ``for(;cond;)``
- C-style ``for`` with plain-expression/assignment init: ``for(i=0; i<n; i++)``
- Multiple variable declarations in one statement: ``var a=1, b=2, c=3``,
  ``let x=1, y=2``, ``const p=1, q=2``
- ``arguments`` object inside functions — ``arguments.length`` and ``arguments[i]``
- Extra args silently ignored (JS semantics — no "too many args" error)
- ``trimLeft`` / ``trimRight`` as aliases for ``trimStart`` / ``trimEnd``
- Optional method call with args when receiver is null: ``null?.method(args)``
  now returns ``null`` instead of raising a runtime error
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


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(interp: Interpreter, name: str = "v") -> Any:
    return interp.globals.get(name)


# ---------------------------------------------------------------------------
# for(;;) — empty init, empty condition, empty update
# ---------------------------------------------------------------------------


class TestForEmptyInit:
    def test_infinite_loop_break(self) -> None:
        """for(;;) with explicit break."""
        i = run("""
var counter = 0
for (;;) {
    counter++
    if (counter >= 5) break
}
let v = counter
""")
        assert val(i) == 5

    def test_empty_init_with_condition(self) -> None:
        """for(; cond; update) — omitted initialiser."""
        i = run("""
var i = 0
for (; i < 4; i++) { }
let v = i
""")
        assert val(i) == 4

    def test_empty_init_empty_update(self) -> None:
        """for(; cond;) — omitted init and update."""
        i = run("""
var i = 0
for (; i < 3;) { i++ }
let v = i
""")
        assert val(i) == 3

    def test_empty_condition_treated_as_true(self) -> None:
        """for(init;; update) — empty condition is truthy (infinite until break)."""
        i = run("""
var i = 0
for (var j = 0;; j++) {
    i++
    if (j >= 4) break
}
let v = i
""")
        assert val(i) == 5

    def test_fully_empty_accumulates(self) -> None:
        """for(;;) — all three parts omitted; loop body manages everything."""
        i = run("""
var total = 0
var n = 0
for (;;) {
    total += n
    n++
    if (n > 4) break
}
let v = total
""")
        # 0+1+2+3+4 = 10
        assert val(i) == 10


# ---------------------------------------------------------------------------
# for with assignment init (no var/let keyword)
# ---------------------------------------------------------------------------


class TestForAssignmentInit:
    def test_simple_assignment_init(self) -> None:
        """for(i=0; i<n; i++) with pre-declared var."""
        i = run("""
var i = 99
for (i = 0; i < 5; i++) { }
let v = i
""")
        assert val(i) == 5

    def test_assignment_init_body_executes(self) -> None:
        i = run("""
var sum = 0
var i = 0
for (i = 1; i <= 4; i++) {
    sum += i
}
let v = sum
""")
        assert val(i) == 10

    def test_expression_init(self) -> None:
        """for with side-effect expression in init (postfix expression)."""
        i = run("""
var k = 0
var total = 0
for (k++; k < 4; k++) {
    total += k
}
let v = total
""")
        # k starts 0, k++ makes k=1, then loop: k=1,2,3 → total=1+2+3=6
        assert val(i) == 6

    def test_assign_init_var_visible_after(self) -> None:
        i = run("""
var x = 0
for (x = 10; x < 13; x++) { }
let v = x
""")
        assert val(i) == 13


# ---------------------------------------------------------------------------
# Multiple variable declarations
# ---------------------------------------------------------------------------


class TestMultiVarDecl:
    def test_multi_var(self) -> None:
        i = run("var a = 1, b = 2, c = 3; let v = a + b + c")
        assert val(i) == 6

    def test_multi_let(self) -> None:
        i = run("let x = 10, y = 20; let v = x + y")
        assert val(i) == 30

    def test_multi_const(self) -> None:
        i = run("const p = 100, q = 200; let v = p + q")
        assert val(i) == 300

    def test_multi_var_some_uninitialized(self) -> None:
        i = run("var a = 5, b; let v = a")
        assert val(i) == 5

    def test_multi_var_used_in_loop(self) -> None:
        i = run("""
var sum = 0
for (var i = 0, j = 10; i < 3; i++, j--) {
    sum += i + j
}
let v = sum
""")
        # (0+10)+(1+9)+(2+8) = 10+10+10 = 30
        assert val(i) == 30

    def test_multi_let_strings(self) -> None:
        i = run("""
let greeting = 'hello', name = 'world'
let v = greeting + ' ' + name
""")
        assert val(i) == "hello world"

    def test_multi_var_expressions(self) -> None:
        i = run("""
var base = 10
var doubled = base * 2, tripled = base * 3
let v = doubled + tripled
""")
        assert val(i) == 50

    def test_multi_let_destructure_with_plain(self) -> None:
        """let a = 1, [b, c] = arr  (plain + destructure)."""
        i = run("""
let a = 1, [b, c] = [2, 3]
let v = a + b + c
""")
        assert val(i) == 6


# ---------------------------------------------------------------------------
# arguments object
# ---------------------------------------------------------------------------


class TestArguments:
    def test_arguments_length(self) -> None:
        i = run("fn f() { return arguments.length }; let v = f(1, 2, 3)")
        assert val(i) == 3

    def test_arguments_indexing(self) -> None:
        i = run("fn f() { return arguments[1] }; let v = f('a', 'b', 'c')")
        assert val(i) == "b"

    def test_arguments_sum(self) -> None:
        i = run("""
fn sum() {
    var total = 0
    for (var i = 0; i < arguments.length; i++) {
        total += arguments[i]
    }
    return total
}
let v = sum(1, 2, 3, 4, 5)
""")
        assert val(i) == 15

    def test_arguments_empty(self) -> None:
        i = run("fn f() { return arguments.length }; let v = f()")
        assert val(i) == 0

    def test_extra_args_ignored(self) -> None:
        """Calling a function with more args than declared doesn't raise an error."""
        i = run("fn add(a, b) { return a + b }; let v = add(1, 2, 999)")
        assert val(i) == 3

    def test_arguments_as_array(self) -> None:
        """arguments can be spread."""
        i = run("""
fn f() {
    return [...arguments]
}
let v = f(10, 20, 30)
""")
        assert val(i) == [10, 20, 30]

    def test_arguments_in_method(self) -> None:
        """arguments works inside class methods too."""
        i = run("""
class Acc {
    init() { this.total = 0 }
    add() {
        for (var i = 0; i < arguments.length; i++) {
            this.total += arguments[i]
        }
    }
    value() { return this.total }
}
let a = Acc.new()
a.add(1, 2, 3)
a.add(4, 5)
let v = a.value()
""")
        assert val(i) == 15


# ---------------------------------------------------------------------------
# trimLeft / trimRight aliases
# ---------------------------------------------------------------------------


class TestTrimAliases:
    def test_trim_left(self) -> None:
        i = run("let v = '   hello'.trimLeft()")
        assert val(i) == "hello"

    def test_trim_right(self) -> None:
        i = run("let v = 'hello   '.trimRight()")
        assert val(i) == "hello"

    def test_trim_left_no_change(self) -> None:
        i = run("let v = 'hello   '.trimLeft()")
        assert val(i) == "hello   "

    def test_trim_right_no_change(self) -> None:
        i = run("let v = '   hello'.trimRight()")
        assert val(i) == "   hello"

    def test_trim_left_both_spaces(self) -> None:
        i = run("let v = '  hello  '.trimLeft()")
        assert val(i) == "hello  "

    def test_trim_right_both_spaces(self) -> None:
        i = run("let v = '  hello  '.trimRight()")
        assert val(i) == "  hello"


# ---------------------------------------------------------------------------
# Optional method call with args on null
# ---------------------------------------------------------------------------


class TestOptionalMethodCallArgs:
    def test_optional_method_null_returns_null(self) -> None:
        """null?.method(args) returns null rather than raising."""
        i = run("let arr = null; let v = arr?.map(x => x * 2) ?? 'fallback'")
        assert val(i) == "fallback"

    def test_optional_method_non_null_executes(self) -> None:
        """non-null?.method(args) calls the method normally."""
        i = run("let arr = [1, 2, 3]; let v = arr?.map(x => x * 2)")
        assert val(i) == [2, 4, 6]

    def test_optional_method_with_multi_args(self) -> None:
        i = run("let s = null; let v = s?.replace('a', 'b') ?? 'gone'")
        assert val(i) == "gone"

    def test_optional_method_chained_null(self) -> None:
        i = run("let obj = null; let v = obj?.foo?.bar?.map(x => x) ?? 42")
        assert val(i) == 42

    def test_optional_method_filter_null(self) -> None:
        i = run("let arr = null; let v = arr?.filter(x => x > 2) ?? []")
        assert val(i) == []

    def test_optional_method_non_null_filter(self) -> None:
        i = run("let arr = [1, 2, 3, 4]; let v = arr?.filter(x => x > 2)")
        assert val(i) == [3, 4]

    def test_optional_call_expression_null(self) -> None:
        """fn?.(args) — existing OptionalCallExpression still works."""
        i = run("let f = null; let v = f?.(1, 2, 3)")
        assert val(i) is None

    def test_optional_call_expression_non_null(self) -> None:
        i = run("fn double(x) { return x * 2 }; let v = double?.(7)")
        assert val(i) == 14
