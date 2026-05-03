"""Phase 42 feature tests.

Covers:
- ``typeof`` operator now returns JS-standard lowercase strings:
  ``'number'``, ``'string'``, ``'boolean'``, ``'object'``, ``'function'``,
  ``'symbol'``, ``'undefined'``
- ``typeof null`` → ``'object'`` (JS quirk)
- ``typeof`` class / function / arrow function → ``'function'``
- ``typeof`` SpryCode instance, array, dict, generator, promise → ``'object'``
- ``typeof`` symbol instance → ``'symbol'``
- ``error.constructor.name`` → error type name string (``'Error'``, ``'TypeError'``, etc.)
- ``list.push(a, b, c)`` / ``list.push(...spread)`` — multi-argument push
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
# typeof — JS-standard lowercase values
# ---------------------------------------------------------------------------


class TestTypeofPrimitives:
    def test_typeof_int(self) -> None:
        i = run("let v = typeof 42")
        assert val(i) == "number"

    def test_typeof_float(self) -> None:
        i = run("let v = typeof 3.14")
        assert val(i) == "number"

    def test_typeof_string(self) -> None:
        i = run("let v = typeof 'hello'")
        assert val(i) == "string"

    def test_typeof_bool_true(self) -> None:
        i = run("let v = typeof true")
        assert val(i) == "boolean"

    def test_typeof_bool_false(self) -> None:
        i = run("let v = typeof false")
        assert val(i) == "boolean"

    def test_typeof_null(self) -> None:
        """typeof null === 'object' — the classic JS quirk."""
        i = run("let v = typeof null")
        assert val(i) == "object"

    def test_typeof_undefined_literal(self) -> None:
        i = run("let v = typeof undefined")
        assert val(i) == "undefined"

    def test_typeof_undeclared(self) -> None:
        """typeof undeclaredVariable returns 'undefined' without raising."""
        i = run("let v = typeof TOTALLY_UNDECLARED_XYZ")
        assert val(i) == "undefined"

    def test_typeof_symbol(self) -> None:
        i = run("let s = Symbol('tag'); let v = typeof s")
        assert val(i) == "symbol"

    def test_typeof_symbol_empty(self) -> None:
        i = run("let s = Symbol(); let v = typeof s")
        assert val(i) == "symbol"


class TestTypeofObjects:
    def test_typeof_array(self) -> None:
        i = run("let v = typeof [1,2,3]")
        assert val(i) == "object"

    def test_typeof_empty_array(self) -> None:
        i = run("let v = typeof []")
        assert val(i) == "object"

    def test_typeof_dict(self) -> None:
        i = run("let v = typeof {a: 1}")
        assert val(i) == "object"

    def test_typeof_empty_dict(self) -> None:
        i = run("let v = typeof {}")
        assert val(i) == "object"

    def test_typeof_class_instance(self) -> None:
        i = run("class Foo {}\nlet x = Foo.new()\nlet v = typeof x")
        assert val(i) == "object"

    def test_typeof_generator_object(self) -> None:
        i = run("fn* g() { yield 1 }\nlet gen = g()\nlet v = typeof gen")
        assert val(i) == "object"

    def test_typeof_promise(self) -> None:
        i = run("async fn f() { return 1 }\nlet v = typeof f()")
        assert val(i) == "object"

    def test_typeof_map(self) -> None:
        i = run("let m = new Map()\nlet v = typeof m")
        assert val(i) == "object"

    def test_typeof_set(self) -> None:
        i = run("let s = new Set()\nlet v = typeof s")
        assert val(i) == "object"

    def test_typeof_null_variable(self) -> None:
        i = run("let x = null\nlet v = typeof x")
        assert val(i) == "object"


class TestTypeofFunctions:
    def test_typeof_named_fn(self) -> None:
        i = run("fn f() { return 1 }\nlet v = typeof f")
        assert val(i) == "function"

    def test_typeof_anon_fn(self) -> None:
        i = run("let f = fn(x) => x\nlet v = typeof f")
        assert val(i) == "function"

    def test_typeof_arrow_fn(self) -> None:
        i = run("let f = x => x * 2\nlet v = typeof f")
        assert val(i) == "function"

    def test_typeof_class(self) -> None:
        i = run("class Bar {}\nlet v = typeof Bar")
        assert val(i) == "function"

    def test_typeof_generator_fn(self) -> None:
        """Generator function itself (not instance) is a function."""
        i = run("fn* gen() { yield 1 }\nlet v = typeof gen")
        assert val(i) == "function"

    def test_typeof_async_fn(self) -> None:
        """async fn itself is a function."""
        i = run("async fn f() { return 1 }\nlet v = typeof f")
        assert val(i) == "function"

    def test_typeof_lambda_multiline(self) -> None:
        i = run("let f = (x, y) => x + y\nlet v = typeof f")
        assert val(i) == "function"


class TestTypeofInExpressions:
    def test_typeof_in_condition(self) -> None:
        i = run("let x = 42\nvar v = 'no'\nif typeof x == 'number' { v = 'yes' }")
        assert val(i) == "yes"

    def test_typeof_in_switch(self) -> None:
        src = """
