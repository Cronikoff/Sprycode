"""Phase 23 feature tests."""
from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import (
    Interpreter,
    SpryClass,
    SpryInstance,
    SpryRuntimeError,
)
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


def val(i: Interpreter, name: str) -> Any:
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# Fix 1 — `===` and `!==` strict equality operators
# ---------------------------------------------------------------------------


class TestStrictEquality:
    def test_strict_eq_same_number(self):
        i = run("let r = (1 === 1)")
        assert val(i, "r") is True

    def test_strict_eq_different_type(self):
        i = run('let r = (1 === "1")')
        assert val(i, "r") is False

    def test_strict_eq_null(self):
        i = run("let r = (null === null)")
        assert val(i, "r") is True

    def test_strict_eq_null_vs_zero(self):
        i = run("let r = (null === 0)")
        assert val(i, "r") is False

    def test_strict_neq_different_types(self):
        i = run('let r = (1 !== "1")')
        assert val(i, "r") is True

    def test_strict_neq_same_value(self):
        i = run("let r = (1 !== 1)")
        assert val(i, "r") is False

    def test_strict_neq_nan(self):
        i = run("let r = (NaN !== NaN)")
        assert val(i, "r") is True

    def test_strict_eq_booleans(self):
        i = run("let r = (true === true)")
        assert val(i, "r") is True

    def test_strict_eq_bool_vs_int(self):
        i = run("let r = (true === 1)")
        assert val(i, "r") is False

    def test_strict_eq_strings(self):
        i = run('let r = ("hello" === "hello")')
        assert val(i, "r") is True

    def test_regular_eq_unchanged(self):
        i = run("let r = (1 == 1)")
        assert val(i, "r") is True

    def test_regular_neq_unchanged(self):
        i = run("let r = (1 != 2)")
        assert val(i, "r") is True

    def test_strict_eq_float_int(self):
        # int and float with same value — numeric interop
        i = run("let r = (1 === 1.0)")
        assert val(i, "r") is True


# ---------------------------------------------------------------------------
# Fix 2 — `instanceof` inheritance chain
# ---------------------------------------------------------------------------


class TestInstanceofInheritance:
    def test_instanceof_direct_class(self):
        i = run("""
class Animal {}
let a = Animal.new()
let r = a instanceof Animal
""")
        assert val(i, "r") is True

    def test_instanceof_parent_class(self):
        i = run("""
class Animal {}
class Dog extends Animal {}
let d = Dog.new()
let r = d instanceof Animal
""")
        assert val(i, "r") is True

    def test_instanceof_grandparent(self):
        i = run("""
class A {}
class B extends A {}
class C extends B {}
let c = C.new()
let r = c instanceof A
""")
        assert val(i, "r") is True

    def test_instanceof_unrelated_class(self):
        i = run("""
class X {}
class Y {}
let x = X.new()
let r = x instanceof Y
""")
        assert val(i, "r") is False

    def test_instanceof_child_not_parent_type(self):
        i = run("""
class Animal {}
class Dog extends Animal {}
let a = Animal.new()
let r = a instanceof Dog
""")
        assert val(i, "r") is False

    def test_instanceof_multi_level_positive(self):
        i = run("""
class Base {}
class Mid extends Base {}
class Leaf extends Mid {}
let leaf = Leaf.new()
let r1 = leaf instanceof Leaf
let r2 = leaf instanceof Mid
let r3 = leaf instanceof Base
""")
        assert val(i, "r1") is True
        assert val(i, "r2") is True
        assert val(i, "r3") is True


# ---------------------------------------------------------------------------
# Fix 3 — Class expression
# ---------------------------------------------------------------------------


