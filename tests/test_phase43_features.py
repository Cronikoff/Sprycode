"""Phase 43 feature tests.

Covers:
- ``to`` and ``stop`` usable as variable / parameter names (added to _IDENTIFIER_LIKE)
- ``String(instance)`` delegates to instance ``toString()`` method
- dict iterator objects (``{next() {...}}``) consumed by spread ``[...iter]``
- class ``[Symbol.iterator]()`` iterable protocol with spread ``[...obj]``
- for-of loop over custom class iterable
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
# `to` and `stop` as identifiers
# ---------------------------------------------------------------------------

class TestToStopAsIdentifiers:
    def test_to_variable(self) -> None:
        i = run("let to = 42; let v = to")
        assert val(i) == 42

    def test_stop_variable(self) -> None:
        i = run("let stop = 7; let v = stop")
        assert val(i) == 7

    def test_to_parameter(self) -> None:
        i = run("fn f(to) { return to * 2 }; let v = f(5)")
        assert val(i) == 10

    def test_stop_parameter(self) -> None:
        i = run("fn f(stop) { return stop + 1 }; let v = f(9)")
        assert val(i) == 10

    def test_to_and_stop_params(self) -> None:
        i = run("fn f(to, stop) { return to + stop }; let v = f(3, 4)")
        assert val(i) == 7

    def test_to_in_object(self) -> None:
        i = run("let obj = {to: 99}; let v = obj.to")
        assert val(i) == 99

    def test_stop_in_object(self) -> None:
        i = run("let obj = {stop: 'here'}; let v = obj.stop")
        assert val(i) == "here"

    def test_to_reassigned(self) -> None:
        i = run("var to = 1; to = 2; let v = to")
        assert val(i) == 2

    def test_stop_in_for_loop_var(self) -> None:
        i = run(
            "var stop = 3; var v = 0; "
            "for (let i = 0; i < stop; i++) { v++ }"
        )
        assert val(i) == 3

    def test_to_class_field(self) -> None:
        i = run(
            "class R { fn init(a, b) { this.a = a; this.to = b } }\n"
            "let r = R.new(1, 5); let v = r.to"
        )
        assert val(i) == 5


# ---------------------------------------------------------------------------
# String(instance) calls toString()
# ---------------------------------------------------------------------------

class TestStringInstanceToString:
    def test_string_calls_tostring(self) -> None:
        i = run(
            "class Vec {\n"
            "  fn init(x, y) { this.x = x; this.y = y }\n"
            "  toString() { return `(${this.x},${this.y})` }\n"
            "}\n"
            "let v = String(Vec.new(3, 4))"
        )
        assert val(i) == "(3,4)"

    def test_string_calls_tostring_no_method(self) -> None:
        """Without toString(), String() still returns some string."""
        i = run(
            "class Foo { fn init() { this.x = 1 } }\n"
            "let v = typeof String(Foo.new())"
        )
        assert val(i) == "string"

    def test_string_tostring_used_in_concatenation_context(self) -> None:
        i = run(
            "class Tag {\n"
            "  fn init(name) { this.name = name }\n"
            "  toString() { return `<${this.name}>` }\n"
            "}\n"
            "let t = Tag.new('div')\n"
            "let v = String(t)"
        )
        assert val(i) == "<div>"

    def test_string_number(self) -> None:
        i = run("let v = String(42)")
        assert val(i) == "42"

    def test_string_null(self) -> None:
        i = run("let v = String(null)")
        assert val(i) == "null"

    def test_string_undefined(self) -> None:
        i = run("let v = String(undefined)")
        assert val(i) == "undefined"

    def test_string_bool_true(self) -> None:
        i = run("let v = String(true)")
        assert val(i) == "true"

    def test_string_float_whole(self) -> None:
        i = run("let v = String(5.0)")
        assert val(i) == "5"


# ---------------------------------------------------------------------------
# dict-based iterator consumed by spread
# ---------------------------------------------------------------------------

class TestDictIteratorSpread:
    def test_simple_dict_iterator(self) -> None:
        i = run(
            "var cur = 1\n"
            "var last = 3\n"
            "let iter = {\n"
            "  next() {\n"
            "    if (cur <= last) { let val = cur; cur++; return {value: val, done: false} }\n"
            "    return {value: undefined, done: true}\n"
            "  }\n"
            "}\n"
            "let v = [...iter]"
        )
        assert val(i) == [1, 2, 3]

    def test_dict_iterator_for_of(self) -> None:
        i = run(
            "var cur = 10\n"
            "var last = 12\n"
            "let iter = {\n"
            "  next() {\n"
            "    if (cur <= last) { let val = cur; cur++; return {value: val, done: false} }\n"
            "    return {value: undefined, done: true}\n"
            "  }\n"
            "}\n"
            "let v = []\n"
            "for (let x of iter) { v.push(x) }"
        )
        assert val(i) == [10, 11, 12]

    def test_dict_iterator_empty(self) -> None:
        i = run(
            "let iter = { next() { return {value: undefined, done: true} } }\n"
            "let v = [...iter]"
        )
        assert val(i) == []

    def test_dict_iterator_single(self) -> None:
        i = run(
            "var done = false\n"
            "let iter = {\n"
            "  next() {\n"
            "    if (!done) { done = true; return {value: 42, done: false} }\n"
            "    return {value: undefined, done: true}\n"
            "  }\n"
            "}\n"
            "let v = [...iter]"
        )
        assert val(i) == [42]


# ---------------------------------------------------------------------------
# class [Symbol.iterator] iterable protocol with spread
# ---------------------------------------------------------------------------

class TestClassIterableSpread:
    def test_class_iterable_spread(self) -> None:
        src = """