fn classify(x) {
  switch typeof x {
    case 'number': return 'num'
    case 'string': return 'str'
    case 'boolean': return 'bool'
    default: return 'other'
  }
}
let v = [classify(1), classify('hi'), classify(true), classify(null)]
"""
        i = run(src)
        assert val(i) == ["num", "str", "bool", "other"]

    def test_typeof_in_match(self) -> None:
        src = """
fn describe(x) {
  return match typeof x {
    'number' => 'n'
    'string' => 's'
    'boolean' => 'b'
    _ => '?'
  }
}
let v = [describe(1), describe('a'), describe(false), describe([])]
"""
        i = run(src)
        assert val(i) == ["n", "s", "b", "?"]


# ---------------------------------------------------------------------------
# error.constructor.name
# ---------------------------------------------------------------------------


class TestErrorConstructorName:
    def test_error_constructor_name(self) -> None:
        i = run("""
var v = ''
try {
  throw new Error('oops')
} catch(e) {
  v = e.constructor.name
}
""")
        assert val(i) == "Error"

    def test_type_error_constructor_name(self) -> None:
        i = run("""
var v = ''
try {
  null.x
} catch(e) {
  v = e.constructor.name
}
""")
        assert val(i) == "TypeError"

    def test_range_error_constructor_name(self) -> None:
        i = run("""
var v = ''
try {
  throw new RangeError('out of range')
} catch(e) {
  v = e.constructor.name
}
""")
        assert val(i) == "RangeError"

    def test_syntax_error_constructor_name(self) -> None:
        i = run("""
var v = ''
try {
  throw new SyntaxError('bad syntax')
} catch(e) {
  v = e.constructor.name
}
""")
        assert val(i) == "SyntaxError"

    def test_constructor_name_matches_name(self) -> None:
        """error.constructor.name === error.name"""
        i = run("""
var v = false
try {
  throw new TypeError('t')
} catch(e) {
  v = e.constructor.name == e.name
}
""")
        assert val(i) is True

    def test_constructor_is_dict(self) -> None:
        """error.constructor is a dict with a 'name' key."""
        i = run("""
var v = ''
try {
  throw new Error('x')
} catch(e) {
  v = e.constructor.name
}
""")
        assert val(i) == "Error"


# ---------------------------------------------------------------------------
# list.push with multiple arguments
# ---------------------------------------------------------------------------


class TestListPushMulti:
    def test_push_single(self) -> None:
        i = run("let a = [1, 2]; a.push(3); let v = a")
        assert val(i) == [1, 2, 3]

    def test_push_two_args(self) -> None:
        i = run("let a = [1]; a.push(2, 3); let v = a")
        assert val(i) == [1, 2, 3]

    def test_push_three_args(self) -> None:
        i = run("let a = []; a.push(1, 2, 3); let v = a")
        assert val(i) == [1, 2, 3]

    def test_push_spread(self) -> None:
        i = run("let a = []; let b = [1, 2, 3]; a.push(...b); let v = a")
        assert val(i) == [1, 2, 3]

    def test_push_returns_new_length(self) -> None:
        i = run("let a = [1, 2]; let v = a.push(3, 4)")
        assert val(i) == 4

    def test_push_returns_length_single(self) -> None:
        i = run("let a = []; let v = a.push(99)")
        assert val(i) == 1

    def test_push_preserves_order(self) -> None:
        i = run("let a = ['a']; a.push('b', 'c', 'd'); let v = a")
        assert val(i) == ["a", "b", "c", "d"]

    def test_push_spread_in_class_method(self) -> None:
        i = run("""
class Collector {
    fn init() { this.items = [] }
    fn add(...args) { this.items.push(...args) }
    fn all() { return this.items }
}
let c = Collector.new()
c.add(1, 2, 3)
let v = c.all()
""")
        assert val(i) == [1, 2, 3]