class TestClassExpression:
    def test_class_expr_anonymous(self):
        i = run("""
let X = class {
    fn f() { return 42 }
}
let x = X.new()
let r = x.f()
""")
        assert val(i, "r") == 42

    def test_class_expr_named(self):
        i = run("""
let X = class Point {
    fn f() { return 99 }
}
let p = X.new()
let r = p.f()
""")
        assert val(i, "r") == 99

    def test_class_expr_with_fields(self):
        i = run("""
let Counter = class {
    var count = 0
    fn increment() { self.count += 1 }
    fn get() { return self.count }
}
let c = Counter.new()
c.increment()
c.increment()
let r = c.get()
""")
        assert val(i, "r") == 2

    def test_class_expr_stored_in_variable(self):
        i = run("""
let Cls = class {
    fn hello() { return "hi" }
}
let obj = Cls.new()
let r = obj.hello()
""")
        assert val(i, "r") == "hi"

    def test_class_expr_with_extends(self):
        i = run("""
class Base {
    fn greet() { return "base" }
}
let Child = class extends Base {
    fn greet() { return "child" }
}
let c = Child.new()
let r = c.greet()
""")
        assert val(i, "r") == "child"


# ---------------------------------------------------------------------------
# Fix 4 — `String(x)`, `Number(x)`, `Boolean(x)` as callables
# ---------------------------------------------------------------------------


class TestCallableConverters:
    def test_string_number(self):
        i = run("let r = String(42)")
        assert val(i, "r") == "42"

    def test_string_null(self):
        i = run("let r = String(null)")
        assert val(i, "r") == ""

    def test_string_bool_true(self):
        i = run("let r = String(true)")
        assert val(i, "r") == "true"

    def test_string_bool_false(self):
        i = run("let r = String(false)")
        assert val(i, "r") == "false"

    def test_string_float(self):
        i = run("let r = String(3.14)")
        assert val(i, "r") == "3.14"

    def test_number_string(self):
        i = run('let r = Number("3.14")')
        assert val(i, "r") == pytest.approx(3.14)

    def test_number_integer_string(self):
        i = run('let r = Number("42")')
        assert val(i, "r") == 42

    def test_number_null(self):
        i = run("let r = Number(null)")
        assert val(i, "r") == 0

    def test_number_bool_true(self):
        i = run("let r = Number(true)")
        assert val(i, "r") == 1

    def test_number_bool_false(self):
        i = run("let r = Number(false)")
        assert val(i, "r") == 0

    def test_boolean_zero(self):
        i = run("let r = Boolean(0)")
        assert val(i, "r") is False

    def test_boolean_nonzero(self):
        i = run("let r = Boolean(1)")
        assert val(i, "r") is True

    def test_boolean_null(self):
        i = run("let r = Boolean(null)")
        assert val(i, "r") is False

    def test_boolean_empty_string(self):
        i = run('let r = Boolean("")')
        assert val(i, "r") is False

    def test_boolean_nonempty_string(self):
        i = run('let r = Boolean("hello")')
        assert val(i, "r") is True

    def test_string_namespace_methods_still_work(self):
        i = run("let r = String.fromCharCode(65)")
        assert val(i, "r") == "A"

    def test_number_namespace_methods_still_work(self):
        i = run("let r = Number.isInteger(42)")
        assert val(i, "r") is True


# ---------------------------------------------------------------------------
# Fix 5 — `yield*` delegation
# ---------------------------------------------------------------------------


class TestYieldStar:
    def test_yield_star_array(self):
        i = run("""
fn* gen() { yield* [1, 2, 3] }
let r = [...gen()]
""")
        assert val(i, "r") == [1, 2, 3]

    def test_yield_star_mixed_yields(self):
        i = run("""
fn* gen() {
    yield 0
    yield* [1, 2, 3]
    yield 4
}
let r = [...gen()]
""")
        assert val(i, "r") == [0, 1, 2, 3, 4]

    def test_yield_star_empty(self):
        i = run("""
fn* gen() { yield* [] }
let r = [...gen()]
""")
        assert val(i, "r") == []

    def test_yield_star_nested_generators(self):
        i = run("""
fn* inner() { yield 1; yield 2 }
fn* outer() { yield* inner() }
let r = [...outer()]
""")
        assert val(i, "r") == [1, 2]

    def test_yield_star_strings(self):
        i = run("""
fn* gen() { yield* ["a", "b", "c"] }
let r = [...gen()]
""")
        assert val(i, "r") == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Fix 6 — `in` with `SpryMap`
