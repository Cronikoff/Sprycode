"""Tests for Phase 52 features:
- new Date(args) constructor: no-args, timestamp, string, components
- Class.prototype: SpryClassPrototype identity, Object.getPrototypeOf(instance)
- JSON.stringify array replacer: key filtering
- yield* return value: the inner generator's return value is yielded by the expression
"""
from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str = "v") -> Any:
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# new Date() constructor
# ---------------------------------------------------------------------------

class TestDateConstructor:
    def test_new_date_no_args_type(self) -> None:
        i = run("let d = new Date(); let v = typeof d.getTime()")
        assert val(i) == "number"

    def test_new_date_no_args_getfullyear(self) -> None:
        import datetime
        i = run("let d = new Date(); let v = d.getFullYear()")
        assert val(i) == datetime.datetime.now().year

    def test_new_date_unix_ms_zero(self) -> None:
        i = run("let d = new Date(0); let v = d.getFullYear()")
        assert val(i) == 1970

    def test_new_date_unix_ms_nonzero(self) -> None:
        i = run("let d = new Date(1000); let v = d.getTime()")
        assert val(i) == 1000.0

    def test_new_date_string_iso(self) -> None:
        i = run("let d = new Date('2024-03-15'); let v = [d.getFullYear(), d.getMonth(), d.getDate()]")
        assert val(i) == [2024, 2, 15]

    def test_new_date_string_iso_month_0indexed(self) -> None:
        # JS getMonth() is 0-indexed: January=0, December=11
        i = run("let d = new Date('2024-01-01'); let v = d.getMonth()")
        assert val(i) == 0

    def test_new_date_components_year_month_day(self) -> None:
        # JS: new Date(2024, 2, 15) = year=2024, month=March(2), day=15
        i = run("let d = new Date(2024, 2, 15); let v = [d.getFullYear(), d.getMonth(), d.getDate()]")
        assert val(i) == [2024, 2, 15]

    def test_new_date_components_january(self) -> None:
        # JS month 0 = January
        i = run("let d = new Date(2024, 0, 1); let v = d.getMonth()")
        assert val(i) == 0

    def test_new_date_gettime_components(self) -> None:
        i = run("let d = new Date(2024, 0, 1); let v = d.getTime()")
        assert isinstance(val(i), (int, float))
        assert val(i) > 0

    def test_new_date_isostring(self) -> None:
        i = run("let d = new Date('2024-03-15'); let v = d.toISOString()")
        assert "2024-03-15" in str(val(i))

    def test_new_date_gethours(self) -> None:
        i = run("let d = new Date(2024, 0, 1); let v = d.getHours()")
        assert val(i) == 0

    def test_new_date_with_time_components(self) -> None:
        i = run("let d = new Date(2024, 0, 1, 12, 30, 45); let v = [d.getHours(), d.getMinutes(), d.getSeconds()]")
        assert val(i) == [12, 30, 45]

    def test_date_now_returns_number(self) -> None:
        i = run("let v = typeof Date.now()")
        assert val(i) == "number"

    def test_date_parse_iso(self) -> None:
        i = run("let v = typeof Date.parse('2024-01-01')")
        assert val(i) == "number"


# ---------------------------------------------------------------------------
# Class.prototype
# ---------------------------------------------------------------------------

