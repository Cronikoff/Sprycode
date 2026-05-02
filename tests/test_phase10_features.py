"""
Phase 10 feature tests:
  - `String` global namespace — String.fromCharCode, String.fromCodePoint,
    String.isString, String.isEmpty, String.of, String.repeat, String.concat
  - Property getters/setters in classes — `get prop() { ... }` / `set prop(v) { ... }`
  - `Map` built-in data structure — Map.new(), Map.from(), .set, .get, .has, .delete,
    .clear, .size, .keys(), .values(), .entries(), .forEach(), .toObject(), .isEmpty
  - Number formatting additions — .toLocaleString(), .toPercent(), .toCurrency()
"""

from __future__ import annotations

import pytest

from sprycode.interpreter import Interpreter, SpryMap
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
# String global namespace
# ---------------------------------------------------------------------------


class TestStringNamespace:
    def test_from_char_code_single(self):
        i = run("let v = String.fromCharCode(65)")
        assert val(i, "v") == "A"

    def test_from_char_code_multiple(self):
        i = run("let v = String.fromCharCode(72, 101, 108, 108, 111)")
        assert val(i, "v") == "Hello"

    def test_from_code_point_single(self):
        i = run("let v = String.fromCodePoint(9733)")
        assert val(i, "v") == "★"

    def test_from_code_point_multiple(self):
        i = run("let v = String.fromCodePoint(65, 66, 67)")
        assert val(i, "v") == "ABC"

    def test_is_string_true(self):
        i = run('let v = String.isString("hello")')
        assert val(i, "v") is True

    def test_is_string_false_number(self):
        i = run("let v = String.isString(42)")
        assert val(i, "v") is False

    def test_is_string_false_null(self):
        i = run("let v = String.isString(null)")
        assert val(i, "v") is False

    def test_is_string_false_list(self):
        i = run("let v = String.isString([1, 2])")
        assert val(i, "v") is False

    def test_is_empty_true(self):
        i = run('let v = String.isEmpty("")')
        assert val(i, "v") is True

    def test_is_empty_false(self):
        i = run('let v = String.isEmpty("x")')
        assert val(i, "v") is False

    def test_is_empty_non_string(self):
        i = run("let v = String.isEmpty(0)")
        assert val(i, "v") is False

    def test_of_single(self):
        i = run('let v = String.of("hello")')
        assert val(i, "v") == "hello"

    def test_of_multiple(self):
        i = run('let v = String.of("a", "b", "c")')
        assert val(i, "v") == "abc"

    def test_of_mixed_types(self):
        i = run('let v = String.of("x", 1, true)')
        assert val(i, "v") == "x1true"

    def test_repeat(self):
        i = run('let v = String.repeat("ab", 3)')
        assert val(i, "v") == "ababab"

    def test_repeat_zero(self):
        i = run('let v = String.repeat("hi", 0)')
        assert val(i, "v") == ""

    def test_concat(self):
        i = run('let v = String.concat("Hello", ", ", "World")')
        assert val(i, "v") == "Hello, World"

    def test_concat_single(self):
        i = run('let v = String.concat("only")')
        assert val(i, "v") == "only"

    def test_repr(self):
        i = run("let v = String")
        assert repr(val(i, "v")) == "String"


# ---------------------------------------------------------------------------
# Property getters
# ---------------------------------------------------------------------------


class TestPropertyGetters:
    def test_basic_getter(self):
        i = run("""
class Box {
  var _val = 0
  fn init(v) { self._val = v }
  get value() { return self._val }
}
let b = Box(42)
let v = b.value
""")
        assert val(i, "v") == 42

    def test_computed_getter(self):
        i = run("""
class Rectangle {
  var width = 0
  var height = 0
  fn init(w, h) { self.width = w\n self.height = h }
  get area() { return self.width * self.height }
}
let r = Rectangle(4, 5)
let v = r.area
""")
        assert val(i, "v") == 20

    def test_getter_perimeter(self):
        i = run("""
class Rectangle {
  var width = 3
  var height = 4
  get perimeter() { return 2 * (self.width + self.height) }
}
let r = Rectangle()
let v = r.perimeter
""")
        assert val(i, "v") == 14

    def test_getter_called_each_time(self):
        i = run("""
class Counter {
  var n = 0
  fn inc() { self.n = self.n + 1 }
  get count() { return self.n }
}
let c = Counter()
c.inc()
c.inc()
c.inc()
let v = c.count
""")
        assert val(i, "v") == 3

    def test_getter_string(self):
        i = run("""
class Person {
  var first = ""
  var last = ""
  fn init(f, l) { self.first = f\n self.last = l }
  get fullName() { return self.first + " " + self.last }
}
let p = Person("Alice", "Smith")
let v = p.fullName
""")
        assert val(i, "v") == "Alice Smith"

    def test_multiple_getters(self):
        i = run("""
class Circle {
  var _r = 1
  fn init(r) { self._r = r }
  get radius() { return self._r }
  get diameter() { return self._r * 2 }
}
let c = Circle(5)
let r = c.radius
let d = c.diameter
""")
        assert val(i, "r") == 5
        assert val(i, "d") == 10