# ---------------------------------------------------------------------------


class TestInWithSpryMap:
    def test_in_map_key_exists(self):
        i = run("""
let m = Map.new([["x", 1]])
let r = "x" in m
""")
        assert val(i, "r") is True

    def test_in_map_key_missing(self):
        i = run("""
let m = Map.new([["x", 1]])
let r = "y" in m
""")
        assert val(i, "r") is False

    def test_in_map_multiple_keys(self):
        i = run("""
let m = Map.new([["a", 1], ["b", 2], ["c", 3]])
let r1 = "a" in m
let r2 = "d" in m
""")
        assert val(i, "r1") is True
        assert val(i, "r2") is False

    def test_in_map_after_set(self):
        i = run("""
let m = Map.new()
m.set("key", 42)
let r = "key" in m
""")
        assert val(i, "r") is True

    def test_in_map_after_delete(self):
        i = run("""
let m = Map.new([["x", 1]])
m.delete("x")
let r = "x" in m
""")
        assert val(i, "r") is False


# ---------------------------------------------------------------------------
# Fix 7 — `??=`, `&&=`, `||=` on MemberExpression
# ---------------------------------------------------------------------------


class TestMemberCompoundAssignment:
    def test_member_null_coalesce_assign_null(self):
        i = run("""
var o = {x: null}
o.x ??= 42
let r = o.x
""")
        assert val(i, "r") == 42

    def test_member_null_coalesce_assign_not_null(self):
        i = run("""
var o = {x: 10}
o.x ??= 42
let r = o.x
""")
        assert val(i, "r") == 10

    def test_member_and_assign_truthy(self):
        i = run("""
var o = {x: 1}
o.x &&= 5
let r = o.x
""")
        assert val(i, "r") == 5

    def test_member_and_assign_falsy(self):
        i = run("""
var o = {x: 0}
o.x &&= 5
let r = o.x
""")
        assert val(i, "r") == 0

    def test_member_or_assign_falsy(self):
        i = run("""
var o = {x: 0}
o.x ||= 3
let r = o.x
""")
        assert val(i, "r") == 3

    def test_member_or_assign_truthy(self):
        i = run("""
var o = {x: 7}
o.x ||= 3
let r = o.x
""")
        assert val(i, "r") == 7

    def test_member_null_coalesce_assign_instance(self):
        i = run("""
class Box {
    var value = null
    fn fill(v) { self.value ??= v }
    fn get() { return self.value }
}
let b = Box.new()
b.fill(99)
b.fill(0)
let r = b.get()
""")
        assert val(i, "r") == 99


# ---------------------------------------------------------------------------
# Fix 8 — Tagged template literals
# ---------------------------------------------------------------------------


class TestTaggedTemplateLiterals:
    def test_custom_tag_basic(self):
        i = run("""
fn tag(parts, a) { return parts[0] + str(a) + parts[1] }
let v = tag`x=${99}y`
""")
        assert val(i, "v") == "x=99y"

    def test_tag_multiple_values(self):
        i = run("""
fn tag(parts, a, b) {
  return parts[0] + str(a) + parts[1] + str(b) + parts[2]
}
let v = tag`hello ${1} and ${2} world`
""")
        assert val(i, "v") == "hello 1 and 2 world"

    def test_tag_parts_count(self):
        i = run("""
fn tag(parts, a, b) { return parts.length }
let v = tag`a${1}b${2}c`
""")
        assert val(i, "v") == 3

    def test_string_raw_no_interpolation(self):
        i = run("let v = String.raw`hello world`")
        assert val(i, "v") == "hello world"

    def test_string_raw_with_interpolation(self):
        i = run("let n = 42\nlet v = String.raw`value is ${n}`")
        assert val(i, "v") == "value is 42"

    def test_string_raw_multiple_interpolations(self):
        i = run("let a = 1\nlet b = 2\nlet v = String.raw`${a} + ${b}`")
        assert val(i, "v") == "1 + 2"
