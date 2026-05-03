"""Phase 39 feature tests.

Covers:
- ``switch`` case body: semicolons between statements are now accepted
  (``case 1: v = 1; break; case 2:`` no longer raises a ParseError)
- ``switch`` no-fallthrough semantics preserved: each case runs independently
  (existing SpryCode semantics, NOT JS fallthrough)
- ``this`` binding in plain object-literal methods: ``{ greet() { return this.x } }``
  now has ``this`` pointing to the containing dict
- Object-literal getter/setter with ``this``:
  ``{ get x() { return this._x }, set x(v) { this._x = v } }``
- ``str.split("")`` → list of characters (JS: ``"hello".split("") → ["h","e","l","l","o"]``)
- ``Array(n)`` / ``new Array(n)`` callable: single-int arg creates a sparse list of
  ``n`` ``None`` values; multiple args create a list of those values
- Computed method shorthand in object literals: ``{ [key]() { return x } }``
- ``undefined`` as a distinct sentinel value (``SPRY_UNDEFINED``) separate from ``null``/``None``:
  - ``String(undefined)`` → ``'undefined'``
  - ``typeof undefined`` → ``'undefined'``
  - ``undefined == null`` → ``True`` (JS loose equality)
  - ``undefined === null`` → ``False`` (strict equality)
  - ``undefined`` is falsy
"""

from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import Interpreter, SPRY_UNDEFINED
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


def val(source: str, name: str = "v") -> Any:
    return run(source).globals.get(name)


# ---------------------------------------------------------------------------
# switch — semicolons in case body
# ---------------------------------------------------------------------------

class TestSwitchSemicolons:
    def test_break_after_semicoloned_expr(self):
        src = "var v = 0; switch (2) { case 1: v = 1; break; case 2: v = 2; break; default: v = 0 }"
        assert val(src) == 2

    def test_break_after_multiple_stmts(self):
        src = "var v = 0; var w = 0; switch (1) { case 1: v = 10; w = 20; break; case 2: v = 99 }"
        i = run(src)
        assert i.globals.get("v") == 10
        assert i.globals.get("w") == 20

    def test_no_case_match_runs_default(self):
        src = "var v = 0; switch (5) { case 1: v = 1; break; case 2: v = 2; break; default: v = 99 }"
        assert val(src) == 99

    def test_string_case_semicolons(self):
        src = "var v = ''; switch ('b') { case 'a': v = 'A'; break; case 'b': v = 'B'; break; default: v = 'D' }"
        assert val(src) == "B"

    def test_default_semicolons(self):
        src = "var v = 0; switch (9) { case 1: v = 1; break; default: v = 999; break }"
        assert val(src) == 999

    def test_no_match_no_default(self):
        src = "var v = 0; switch (9) { case 1: v = 1; break; case 2: v = 2; break }"
        assert val(src) == 0

    def test_case_multiple_stmts_semicolons(self):
        src = """
var a = 0; var b = 0
switch (2) {
  case 1: a = 1; b = 1; break
  case 2: a = 2; b = 3; break
  default: a = 9
}
"""
        i = run(src)
        assert i.globals.get("a") == 2
        assert i.globals.get("b") == 3


# ---------------------------------------------------------------------------
# switch — no-fallthrough semantics preserved
# ---------------------------------------------------------------------------

class TestSwitchNoFallthrough:
    def test_first_match_wins(self):
        # Case 1 matches; case 2 should NOT execute (no fallthrough)
        src = "var v = 0; switch (1) { case 1: v = 10; case 2: v = 20 }"
        assert val(src) == 10

    def test_break_stops_further_cases(self):
        src = "var v = 0; switch (1) { case 1: v = 10; break; case 2: v = 20 }"
        assert val(src) == 10

    def test_only_matching_case_runs(self):
        src = "var hits = []; switch (2) { case 1: hits.push(1); case 2: hits.push(2); case 3: hits.push(3) }; let v = hits"
        assert val(src) == [2]

    def test_default_only_when_no_match(self):
        src = "var v = 0; switch (3) { case 1: v = 1; case 2: v = 2; default: v = 99 }"
        assert val(src) == 99

    def test_string_match(self):
        src = "var v = ''; switch ('b') { case 'a': v = 'got-a'; case 'b': v = 'got-b'; case 'c': v = 'got-c' }"
        assert val(src) == "got-b"


