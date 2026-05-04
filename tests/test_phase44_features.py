"""Phase 44 feature tests.

Covers:
- Unary ``+`` operator (numeric coercion: ``+expr``)
- ``??`` (NullCoalesceExpression) treating ``undefined`` as nullish
- ``valueOf()`` coercion in arithmetic for SpryInstance
- ``Symbol.toPrimitive`` coercion for SpryInstance
- ``arr[Symbol.iterator]()``, ``str[Symbol.iterator]()``,
  ``set[Symbol.iterator]()``, ``map[Symbol.iterator]()``
"""

from __future__ import annotations

from typing import Any

import math
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
# Unary + operator
# ---------------------------------------------------------------------------

class TestUnaryPlus:
    def test_string_to_number(self) -> None:
        i = run('let v = +"42"')
        assert val(i) == 42

    def test_string_float(self) -> None:
        i = run('let v = +"3.14"')
        assert abs(val(i) - 3.14) < 1e-9

    def test_true_to_1(self) -> None:
        i = run("let v = +true")
        assert val(i) == 1

    def test_false_to_0(self) -> None:
        i = run("let v = +false")
        assert val(i) == 0

    def test_null_to_0(self) -> None:
        i = run("let v = +null")
        assert val(i) == 0

    def test_undefined_to_nan(self) -> None:
        i = run("let v = +undefined")
        assert math.isnan(val(i))

    def test_non_numeric_string_to_nan(self) -> None:
        i = run('let v = +"abc"')
        assert math.isnan(val(i))

    def test_number_unchanged(self) -> None:
        i = run("let v = +7")
        assert val(i) == 7

    def test_negative_number(self) -> None:
        i = run("let v = +(-3)")
        assert val(i) == -3

    def test_empty_string_to_0(self) -> None:
        i = run('let v = +""')
        assert val(i) == 0

    def test_unary_plus_in_expression(self) -> None:
        i = run('let x = "5"; let v = +x + 3')
        assert val(i) == 8

    def test_unary_plus_whitespace_string(self) -> None:
        i = run('let v = +"  7  "')
        assert val(i) == 7


# ---------------------------------------------------------------------------
# ?? (NullCoalesceExpression) with undefined
# ---------------------------------------------------------------------------

class TestNullCoalesceUndefined:
    def test_undefined_returns_fallback(self) -> None:
        i = run('let v = undefined ?? "fallback"')
        assert val(i) == "fallback"

    def test_null_returns_fallback(self) -> None:
        i = run('let v = null ?? "fallback"')
        assert val(i) == "fallback"

    def test_zero_is_not_nullish(self) -> None:
        i = run('let v = 0 ?? "fallback"')
        assert val(i) == 0

    def test_false_is_not_nullish(self) -> None:
        i = run('let v = false ?? "fallback"')
        assert val(i) is False

    def test_empty_string_is_not_nullish(self) -> None:
        i = run('let v = "" ?? "fallback"')
        assert val(i) == ""

    def test_undefined_variable_nullish(self) -> None:
        i = run("var x = undefined; let v = x ?? 99")
        assert val(i) == 99

    def test_chained_nullish(self) -> None:
        i = run('let v = undefined ?? null ?? "final"')
        assert val(i) == "final"

    def test_nullish_assign_undefined(self) -> None:
        i = run("var x = undefined; x ??= 42; let v = x")
        assert val(i) == 42

    def test_nullish_assign_null(self) -> None:
        i = run("var x = null; x ??= 5; let v = x")
        assert val(i) == 5

    def test_nullish_assign_preserves_value(self) -> None:
        i = run("var x = 10; x ??= 99; let v = x")
        assert val(i) == 10


# ---------------------------------------------------------------------------
# valueOf() coercion in arithmetic
# ---------------------------------------------------------------------------

class TestValueOfCoercion:
    def test_add_to_number(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n }\n"
            "}\n"
            "let v = N.new(10) + 5"
        )
        assert val(i) == 15

    def test_subtract(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n }\n"
            "}\n"
            "let v = N.new(20) - 7"
        )
        assert val(i) == 13

    def test_multiply(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n }\n"
            "}\n"
            "let v = N.new(6) * 7"
        )
        assert val(i) == 42

    def test_divide(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n }\n"
            "}\n"
            "let v = N.new(10) / 2"
        )
        assert val(i) == 5

    def test_modulo(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n }\n"
            "}\n"
            "let v = N.new(11) % 3"
        )
        assert val(i) == 2

    def test_power(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n }\n"
            "}\n"
            "let v = N.new(3) ** 4"
        )
        assert val(i) == 81

    def test_string_plus_instance_uses_tostring(self) -> None:
        # JS "default" hint calls valueOf() first; valueOf returns 0,
        # which is then coerced to "0" since left side is a string.
        i = run(
            "class Tag {\n"
            "  fn init(name) { this.name = name }\n"
            "  valueOf() { return 0 }\n"
            "  toString() { return this.name }\n"
            "}\n"
            "let v = 'hello ' + Tag.new('world')"
        )
        # valueOf() returns 0 (default hint), then 0 is coerced to "0"
        assert val(i) == "hello 0"

    def test_valueof_two_instances(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n }\n"
            "}\n"
            "let v = N.new(3) + N.new(4)"
        )
        assert val(i) == 7

    def test_unary_plus_calls_valueof(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n }\n"
            "}\n"
            "let v = +N.new(99)"
        )
        assert val(i) == 99


