"""
Phase 7 feature tests:
  - ??= null-coalescing assignment
  - mixin keyword for class composition
  - JSON global namespace (JSON.stringify, JSON.parse)
  - Array global namespace (Array.isArray, Array.of)
  - Object global namespace (Object.keys, Object.values, Object.assign, Object.entries, Object.fromEntries)
  - Number global namespace (Number.isInteger, Number.isNaN, Number.isFinite, Number.parseInt, Number.parseFloat)
  - fromEntries() / merge() global functions
  - parseInt() / parseFloat() global functions
  - list.at(n) with negative index
  - math.random() / math.randomInt() / math.shuffle() / math.sample()
  - format() printf-style (%05d, %.2f, %s)
  - string.matchAll() with /pattern/flags and plain pattern
  - _parse_regex_pattern helper (via match/matchAll/search)
  - Number type tokens usable as identifiers (Number.isInteger, etc.)
"""

from __future__ import annotations

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


def val(i: Interpreter, name: str):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# ??= null-coalescing assignment
# ---------------------------------------------------------------------------


class TestNullCoalescingAssignment:
    def test_assigns_when_null(self):
        i = run("var x = null\nx ??= 5\nlet v = x")
        assert val(i, "v") == 5

    def test_noop_when_value_set(self):
        i = run("var x = 10\nx ??= 5\nlet v = x")
        assert val(i, "v") == 10

    def test_assigns_with_expression(self):
        i = run("var x = null\nx ??= 3 + 2\nlet v = x")
        assert val(i, "v") == 5

    def test_assigns_string(self):
        i = run('var x = null\nx ??= "hello"\nlet v = x')
        assert val(i, "v") == "hello"

    def test_noop_with_zero(self):
        # 0 is NOT null, so ??= should not overwrite
        i = run("var x = 0\nx ??= 99\nlet v = x")
        assert val(i, "v") == 0

    def test_noop_with_false(self):
        i = run("var x = false\nx ??= true\nlet v = x")
        assert val(i, "v") is False

    def test_noop_with_empty_string(self):
        i = run('var x = ""\nx ??= "default"\nlet v = x')
        assert val(i, "v") == ""

    def test_chained_usage(self):
        i = run("var a = null\nvar b = null\na ??= 1\nb ??= 2\nlet v = a + b")
        assert val(i, "v") == 3

    def test_in_function(self):
        src = """fn ensure(default_val) {
  var result = null
  result ??= default_val
  return result
}
let v = ensure(42)"""
        i = run(src)
        assert val(i, "v") == 42

    def test_does_not_affect_existing(self):
        src = """fn ensure(default_val) {
  var result = null
  result ??= default_val
  return result
}
let v = ensure(7)"""
        i = run(src)
        assert val(i, "v") == 7


# ---------------------------------------------------------------------------
# mixin keyword
# ---------------------------------------------------------------------------


class TestMixin:
    def test_basic_mixin(self):
        src = """class Mixin {
  fn hello() { return "from mixin" }
}
class Foo mixin Mixin {}
let f = Foo.new()
let v = f.hello()"""
        i = run(src)
        assert val(i, "v") == "from mixin"

    def test_mixin_does_not_override_class_method(self):
        src = """class Mixin {
  fn greet() { return "mixin" }
}
class Foo mixin Mixin {
  fn greet() { return "class" }
}
let f = Foo.new()
let v = f.greet()"""
        i = run(src)
        assert val(i, "v") == "class"

    def test_mixin_field_available(self):
        src = """class DefaultFields {
  var score = 100
}
class Player mixin DefaultFields {}
let p = Player.new()
let v = p.score"""
        i = run(src)
        assert val(i, "v") == 100

    def test_mixin_with_class_own_method(self):
        src = """class Serializable {
  fn serialize() { return "serialized" }
}
class User mixin Serializable {
  fn greet() { return "hello" }
}
let u = User.new()
let v = u.serialize() + " " + u.greet()"""
        i = run(src)
        assert val(i, "v") == "serialized hello"

    def test_mixin_and_extends(self):
        src = """class Mixin {
  fn mixinMethod() { return "mixin" }
}
class Base {
  fn baseMethod() { return "base" }
}
class Child extends Base mixin Mixin {}
let c = Child.new()
let v = c.baseMethod() + c.mixinMethod()"""
        i = run(src)
        assert val(i, "v") == "basemixin"