class TestClassPrototype:
    def test_class_prototype_is_object(self) -> None:
        i = run("class Foo {}; let v = typeof Foo.prototype")
        assert val(i) == "object"

    def test_prototype_identity_same_class(self) -> None:
        i = run("""
class Dog {}
let p1 = Dog.prototype
let p2 = Dog.prototype
let v = p1 === p2
""")
        assert val(i) is True

    def test_getprototypeof_basic(self) -> None:
        i = run("""
class Dog {}
let d = new Dog()
let v = Object.getPrototypeOf(d) === Dog.prototype
""")
        assert val(i) is True

    def test_getprototypeof_different_classes(self) -> None:
        i = run("""
class Cat {}
class Dog {}
let d = new Dog()
let v = Object.getPrototypeOf(d) === Cat.prototype
""")
        assert val(i) is False

    def test_getprototypeof_inheritance_direct(self) -> None:
        i = run("""
class Animal {}
class Dog extends Animal {}
let d = new Dog()
let v = [
  Object.getPrototypeOf(d) === Dog.prototype,
  Object.getPrototypeOf(d) === Animal.prototype
]
""")
        assert val(i) == [True, False]

    def test_prototype_instances_share_same(self) -> None:
        i = run("""
class Cat {}
let c1 = new Cat()
let c2 = new Cat()
let v = Object.getPrototypeOf(c1) === Object.getPrototypeOf(c2)
""")
        assert val(i) is True

    def test_prototype_different_instances_different_classes(self) -> None:
        i = run("""
class A {}
class B {}
let a = new A()
let b = new B()
let v = Object.getPrototypeOf(a) === Object.getPrototypeOf(b)
""")
        assert val(i) is False

    def test_class_prototype_toString(self) -> None:
        i = run("""
class MyClass {}
let v = MyClass.prototype.toString()
""")
        # Should not throw; toString returns something string-like
        assert val(i) is not None


# ---------------------------------------------------------------------------
# JSON.stringify array replacer
# ---------------------------------------------------------------------------

class TestJsonStringifyReplacer:
    def test_array_replacer_filters_keys(self) -> None:
        i = run("let v = JSON.stringify({a: 1, b: 2, c: 3}, ['a', 'c'])")
        import json
        result = json.loads(val(i))
        assert result == {"a": 1, "c": 3}
        assert "b" not in result

    def test_array_replacer_single_key(self) -> None:
        i = run("let v = JSON.stringify({x: 10, y: 20, z: 30}, ['x'])")
        import json
        result = json.loads(val(i))
        assert result == {"x": 10}

    def test_array_replacer_all_keys(self) -> None:
        i = run("let v = JSON.stringify({a: 1, b: 2}, ['a', 'b'])")
        import json
        result = json.loads(val(i))
        assert result == {"a": 1, "b": 2}

    def test_null_replacer_returns_all(self) -> None:
        i = run("let v = JSON.stringify({a: 1, b: 2}, null)")
        import json
        result = json.loads(val(i))
        assert result == {"a": 1, "b": 2}

    def test_no_replacer_returns_all(self) -> None:
        i = run("let v = JSON.stringify({a: 1, b: 2})")
        import json
        result = json.loads(val(i))
        assert result == {"a": 1, "b": 2}

    def test_array_replacer_with_indent(self) -> None:
        i = run("let v = JSON.stringify({a: 1, b: 2, c: 3}, ['a', 'c'], 2)")
        import json
        result = json.loads(val(i))
        assert result == {"a": 1, "c": 3}

    def test_empty_array_replacer(self) -> None:
        i = run("let v = JSON.stringify({a: 1, b: 2}, [])")
        import json
        result = json.loads(val(i))
        assert result == {}

    def test_stringify_array_value(self) -> None:
        i = run("let v = JSON.stringify([1, 2, 3])")
        assert val(i) == "[1,2,3]"

    def test_stringify_nested_with_replacer(self) -> None:
        i = run("let v = JSON.stringify({a: {x: 1, y: 2}, b: 3}, ['a', 'b'])")
        import json
        result = json.loads(val(i))
        assert "a" in result
        assert "b" in result


# ---------------------------------------------------------------------------
# yield* return value
# ---------------------------------------------------------------------------