# ---------------------------------------------------------------------------
# this binding in object-literal methods
# ---------------------------------------------------------------------------

class TestObjectLiteralThis:
    def test_method_reads_this(self):
        src = "let obj = {x: 42, get() { return this.x } }; let v = obj.get()"
        assert val(src) == 42

    def test_method_writes_this(self):
        src = "let obj = {x: 0, inc() { this.x = this.x + 1 } }; obj.inc(); let v = obj.x"
        assert val(src) == 1

    def test_method_multiple_calls(self):
        src = "let obj = {n: 0, inc() { this.n = this.n + 1; return this.n } }; obj.inc(); obj.inc(); let v = obj.inc()"
        assert val(src) == 3

    def test_method_returns_this_field(self):
        src = "let obj = {name: 'Alice', greet() { return 'Hello, ' + this.name } }; let v = obj.greet()"
        assert val(src) == "Hello, Alice"

    def test_method_passes_this_to_nested(self):
        src = "let obj = {x: 10, y: 20, sum() { return this.x + this.y } }; let v = obj.sum()"
        assert val(src) == 30

    def test_method_with_params_and_this(self):
        src = "let obj = {base: 5, add(n) { return this.base + n } }; let v = obj.add(3)"
        assert val(src) == 8

    def test_method_chained_via_return_this(self):
        src = """
let counter = {
  n: 0,
  inc() { this.n = this.n + 1; return this },
  val() { return this.n }
}
let v = counter.inc().inc().val()
"""
        assert val(src) == 2

    def test_shorthand_no_args(self):
        src = "let obj = { hello() { return 'world' } }; let v = obj.hello()"
        assert val(src) == "world"

    def test_shorthand_rest_param(self):
        src = "let obj = { sum(...args) { var t = 0; for (let x of args) { t = t + x }; return t } }; let v = obj.sum(1, 2, 3)"
        assert val(src) == 6


# ---------------------------------------------------------------------------
# Object-literal getter / setter with this
# ---------------------------------------------------------------------------

class TestObjectLiteralGetterSetter:
    def test_getter_reads_this(self):
        src = "let obj = { _x: 7, get x() { return this._x } }; let v = obj.x"
        assert val(src) == 7

    def test_setter_writes_this(self):
        src = "let obj = { _x: 0, get x() { return this._x }, set x(v) { this._x = v } }; obj.x = 42; let v = obj.x"
        assert val(src) == 42

    def test_setter_transforms_value(self):
        src = "let obj = { _n: 0, get n() { return this._n }, set n(v) { this._n = v * 2 } }; obj.n = 5; let v = obj.n"
        assert val(src) == 10

    def test_getter_computed(self):
        src = "let obj = { a: 3, b: 4, get hyp() { return this.a * this.a + this.b * this.b } }; let v = obj.hyp"
        assert val(src) == 25


# ---------------------------------------------------------------------------
# str.split("") → list of characters
# ---------------------------------------------------------------------------

class TestStrSplitEmpty:
    def test_split_empty_single_char(self):
        assert val('let v = "a".split("")') == ["a"]

    def test_split_empty_hello(self):
        assert val('let v = "hello".split("")') == ["h", "e", "l", "l", "o"]

    def test_split_empty_with_limit(self):
        assert val('let v = "hello".split("", 3)') == ["h", "e", "l"]

    def test_split_nonempty_still_works(self):
        assert val('let v = "a,b,c".split(",")') == ["a", "b", "c"]

    def test_split_empty_unicode(self):
        assert val('let v = "abc".split("")') == ["a", "b", "c"]

    def test_split_empty_string_input(self):
        assert val('let v = "".split("")') == []


# ---------------------------------------------------------------------------
# Array(n) / new Array(n)
# ---------------------------------------------------------------------------