# ---------------------------------------------------------------------------
# JSON global namespace
# ---------------------------------------------------------------------------


class TestJSONNamespace:
    def test_stringify_dict(self):
        i = run('let v = JSON.stringify({a: 1, b: 2})')
        import json
        assert json.loads(val(i, "v")) == {"a": 1, "b": 2}

    def test_stringify_list(self):
        i = run('let v = JSON.stringify([1, 2, 3])')
        assert val(i, "v") == "[1,2,3]"

    def test_stringify_string(self):
        i = run('let v = JSON.stringify("hello")')
        assert val(i, "v") == '"hello"'

    def test_parse_object(self):
        i = run('let v = JSON.parse("{\\"x\\": 42}")')
        assert val(i, "v") == {"x": 42}

    def test_parse_list(self):
        i = run('let v = JSON.parse("[1, 2, 3]")')
        assert val(i, "v") == [1, 2, 3]

    def test_parse_number(self):
        i = run('let v = JSON.parse("42")')
        assert val(i, "v") == 42

    def test_roundtrip(self):
        src = """let original = {name: "Alice", age: 30}
let serialized = JSON.stringify(original)
let restored = JSON.parse(serialized)
let v = restored"""
        i = run(src)
        assert val(i, "v") == {"name": "Alice", "age": 30}


# ---------------------------------------------------------------------------
# Array global namespace
# ---------------------------------------------------------------------------


class TestArrayNamespace:
    def test_isArray_list(self):
        i = run('let v = Array.isArray([1, 2, 3])')
        assert val(i, "v") is True

    def test_isArray_string(self):
        i = run('let v = Array.isArray("hello")')
        assert val(i, "v") is False

    def test_isArray_number(self):
        i = run('let v = Array.isArray(42)')
        assert val(i, "v") is False

    def test_isArray_dict(self):
        i = run('let v = Array.isArray({a: 1})')
        assert val(i, "v") is False

    def test_of(self):
        i = run('let v = Array.of(1, 2, 3)')
        assert val(i, "v") == [1, 2, 3]

    def test_of_single(self):
        i = run('let v = Array.of(42)')
        assert val(i, "v") == [42]

    def test_of_empty(self):
        i = run('let v = Array.of()')
        assert val(i, "v") == []


# ---------------------------------------------------------------------------
# Object global namespace
# ---------------------------------------------------------------------------


class TestObjectNamespace:
    def test_keys(self):
        i = run('let v = Object.keys({a: 1, b: 2, c: 3})')
        assert sorted(val(i, "v")) == ["a", "b", "c"]

    def test_values(self):
        i = run('let v = Object.values({a: 1, b: 2, c: 3})')
        assert sorted(val(i, "v")) == [1, 2, 3]

    def test_entries(self):
        i = run('let v = Object.entries({x: 10})')
        assert val(i, "v") == [["x", 10]]

    def test_fromEntries(self):
        i = run('let v = Object.fromEntries([["a", 1], ["b", 2]])')
        assert val(i, "v") == {"a": 1, "b": 2}

    def test_assign_two_dicts(self):
        i = run('let v = Object.assign({a: 1}, {b: 2})')
        assert val(i, "v") == {"a": 1, "b": 2}

    def test_assign_override(self):
        i = run('let v = Object.assign({a: 1, b: 0}, {b: 2})')
        assert val(i, "v") == {"a": 1, "b": 2}

    def test_assign_three_dicts(self):
        i = run('let v = Object.assign({a: 1}, {b: 2}, {c: 3})')
        assert val(i, "v") == {"a": 1, "b": 2, "c": 3}

    def test_hasOwn_present(self):
        i = run('let v = Object.hasOwn({a: 1}, "a")')
        assert val(i, "v") is True

    def test_hasOwn_absent(self):
        i = run('let v = Object.hasOwn({a: 1}, "b")')
        assert val(i, "v") is False


# ---------------------------------------------------------------------------
# Number global namespace
# ---------------------------------------------------------------------------