class TestYieldStarReturnValue:
    def test_yield_star_return_value_basic(self) -> None:
        i = run("""
fn* inner() {
  yield 1
  return 'done'
}
fn* outer() {
  let r = yield* inner()
  yield r
}
let v = [...outer()]
""")
        assert val(i) == [1, "done"]

    def test_yield_star_no_explicit_return(self) -> None:
        i = run("""
fn* inner() { yield 1; yield 2 }
fn* outer() {
  let r = yield* inner()
  yield r
}
let v = [...outer()]
""")
        # No return statement, so return value is None/undefined
        assert val(i) == [1, 2, None]

    def test_yield_star_multiple_yields_then_return(self) -> None:
        i = run("""
fn* inner() {
  yield 'a'
  yield 'b'
  return 'inner-done'
}
fn* outer() {
  let r = yield* inner()
  yield 'after: ' + r
}
let v = [...outer()]
""")
        assert val(i) == ["a", "b", "after: inner-done"]

    def test_yield_star_chain(self) -> None:
        i = run("""
fn* nums() { yield 1; yield 2; return 'nums-done' }
fn* letters() { yield 'a'; yield 'b'; return 'letters-done' }
fn* combined() {
  let r1 = yield* nums()
  let r2 = yield* letters()
  yield r1 + ',' + r2
}
let v = [...combined()]
""")
        assert val(i) == [1, 2, "a", "b", "nums-done,letters-done"]

    def test_yield_star_plain_iterable(self) -> None:
        i = run("""
fn* outer() {
  yield* [10, 20, 30]
  yield 'end'
}
let v = [...outer()]
""")
        assert val(i) == [10, 20, 30, "end"]

    def test_yield_star_nested_generators(self) -> None:
        i = run("""
fn* a() { yield 1; return 'a-ret' }
fn* b() {
  let r = yield* a()
  yield r
  return 'b-ret'
}
fn* c() {
  let r = yield* b()
  yield r
}
let v = [...c()]
""")
        assert val(i) == [1, "a-ret", "b-ret"]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase52Integration:
    def test_date_comparison(self) -> None:
        i = run("""
let d1 = new Date('2024-01-01')
let d2 = new Date('2024-12-31')
let v = d1.getTime() < d2.getTime()
""")
        assert val(i) is True

    def test_json_stringify_parse_roundtrip(self) -> None:
        i = run("""
let original = {name: 'Alice', age: 30, secret: 'hidden'}
let json = JSON.stringify(original, ['name', 'age'])
let parsed = JSON.parse(json)
let v = [parsed.name, parsed.age, parsed.secret]
""")
        result = val(i)
        assert result[0] == "Alice"
        assert result[1] == 30
        assert result[2] is None or str(result[2]) == "undefined"

    def test_class_prototype_instanceof_consistency(self) -> None:
        i = run("""
class Shape {}
class Circle extends Shape {}
let c = new Circle()
let v = [
  c instanceof Circle,
  c instanceof Shape,
  Object.getPrototypeOf(c) === Circle.prototype
]
""")
        assert val(i) == [True, True, True]

    def test_generator_tree_traverse(self) -> None:
        i = run("""
fn* range(start, end) {
  let i = start
  while(i <= end) { yield i; i++ }
  return 'done-' + start + '-' + end
}
fn* concat_ranges() {
  let r1 = yield* range(1, 3)
  let r2 = yield* range(10, 12)
  yield r1 + ',' + r2
}
let v = [...concat_ranges()]
""")
        assert val(i) == [1, 2, 3, 10, 11, 12, "done-1-3,done-10-12"]

    def test_date_in_calculation(self) -> None:
        i = run("""
fn daysUntil(year, month, day) {
  let target = new Date(year, month - 1, day)
  let now = new Date(2024, 0, 1)
  let diffMs = target.getTime() - now.getTime()
  return Math.round(diffMs / (1000 * 60 * 60 * 24))
}
let v = daysUntil(2024, 1, 1)
""")
        assert val(i) == 0

    def test_json_api_serialization(self) -> None:
        i = run("""
class User {
  constructor(name, email, password) {
    this.name = name
    this.email = email
    this.password = password
  }
}
let user = new User('Alice', 'alice@example.com', 'secret')
let json = JSON.stringify(user, ['name', 'email'])
let v = JSON.parse(json)
""")
        result = val(i)
        assert result["name"] == "Alice"
        assert result["email"] == "alice@example.com"
        assert "password" not in result