class TestArrayConstructor:
    def test_array_n_creates_sparse(self):
        assert val("let v = Array(3)") == [None, None, None]

    def test_array_n_zero(self):
        assert val("let v = Array(0)") == []

    def test_array_n_one(self):
        assert val("let v = Array(1)") == [None]

    def test_array_n_length(self):
        assert val("let v = Array(5).length") == 5

    def test_array_multiple_args(self):
        assert val("let v = Array(1, 2, 3)") == [1, 2, 3]

    def test_array_string_args(self):
        assert val('let v = Array("a", "b")') == ["a", "b"]

    def test_new_array_n(self):
        assert val("let v = new Array(3)") == [None, None, None]

    def test_new_array_multiple_args(self):
        assert val("let v = new Array(1, 2, 3)") == [1, 2, 3]

    def test_array_n_fill(self):
        assert val("let v = Array(3).fill(0)") == [0, 0, 0]

    def test_array_n_fill_slice(self):
        result = val("let v = Array(5).fill(7)")
        assert result == [7, 7, 7, 7, 7]


# ---------------------------------------------------------------------------
# Computed method shorthand in object literals
# ---------------------------------------------------------------------------

class TestComputedMethodShorthand:
    def test_simple_method(self):
        src = "let key = 'greet'; let obj = { [key]() { return 'hello' } }; let v = obj.greet()"
        assert val(src) == "hello"

    def test_method_with_args(self):
        src = "let k = 'add'; let obj = { [k](a, b) { return a + b } }; let v = obj.add(1, 2)"
        assert val(src) == 3

    def test_method_with_this(self):
        src = "let k = 'getValue'; let obj = { _v: 42, [k]() { return this._v } }; let v = obj.getValue()"
        assert val(src) == 42

    def test_multiple_computed_methods(self):
        src = """
let a = 'foo'
let b = 'bar'
let obj = {
  [a](x) { return x * 2 },
  [b](x) { return x + 10 }
}
let v = obj.foo(3) + obj.bar(5)
"""
        assert val(src) == 21

    def test_computed_key_expr(self):
        src = "let obj = { ['pre' + 'fix']() { return 99 } }; let v = obj.prefix()"
        assert val(src) == 99

    def test_mixed_computed_and_literal(self):
        src = "let k = 'dyn'; let obj = { static: 1, [k]() { return 2 } }; let v = obj.static + obj.dyn()"
        assert val(src) == 3


# ---------------------------------------------------------------------------
# undefined sentinel
# ---------------------------------------------------------------------------

class TestUndefinedSentinel:
    def test_string_undefined(self):
        assert val("let v = String(undefined)") == "undefined"

    def test_typeof_undefined(self):
        assert val("let v = typeof undefined") == "undefined"

    def test_undefined_eq_null(self):
        assert val("let v = undefined == null") is True

    def test_undefined_eq_undefined(self):
        assert val("let v = undefined == undefined") is True

    def test_undefined_neq_zero(self):
        assert val("let v = undefined == 0") is False

    def test_undefined_neq_false(self):
        assert val("let v = undefined == false") is False

    def test_undefined_neq_empty_str(self):
        assert val('let v = undefined == ""') is False

    def test_undefined_strict_neq_null(self):
        assert val("let v = undefined === null") is False

    def test_undefined_strict_eq_undefined(self):
        assert val("let v = undefined === undefined") is True

    def test_undefined_is_falsy(self):
        src = "var v = 'yes'; if (undefined) { v = 'no' }; let _ = v"
        assert run(src).globals.get("_") == "yes"

    def test_undefined_in_ternary(self):
        src = "let v = undefined ? 'truthy' : 'falsy'"
        assert val(src) == "falsy"

    def test_null_still_string_null(self):
        assert val("let v = String(null)") == "null"

    def test_typeof_null(self):
        assert val("let v = typeof null") == "Null"

    def test_globalthis_undefined_typeof(self):
        assert val("let v = typeof globalThis.undefined") == "undefined"

    def test_globalthis_undefined_eq_null(self):
        assert val("let v = globalThis.undefined == null") is True