class TestNumberNamespace:
    def test_isInteger_int(self):
        i = run('let v = Number.isInteger(5)')
        assert val(i, "v") is True

    def test_isInteger_float_whole(self):
        i = run('let v = Number.isInteger(5.0)')
        assert val(i, "v") is True

    def test_isInteger_float_frac(self):
        i = run('let v = Number.isInteger(5.1)')
        assert val(i, "v") is False

    def test_isFinite_regular(self):
        i = run('let v = Number.isFinite(42)')
        assert val(i, "v") is True

    def test_isFinite_false_for_bool(self):
        # booleans are not considered finite numbers
        i = run('let v = Number.isFinite(true)')
        assert val(i, "v") is False

    def test_parseInt_basic(self):
        i = run('let v = Number.parseInt("42")')
        assert val(i, "v") == 42

    def test_parseInt_hex(self):
        i = run('let v = Number.parseInt("ff", 16)')
        assert val(i, "v") == 255

    def test_parseFloat_basic(self):
        i = run('let v = Number.parseFloat("3.14")')
        assert abs(val(i, "v") - 3.14) < 1e-9

    def test_parseFloat_scientific(self):
        i = run('let v = Number.parseFloat("1e3")')
        assert val(i, "v") == 1000.0

    def test_toFixed(self):
        i = run('let v = Number.toFixed(3.14159, 2)')
        assert val(i, "v") == "3.14"


# ---------------------------------------------------------------------------
# Global helper functions
# ---------------------------------------------------------------------------


class TestGlobalHelpers:
    def test_fromEntries(self):
        i = run('let v = fromEntries([["a", 1], ["b", 2]])')
        assert val(i, "v") == {"a": 1, "b": 2}

    def test_merge_two(self):
        i = run('let v = merge({a: 1}, {b: 2})')
        assert val(i, "v") == {"a": 1, "b": 2}

    def test_merge_override(self):
        i = run('let v = merge({a: 1, b: 0}, {b: 2})')
        assert val(i, "v") == {"a": 1, "b": 2}

    def test_merge_three(self):
        i = run('let v = merge({a: 1}, {b: 2}, {c: 3})')
        assert val(i, "v") == {"a": 1, "b": 2, "c": 3}

    def test_parseInt_global(self):
        i = run('let v = parseInt("42")')
        assert val(i, "v") == 42

    def test_parseInt_with_whitespace(self):
        i = run('let v = parseInt("  42  ")')
        assert val(i, "v") == 42

    def test_parseFloat_global(self):
        i = run('let v = parseFloat("3.14")')
        assert abs(val(i, "v") - 3.14) < 1e-9


# ---------------------------------------------------------------------------
# list.at(n) with negative index
# ---------------------------------------------------------------------------


class TestListAt:
    def test_at_zero(self):
        i = run('let v = [10, 20, 30].at(0)')
        assert val(i, "v") == 10

    def test_at_positive(self):
        i = run('let v = [10, 20, 30].at(2)')
        assert val(i, "v") == 30

    def test_at_minus_one(self):
        i = run('let v = [10, 20, 30].at(-1)')
        assert val(i, "v") == 30

    def test_at_minus_two(self):
        i = run('let v = [10, 20, 30].at(-2)')
        assert val(i, "v") == 20

    def test_at_minus_three(self):
        i = run('let v = [10, 20, 30].at(-3)')
        assert val(i, "v") == 10

    def test_at_out_of_bounds(self):
        i = run('let v = [1, 2, 3].at(10)')
        assert val(i, "v") is None

    def test_at_negative_out_of_bounds(self):
        i = run('let v = [1, 2, 3].at(-10)')
        assert val(i, "v") is None

    def test_at_with_variable(self):
        i = run('let lst = [10, 20, 30]\nlet idx = -1\nlet v = lst.at(idx)')
        assert val(i, "v") == 30


# ---------------------------------------------------------------------------
# math.random() and related
# ---------------------------------------------------------------------------


