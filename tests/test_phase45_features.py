"""Phase 45 feature tests.

Covers:
- ``static [expr]()`` — static computed methods in class bodies
- ``Symbol.hasInstance`` in ``instanceof`` — custom instanceof behaviour
- ``get [expr]() { }`` / ``set [expr](v) { }`` — computed getter/setter in class bodies
- ``Symbol.toStringTag`` — ``obj[Symbol.toStringTag]`` calls computed getter
- ``Symbol.isConcatSpreadable`` — ``[].concat(obj)`` spreads if symbol is true
- ``Object.prototype.hasOwnProperty.call(obj, key)``
- ``Object.prototype.toString.call(obj)`` — returns ``[object Tag]``
- ``instance.hasOwnProperty(key)`` — own-property check on SpryInstance
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
# static [Symbol.hasInstance]() — static computed methods
# ---------------------------------------------------------------------------

class TestStaticComputedMethods:
    def test_static_computed_method_parsed(self) -> None:
        """static [Symbol.hasInstance]() is stored in the class _static_fields."""
        i = run(
            "class Foo {\n"
            "  static [Symbol.hasInstance](x) { return x > 5 }\n"
            "}\n"
            "let sym = Symbol.hasInstance\n"
            "let myFn = Foo[sym]\n"
            "let v = typeof myFn"
        )
        assert val(i) == "function"

    def test_symbol_has_instance_even(self) -> None:
        i = run(
            "class EvenNumber {\n"
            "  static [Symbol.hasInstance](n) {\n"
            "    return typeof n === 'number' && n % 2 === 0\n"
            "  }\n"
            "}\n"
            "let v1 = 2 instanceof EvenNumber\n"
            "let v2 = 3 instanceof EvenNumber\n"
            "let v = [v1, v2]"
        )
        assert val(i) == [True, False]

    def test_symbol_has_instance_non_number(self) -> None:
        i = run(
            "class EvenNumber {\n"
            "  static [Symbol.hasInstance](n) {\n"
            "    return typeof n === 'number' && n % 2 === 0\n"
            "  }\n"
            "}\n"
            "let v = 'hello' instanceof EvenNumber"
        )
        assert val(i) is False

    def test_symbol_has_instance_array_check(self) -> None:
        i = run(
            "class MyArray {\n"
            "  static [Symbol.hasInstance](inst) { return Array.isArray(inst) }\n"
            "}\n"
            "let v1 = [] instanceof MyArray\n"
            "let v2 = {} instanceof MyArray\n"
            "let v = [v1, v2]"
        )
        assert val(i) == [True, False]

    def test_symbol_has_instance_with_range(self) -> None:
        i = run(
            "class InRange {\n"
            "  static [Symbol.hasInstance](n) { return n >= 1 && n <= 10 }\n"
            "}\n"
            "let v1 = 5 instanceof InRange\n"
            "let v2 = 15 instanceof InRange\n"
            "let v = [v1, v2]"
        )
        assert val(i) == [True, False]

    def test_normal_instanceof_unchanged(self) -> None:
        """Normal instanceof still works when no Symbol.hasInstance is defined."""
        i = run(
            "class Dog {\n"
            "  fn init(name) { this.name = name }\n"
            "}\n"
            "let d = Dog.new('Rex')\n"
            "let v1 = d instanceof Dog\n"
            "let v2 = 42 instanceof Dog\n"
            "let v = [v1, v2]"
        )
        assert val(i) == [True, False]

    def test_static_computed_method_called_directly(self) -> None:
        i = run(
            "class Checker {\n"
            "  static [Symbol.hasInstance](x) { return x === 42 }\n"
            "}\n"
            "let sym = Symbol.hasInstance\n"
            "let result = Checker[sym](42)\n"
            "let v = result"
        )
        assert val(i) is True


# ---------------------------------------------------------------------------
# get [Symbol.toStringTag]() — computed getter
# ---------------------------------------------------------------------------

class TestComputedGetters:
    def test_get_computed_getter(self) -> None:
        i = run(
            "class Bag {\n"
            "  get [Symbol.toStringTag]() { return 'Bag' }\n"
            "}\n"
            "let b = Bag.new()\n"
            "let v = b[Symbol.toStringTag]"
        )
        assert val(i) == "Bag"

    def test_computed_getter_uses_this(self) -> None:
        i = run(
            "class Named {\n"
            "  fn init(n) { this.n = n }\n"
            "  get [Symbol.toStringTag]() { return 'Named:' + this.n }\n"
            "}\n"
            "let obj = Named.new('foo')\n"
            "let v = obj[Symbol.toStringTag]"
        )
        assert val(i) == "Named:foo"

    def test_computed_getter_string_tag(self) -> None:
        i = run(
            "class DB {\n"
            "  get [Symbol.toStringTag]() { return 'Database' }\n"
            "}\n"
            "let db = DB.new()\n"
            "let v = db[Symbol.toStringTag]"
        )
        assert val(i) == "Database"

    def test_object_prototype_tostring_with_toStringTag(self) -> None:
        i = run(
            "class Bag {\n"
            "  get [Symbol.toStringTag]() { return 'Bag' }\n"
            "}\n"
            "let b = Bag.new()\n"
            "let v = Object.prototype.toString.call(b)"
        )
        assert val(i) == "[object Bag]"

    def test_computed_setter(self) -> None:
        i = run(
            "let log = []\n"
            "class Box {\n"
            "  fn init() { this.val = 0 }\n"
            "  set [Symbol.toStringTag](x) { this.val = x }\n"
            "}\n"
            "let b = Box.new()\n"
            "b[Symbol.toStringTag] = 42\n"
            "let v = b.val"
        )
        assert val(i) == 42


# ---------------------------------------------------------------------------
# Symbol.isConcatSpreadable
# ---------------------------------------------------------------------------

class TestSymbolIsConcatSpreadable:
    def test_plain_array_concat_unchanged(self) -> None:
        i = run(
            "let v = [1, 2].concat([3, 4])"
        )
        assert val(i) == [1, 2, 3, 4]

    def test_non_array_not_spread_by_default(self) -> None:
        i = run(
            "let obj = {'0': 'a', '1': 'b', 'length': 2}\n"
            "let v = [1].concat(obj)"
        )
        result = val(i)
        # obj is not spread: [1, {...}]
        assert len(result) == 2
        assert result[0] == 1
        assert isinstance(result[1], dict)

    def test_dict_with_ics_true_is_spread(self) -> None:
        i = run(
            "let obj = {}\n"
            "obj['0'] = 'a'\n"
            "obj['1'] = 'b'\n"
            "obj['length'] = 2\n"
            "obj[Symbol.isConcatSpreadable] = true\n"
            "let v = [1].concat(obj)"
        )
        assert val(i) == [1, "a", "b"]

    def test_dict_ics_true_multiple_concat(self) -> None:
        i = run(
            "let arr = [10, 20]\n"
            "let obj = {}\n"
            "obj['0'] = 30\n"
            "obj['1'] = 40\n"
            "obj['length'] = 2\n"
            "obj[Symbol.isConcatSpreadable] = true\n"
            "let v = [].concat(arr, obj)"
        )
        assert val(i) == [10, 20, 30, 40]

    def test_dict_ics_true_empty(self) -> None:
        i = run(
            "let obj = {'length': 0}\n"
            "obj[Symbol.isConcatSpreadable] = true\n"
            "let v = [1].concat(obj)"
        )
        assert val(i) == [1]

    def test_scalar_concat_still_works(self) -> None:
        i = run(
            "let v = [1].concat(2, 3)"
        )
        assert val(i) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Object.prototype.hasOwnProperty and toString
# ---------------------------------------------------------------------------

class TestObjectPrototype:
    def test_has_own_property_present(self) -> None:
        i = run(
            "let obj = {a: 1, b: 2}\n"
            "let v = Object.prototype.hasOwnProperty.call(obj, 'a')"
        )
        assert val(i) is True

    def test_has_own_property_absent(self) -> None:
        i = run(
            "let obj = {a: 1}\n"
            "let v = Object.prototype.hasOwnProperty.call(obj, 'c')"
        )
        assert val(i) is False

    def test_has_own_on_instance(self) -> None:
        i = run(
            "class Foo { fn init() { this.x = 1 } }\n"
            "let f = Foo.new()\n"
            "let v1 = Object.prototype.hasOwnProperty.call(f, 'x')\n"
            "let v2 = Object.prototype.hasOwnProperty.call(f, 'z')\n"
            "let v = [v1, v2]"
        )
        assert val(i) == [True, False]

    def test_tostring_call_array(self) -> None:
        i = run("let v = Object.prototype.toString.call([])")
        assert val(i) == "[object Array]"

    def test_tostring_call_null(self) -> None:
        i = run("let v = Object.prototype.toString.call(null)")
        assert val(i) == "[object Null]"

    def test_tostring_call_number(self) -> None:
        i = run("let v = Object.prototype.toString.call(42)")
        assert val(i) == "[object Number]"

    def test_tostring_call_string(self) -> None:
        i = run("let v = Object.prototype.toString.call('hi')")
        assert val(i) == "[object String]"

    def test_tostring_call_boolean(self) -> None:
        i = run("let v = Object.prototype.toString.call(true)")
        assert val(i) == "[object Boolean]"

    def test_tostring_call_object(self) -> None:
        i = run("let v = Object.prototype.toString.call({})")
        assert val(i) == "[object Object]"

    def test_tostring_call_map(self) -> None:
        i = run("let v = Object.prototype.toString.call(new Map())")
        assert val(i) == "[object Map]"

    def test_tostring_call_set(self) -> None:
        i = run("let v = Object.prototype.toString.call(new Set())")
        assert val(i) == "[object Set]"

    def test_tostring_with_tag(self) -> None:
        i = run(
            "class DB {\n"
            "  get [Symbol.toStringTag]() { return 'Database' }\n"
            "}\n"
            "let db = DB.new()\n"
            "let v = Object.prototype.toString.call(db)"
        )
        assert val(i) == "[object Database]"

    def test_tostring_plain_instance(self) -> None:
        i = run(
            "class Foo { fn init() { this.x = 1 } }\n"
            "let f = Foo.new()\n"
            "let v = Object.prototype.toString.call(f)"
        )
        assert val(i) == "[object Object]"


# ---------------------------------------------------------------------------
# instance.hasOwnProperty()
# ---------------------------------------------------------------------------

class TestInstanceHasOwnProperty:
    def test_has_own_true(self) -> None:
        i = run(
            "class Foo { fn init() { this.x = 1 } }\n"
            "let f = Foo.new()\n"
            "let v = f.hasOwnProperty('x')"
        )
        assert val(i) is True

    def test_has_own_false(self) -> None:
        i = run(
            "class Foo { fn init() { this.x = 1 } }\n"
            "let f = Foo.new()\n"
            "let v = f.hasOwnProperty('y')"
        )
        assert val(i) is False

    def test_has_own_multiple_fields(self) -> None:
        i = run(
            "class Pair {\n"
            "  fn init(a, b) { this.a = a; this.b = b }\n"
            "}\n"
            "let p = Pair.new(1, 2)\n"
            "let v1 = p.hasOwnProperty('a')\n"
            "let v2 = p.hasOwnProperty('b')\n"
            "let v3 = p.hasOwnProperty('c')\n"
            "let v = [v1, v2, v3]"
        )
        assert val(i) == [True, True, False]

    def test_has_own_after_assignment(self) -> None:
        i = run(
            "class Foo { fn init() { this.x = 1 } }\n"
            "let f = Foo.new()\n"
            "f.y = 99\n"
            "let v1 = f.hasOwnProperty('x')\n"
            "let v2 = f.hasOwnProperty('y')\n"
            "let v3 = f.hasOwnProperty('z')\n"
            "let v = [v1, v2, v3]"
        )
        assert val(i) == [True, True, False]

    def test_dict_has_own_property(self) -> None:
        i = run(
            "let obj = {a: 1, b: 2}\n"
            "let v1 = obj.hasOwnProperty('a')\n"
            "let v2 = obj.hasOwnProperty('c')\n"
            "let v = [v1, v2]"
        )
        assert val(i) == [True, False]