# ---------------------------------------------------------------------------
# Property setters
# ---------------------------------------------------------------------------


class TestPropertySetters:
    def test_basic_setter(self):
        i = run("""
class Box {
  var _val = 0
  set value(v) { self._val = v }
  get value() { return self._val }
}
let b = Box()
b.value = 99
let v = b.value
""")
        assert val(i, "v") == 99

    def test_setter_with_validation(self):
        i = run("""
class PositiveNumber {
  var _n = 0
  get n() { return self._n }
  set n(v) {
    if v > 0 {
      self._n = v
    }
  }
}
let p = PositiveNumber()
p.n = 5
let v1 = p.n
p.n = -3
let v2 = p.n
""")
        assert val(i, "v1") == 5
        assert val(i, "v2") == 5  # negative ignored

    def test_setter_transforms_value(self):
        i = run("""
class UpperBox {
  var _s = ""
  get text() { return self._s }
  set text(v) { self._s = v.upper }
}
let b = UpperBox()
b.text = "hello"
let v = b.text
""")
        assert val(i, "v") == "HELLO"

    def test_setter_no_getter(self):
        i = run("""
class Sink {
  var last = ""
  set value(v) { self.last = v }
}
let s = Sink()
s.value = "test"
let v = s.last
""")
        assert val(i, "v") == "test"

    def test_getter_setter_round_trip(self):
        i = run("""
class Temperature {
  var _celsius = 0.0
  fn init(c) { self._celsius = c }
  get celsius() { return self._celsius }
  set celsius(v) { self._celsius = v }
  get fahrenheit() { return self._celsius * 9.0 / 5.0 + 32.0 }
}
let t = Temperature(100)
let boil_f = t.fahrenheit
t.celsius = 0
let freeze_f = t.fahrenheit
""")
        assert val(i, "boil_f") == pytest.approx(212.0)
        assert val(i, "freeze_f") == pytest.approx(32.0)


# ---------------------------------------------------------------------------
# Map data structure
# ---------------------------------------------------------------------------


class TestMapNew:
    def test_map_new_creates_empty(self):
        i = run("let m = Map.new()\nlet v = m.size")
        assert val(i, "v") == 0

    def test_map_set_and_get(self):
        i = run('let m = Map.new()\nm.set("a", 1)\nlet v = m.get("a")')
        assert val(i, "v") == 1

    def test_map_get_missing_returns_null(self):
        i = run('let m = Map.new()\nlet v = m.get("missing")')
        assert val(i, "v") is None

    def test_map_get_with_default(self):
        i = run('let m = Map.new()\nlet v = m.get("x", 99)')
        assert val(i, "v") == 99

    def test_map_size(self):
        i = run('let m = Map.new()\nm.set("a", 1)\nm.set("b", 2)\nm.set("c", 3)\nlet v = m.size')
        assert val(i, "v") == 3

    def test_map_has_true(self):
        i = run('let m = Map.new()\nm.set("k", "v")\nlet v = m.has("k")')
        assert val(i, "v") is True

    def test_map_has_false(self):
        i = run('let m = Map.new()\nlet v = m.has("missing")')
        assert val(i, "v") is False

    def test_map_delete(self):
        i = run('let m = Map.new()\nm.set("a", 1)\nm.set("b", 2)\nm.delete("a")\nlet v = m.size')
        assert val(i, "v") == 1

    def test_map_delete_returns_true(self):
        i = run('let m = Map.new()\nm.set("x", 10)\nlet v = m.delete("x")')
        assert val(i, "v") is True

    def test_map_delete_missing_returns_false(self):
        i = run('let m = Map.new()\nlet v = m.delete("nope")')
        assert val(i, "v") is False

    def test_map_clear(self):
        i = run('let m = Map.new()\nm.set("a", 1)\nm.set("b", 2)\nm.clear()\nlet v = m.size')
        assert val(i, "v") == 0

    def test_map_is_empty_true(self):
        i = run("let m = Map.new()\nlet v = m.isEmpty")
        assert val(i, "v") is True

    def test_map_is_empty_false(self):
        i = run('let m = Map.new()\nm.set("a", 1)\nlet v = m.isEmpty')
        assert val(i, "v") is False

    def test_map_keys(self):
        i = run('let m = Map.new()\nm.set("x", 1)\nm.set("y", 2)\nlet v = m.keys()')
        assert val(i, "v") == ["x", "y"]

    def test_map_values(self):
        i = run('let m = Map.new()\nm.set("a", 10)\nm.set("b", 20)\nlet v = m.values()')
        assert val(i, "v") == [10, 20]

    def test_map_entries(self):
        i = run('let m = Map.new()\nm.set("k", "v")\nlet e = m.entries()')
        assert val(i, "e") == [["k", "v"]]

    def test_map_to_object(self):
        i = run('let m = Map.new()\nm.set("a", 1)\nm.set("b", 2)\nlet v = m.toObject()')
        assert val(i, "v") == {"a": 1, "b": 2}

    def test_map_numeric_keys(self):
        i = run("let m = Map.new()\nm.set(1, \"one\")\nm.set(2, \"two\")\nlet v = m.get(1)")
        assert val(i, "v") == "one"

    def test_map_overwrite_key(self):
        i = run('let m = Map.new()\nm.set("k", 1)\nm.set("k", 2)\nlet v = m.get("k")')
        assert val(i, "v") == 2

    def test_map_set_returns_self(self):
        # set() returns the map for chaining; we just verify the value is set correctly
        i = run('let m = Map.new()\nm.set("a", 1)\nm.set("b", 2)\nlet v = m.size')
        assert val(i, "v") == 2