class TestMathRandom:
    def test_random_returns_float(self):
        i = run('let v = typeof math.random()')
        assert val(i, "v") == "Float"

    def test_random_in_range(self):
        src = """var passed = true
var i = 0
while i < 20 {
  let r = math.random()
  if r < 0.0 { passed = false }
  if r >= 1.0 { passed = false }
  i = i + 1
}
let v = passed"""
        i = run(src)
        assert val(i, "v") is True

    def test_randomInt_fixed(self):
        i = run('let v = math.randomInt(7, 7)')
        assert val(i, "v") == 7

    def test_randomInt_in_range(self):
        src = """var passed = true
var i = 0
while i < 30 {
  let r = math.randomInt(1, 6)
  if r < 1 { passed = false }
  if r > 6 { passed = false }
  i = i + 1
}
let v = passed"""
        i = run(src)
        assert val(i, "v") is True

    def test_shuffle_returns_list(self):
        i = run('let v = math.shuffle([1, 2, 3, 4, 5])')
        result = val(i, "v")
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3, 4, 5]

    def test_shuffle_preserves_elements(self):
        src = """let lst = [1, 2, 3, 4, 5]
let shuffled = math.shuffle(lst)
let v = len(shuffled)"""
        i = run(src)
        assert val(i, "v") == 5

    def test_sample_count(self):
        i = run('let v = len(math.sample([1, 2, 3, 4, 5], 3))')
        assert val(i, "v") == 3

    def test_sample_single(self):
        i = run('let v = len(math.sample([1, 2, 3, 4, 5], 1))')
        assert val(i, "v") == 1


# ---------------------------------------------------------------------------
# format() with printf and positional styles
# ---------------------------------------------------------------------------


class TestFormat:
    def test_printf_d(self):
        i = run('let v = format("%d", 42)')
        assert val(i, "v") == "42"

    def test_printf_05d(self):
        i = run('let v = format("%05d", 42)')
        assert val(i, "v") == "00042"

    def test_printf_f(self):
        i = run('let v = format("%.2f", 3.14159)')
        assert val(i, "v") == "3.14"

    def test_printf_s(self):
        i = run('let v = format("Hello, %s!", "world")')
        assert val(i, "v") == "Hello, world!"

    def test_printf_multiple(self):
        i = run('let v = format("%s is %d years old", "Alice", 30)')
        assert val(i, "v") == "Alice is 30 years old"

    def test_positional_single(self):
        i = run('let v = format("Hello, {}!", "world")')
        assert val(i, "v") == "Hello, world!"

    def test_positional_multiple(self):
        i = run('let v = format("{} + {} = {}", 1, 2, 3)')
        assert val(i, "v") == "1 + 2 = 3"

    def test_no_args(self):
        i = run('let v = format("no placeholders")')
        assert val(i, "v") == "no placeholders"

    def test_printf_x(self):
        i = run('let v = format("%x", 255)')
        assert val(i, "v") == "ff"


# ---------------------------------------------------------------------------
# string.matchAll() with regex
# ---------------------------------------------------------------------------


class TestStringMatchAll:
    def test_matchAll_with_flags(self):
        i = run('let v = "hello world foo".matchAll("/[a-z]+/g")')
        result = val(i, "v")
        # Each match is [full_match, ...groups]
        assert [m[0] for m in result] == ["hello", "world", "foo"]

    def test_matchAll_plain_pattern(self):
        i = run('let v = "hello world".matchAll("[a-z]+")')
        result = val(i, "v")
        assert [m[0] for m in result] == ["hello", "world"]

    def test_matchAll_with_groups(self):
        i = run('let v = "2024-01-15".matchAll("/(\\\\d{4})-(\\\\d{2})-(\\\\d{2})/")')
        result = val(i, "v")
        assert len(result) == 1
        assert result[0][0] == "2024-01-15"
        assert result[0][1] == "2024"

    def test_matchAll_case_insensitive(self):
        i = run('let v = "Hello WORLD".matchAll("/[a-z]+/i")')
        result = val(i, "v")
        assert len(result) == 2

    def test_match_with_flags(self):
        i = run('let v = "Hello World".match("/[a-z]+/gi")')
        result = val(i, "v")
        assert result == ["Hello", "World"]

    def test_search_with_flags(self):
        i = run('let v = "hello world".search("/world/")')
        assert val(i, "v") == 6

    def test_search_not_found(self):
        i = run('let v = "hello world".search("/xyz/")')
        assert val(i, "v") == -1