# ---------------------------------------------------------------------------
# Symbol.toPrimitive coercion
# ---------------------------------------------------------------------------

class TestSymbolToPrimitive:
    def test_number_hint(self) -> None:
        # Use subtraction (numeric op) to get "number" hint via _to_numeric
        i = run(
            "class Temp {\n"
            "  fn init(c) { this.celsius = c }\n"
            "  [Symbol.toPrimitive](hint) {\n"
            "    if (hint == 'number') { return this.celsius }\n"
            "    return this.celsius + 'C'\n"
            "  }\n"
            "}\n"
            "let v = Temp.new(100) - 0"
        )
        assert val(i) == 100

    def test_arithmetic_minus(self) -> None:
        i = run(
            "class Temp {\n"
            "  fn init(c) { this.celsius = c }\n"
            "  [Symbol.toPrimitive](hint) {\n"
            "    return this.celsius\n"
            "  }\n"
            "}\n"
            "let v = Temp.new(50) - 10"
        )
        assert val(i) == 40

    def test_default_hint_for_plus(self) -> None:
        i = run(
            "class Box {\n"
            "  fn init(n) { this.n = n }\n"
            "  [Symbol.toPrimitive](hint) {\n"
            "    if (hint == 'default' || hint == 'number') { return this.n }\n"
            "    return 'box(' + this.n + ')'\n"
            "  }\n"
            "}\n"
            "let v = Box.new(7) + 3"
        )
        assert val(i) == 10

    def test_string_hint_in_template(self) -> None:
        i = run(
            "class Tag {\n"
            "  fn init(name) { this.name = name }\n"
            "  [Symbol.toPrimitive](hint) {\n"
            "    if (hint == 'string') { return '<' + this.name + '>' }\n"
            "    return 0\n"
            "  }\n"
            "}\n"
            "let t = Tag.new('div')\n"
            "let v = `tag: ${t}`"
        )
        assert val(i) == "tag: <div>"

    def test_toprimitive_takes_priority_over_valueof(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  valueOf() { return this.n * 10 }\n"
            "  [Symbol.toPrimitive](hint) { return this.n }\n"
            "}\n"
            "let v = N.new(5) + 0"
        )
        assert val(i) == 5

    def test_multiply(self) -> None:
        i = run(
            "class Scalar {\n"
            "  fn init(v) { this.v = v }\n"
            "  [Symbol.toPrimitive](hint) { return this.v }\n"
            "}\n"
            "let v = Scalar.new(6) * 7"
        )
        assert val(i) == 42

    def test_unary_plus_calls_toprimitive(self) -> None:
        i = run(
            "class N {\n"
            "  fn init(n) { this.n = n }\n"
            "  [Symbol.toPrimitive](hint) { return this.n }\n"
            "}\n"
            "let v = +N.new(77)"
        )
        assert val(i) == 77


# ---------------------------------------------------------------------------
# [Symbol.iterator]() on built-in types
# ---------------------------------------------------------------------------

class TestSymbolIteratorBuiltins:
    def test_array_iterator(self) -> None:
        i = run(
            "let arr = [10, 20, 30]\n"
            "let it = arr[Symbol.iterator]()\n"
            "let v1 = it.next()\n"
            "let v2 = it.next()\n"
            "let v3 = it.next()\n"
            "let v4 = it.next()\n"
            "let v = [v1.value, v2.value, v3.value, v4.done]"
        )
        assert val(i) == [10, 20, 30, True]

    def test_array_iterator_empty(self) -> None:
        i = run(
            "let arr = []\n"
            "let it = arr[Symbol.iterator]()\n"
            "let r = it.next()\n"
            "let v = r.done"
        )
        assert val(i) is True

    def test_string_iterator(self) -> None:
        i = run(
            "let it = 'hi'[Symbol.iterator]()\n"
            "let v1 = it.next().value\n"
            "let v2 = it.next().value\n"
            "let v3 = it.next().done\n"
            "let v = [v1, v2, v3]"
        )
        assert val(i) == ["h", "i", True]

    def test_set_iterator(self) -> None:
        i = run(
            "let s = new Set([1, 2, 3])\n"
            "let it = s[Symbol.iterator]()\n"
            "let v1 = it.next().value\n"
            "let v2 = it.next().value\n"
            "let v3 = it.next().value\n"
            "let v4 = it.next().done\n"
            "let v = [v1, v2, v3, v4]"
        )
        assert val(i) == [1, 2, 3, True]

    def test_map_iterator(self) -> None:
        i = run(
            "let m = new Map()\n"
            "m.set('a', 1)\n"
            "m.set('b', 2)\n"
            "let it = m[Symbol.iterator]()\n"
            "let e1 = it.next().value\n"
            "let e2 = it.next().value\n"
            "let done = it.next().done\n"
            "let v = [e1, e2, done]"
        )
        assert val(i) == [["a", 1], ["b", 2], True]

    def test_array_iterator_used_in_for_of(self) -> None:
        i = run(
            "let arr = [4, 5, 6]\n"
            "let it = arr[Symbol.iterator]()\n"
            "let v = []\n"
            "for (let x of it) { v.push(x) }"
        )
        assert val(i) == [4, 5, 6]

    def test_array_spread_after_iterator(self) -> None:
        i = run(
            "let arr = [7, 8, 9]\n"
            "let it = arr[Symbol.iterator]()\n"
            "let v = [...it]"
        )
        assert val(i) == [7, 8, 9]