class Range {
  fn init(a, b) { this.a = a; this.b = b }
  [Symbol.iterator]() {
    var cur = this.a
    var last = this.b
    return {
      next() {
        if (cur <= last) { let val = cur; cur++; return {value: val, done: false} }
        return {value: undefined, done: true}
      }
    }
  }
}
let r = Range.new(1, 5)
let v = [...r]
"""
        i = run(src)
        assert val(i) == [1, 2, 3, 4, 5]

    def test_class_iterable_for_of(self) -> None:
        src = """
class Range {
  fn init(a, b) { this.a = a; this.b = b }
  [Symbol.iterator]() {
    var cur = this.a
    var last = this.b
    return {
      next() {
        if (cur <= last) { let val = cur; cur++; return {value: val, done: false} }
        return {value: undefined, done: true}
      }
    }
  }
}
let r = Range.new(2, 4)
let v = []
for (let x of r) { v.push(x) }
"""
        i = run(src)
        assert val(i) == [2, 3, 4]

    def test_class_iterable_spread_empty(self) -> None:
        src = """
class Empty {
  fn init() {}
  [Symbol.iterator]() {
    return { next() { return {value: undefined, done: true} } }
  }
}
let v = [...Empty.new()]
"""
        i = run(src)
        assert val(i) == []

    def test_class_iterable_spread_single(self) -> None:
        src = """
class Once {
  fn init(val) { this.val = val; this.done = false }
  [Symbol.iterator]() {
    var delivered = false
    var stored = this.val
    return {
      next() {
        if (!delivered) { delivered = true; return {value: stored, done: false} }
        return {value: undefined, done: true}
      }
    }
  }
}
let v = [...Once.new(99)]
"""
        i = run(src)
        assert val(i) == [99]

    def test_class_iterable_destructuring(self) -> None:
        src = """
class Pair {
  fn init(a, b) { this.a = a; this.b = b }
  [Symbol.iterator]() {
    var items = [this.a, this.b]
    var idx = 0
    return {
      next() {
        if (idx < items.length) { let v = items[idx]; idx++; return {value: v, done: false} }
        return {value: undefined, done: true}
      }
    }
  }
}
let [x, y] = Pair.new(10, 20)
let v = x + y
"""
        i = run(src)
        assert val(i) == 30