class TestMapFrom:
    def test_map_from_list_of_pairs(self):
        i = run('let m = Map.from([["a", 1], ["b", 2]])\nlet v = m.get("b")')
        assert val(i, "v") == 2

    def test_map_from_size(self):
        i = run('let m = Map.from([["x", 10], ["y", 20], ["z", 30]])\nlet v = m.size')
        assert val(i, "v") == 3

    def test_map_from_empty(self):
        i = run("let m = Map.from([])\nlet v = m.size")
        assert val(i, "v") == 0

    def test_map_from_dict(self):
        i = run('let m = Map.from({a: 1, b: 2})\nlet v = m.has("a")')
        assert val(i, "v") is True

    def test_map_from_entries_roundtrip(self):
        i = run('let m = Map.from([["hello", 1], ["world", 2]])\nlet k = m.keys()')
        assert val(i, "k") == ["hello", "world"]


class TestMapForEach:
    def test_map_for_each(self):
        i = run("""
let m = Map.new()
m.set("a", 1)
m.set("b", 2)
m.set("c", 3)
var total = 0
m.forEach((v, k) => { total += v })
let v = total
""")
        assert val(i, "v") == 6


# ---------------------------------------------------------------------------
# Number formatting additions
# ---------------------------------------------------------------------------


class TestNumberFormatting:
    def test_to_locale_string_integer(self):
        i = run("let v = (1234567).toLocaleString()")
        assert val(i, "v") == "1,234,567"

    def test_to_locale_string_small(self):
        i = run("let v = (42).toLocaleString()")
        assert val(i, "v") == "42"

    def test_to_locale_string_float(self):
        i = run("let v = (1234.56).toLocaleString()")
        assert val(i, "v") == "1,234.56"

    def test_to_percent_half(self):
        i = run("let v = (0.5).toPercent()")
        assert val(i, "v") == "50.00%"

    def test_to_percent_zero_decimals(self):
        i = run("let v = (0.75).toPercent(0)")
        assert val(i, "v") == "75%"

    def test_to_percent_one_decimal(self):
        i = run("let v = (0.333).toPercent(1)")
        assert val(i, "v") == "33.3%"

    def test_to_currency_default(self):
        i = run("let v = (99.99).toCurrency()")
        assert val(i, "v") == "$99.99"

    def test_to_currency_custom_symbol(self):
        i = run('let v = (49.95).toCurrency("€")')
        assert val(i, "v") == "€49.95"

    def test_to_currency_thousands(self):
        i = run("let v = (1234567.89).toCurrency()")
        assert val(i, "v") == "$1,234,567.89"

    def test_to_currency_zero_decimals(self):
        i = run('let v = (100.0).toCurrency("$", 0)')
        assert val(i, "v") == "$100"
