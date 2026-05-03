"""Phase 22 feature tests."""
from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import (
    Interpreter,
    SpryClass,
    SpryInstance,
    SpryIterator,
    SpryRuntimeError,
    SpryTypedArray,
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
# Fix 1 — `this` as alias for `self` in methods
# ---------------------------------------------------------------------------


class TestThisKeyword:
    def test_this_in_method(self):
        i = run("""
class Counter {
    var count = 0
    fn increment() {
        this.count += 1
    }
    fn get() {
        return this.count
    }
}
let c = Counter.new()
c.increment()
c.increment()
let result = c.get()
""")
        assert val(i, "result") == 2

    def test_this_in_init(self):
        i = run("""
class Person {
    var name = ""
    fn init(n) {
        this.name = n
    }
    fn greet() {
        return "Hello " + this.name
    }
}
let p = Person.new("Alice")
let greeting = p.greet()
""")
        assert val(i, "greeting") == "Hello Alice"

    def test_self_still_works(self):
        i = run("""
class Box {
    var value = 0
    fn set(v) { self.value = v }
    fn get() { return self.value }
}
let b = Box.new()
b.set(42)
let r = b.get()
""")
        assert val(i, "r") == 42


# ---------------------------------------------------------------------------
# Fix 2 — Static field mutation on SpryClass
# ---------------------------------------------------------------------------


class TestStaticFieldMutation:
    def test_static_field_read(self):
        i = run("""
class Config {
    let version = 1
}
let v = Config.version
""")
        assert val(i, "v") == 1

    def test_static_field_assign(self):
        i = run("""
class Config {
    var count = 0
}
Config.count = 5
let v = Config.count
""")
        assert val(i, "v") == 5

    def test_static_field_compound_assign(self):
        i = run("""
class Counter {
    var total = 0
}
Counter.total += 10
Counter.total += 5
let v = Counter.total
""")
        assert val(i, "v") == 15

    def test_static_field_persists_across_reads(self):
        i = run("""
class State {
    var x = 100
}
State.x = 200
let a = State.x
let b = State.x
""")
        assert val(i, "a") == 200
        assert val(i, "b") == 200


# ---------------------------------------------------------------------------
# Fix 3 — SpryTypedArray subscript indexing
# ---------------------------------------------------------------------------


class TestTypedArraySubscript:
    def test_typed_array_getitem(self):
        i = run("""
let arr = Int32Array.new(3)
arr.set(0, 10)
arr.set(1, 20)
arr.set(2, 30)
let v = arr[1]
""")
        assert val(i, "v") == 20

    def test_typed_array_setitem(self):
        i = run("""
let arr = Uint8Array.new(2)
arr[0] = 42
arr[1] = 99
let a = arr[0]
let b = arr[1]
""")
        assert val(i, "a") == 42
        assert val(i, "b") == 99

    def test_typed_array_for_loop(self):
        i = run("""
let arr = Float64Array.new(3)
arr.set(0, 1.0)
arr.set(1, 2.0)
arr.set(2, 3.0)
var total = 0.0
for x in arr {
    total += x
}
""")
        assert val(i, "total") == pytest.approx(6.0)

    def test_typed_array_len(self):
        """SpryTypedArray supports len() via __len__."""
        i = run("""
let arr = Int32Array.new(5)
let n = arr.length
""")
        assert val(i, "n") == 5


# ---------------------------------------------------------------------------
# Fix 4 — array.reduceRight
# ---------------------------------------------------------------------------


class TestReduceRight:
    def test_reduce_right_basic(self):
        i = run("""
let arr = [1, 2, 3, 4]
let result = arr.reduceRight((acc, x) => acc + x, 0)
""")
        assert val(i, "result") == 10

    def test_reduce_right_order(self):
        i = run("""
let arr = ["a", "b", "c"]
let result = arr.reduceRight((acc, x) => acc + x, "")
""")
        assert val(i, "result") == "cba"

    def test_reduce_right_no_initial(self):
        i = run("""
let arr = [1, 2, 3]
let result = arr.reduceRight((acc, x) => acc - x)
""")
        # reversed: [3, 2, 1] → acc=3, then 3-2=1, then 1-1=0
        assert val(i, "result") == 0

    def test_reduce_right_empty_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("let r = [].reduceRight((acc, x) => acc + x)")


# ---------------------------------------------------------------------------
# Fix 5 — fn.bind(), fn.call(), fn.apply()
# ---------------------------------------------------------------------------


class TestFunctionMethods:
    def test_fn_call(self):
        i = run("""
fn add(a, b) { return a + b }
let result = add.call(null, 3, 4)
""")
        assert val(i, "result") == 7

    def test_fn_apply(self):
        i = run("""
fn sum(a, b, c) { return a + b + c }
let result = sum.apply(null, [1, 2, 3])
""")
        assert val(i, "result") == 6

    def test_fn_bind(self):
        i = run("""
fn mul(a, b) { return a * b }
let double = mul.bind(null, 2)
let result = double(5)
""")
        assert val(i, "result") == 10

    def test_fn_name(self):
        i = run("""
fn greet() { return "hi" }
let n = greet.name
""")
        assert val(i, "n") == "greet"

    def test_fn_length(self):
        i = run("""
fn add(a, b, c) { return a + b + c }
let n = add.length
""")
        assert val(i, "n") == 3

    def test_fn_apply_empty_args(self):
        i = run("""
fn zero() { return 42 }
let result = zero.apply(null)
""")
        assert val(i, "result") == 42


# ---------------------------------------------------------------------------
# Fix 6 — for..in SpryInstance yields keys
# ---------------------------------------------------------------------------


class TestForInInstance:
    def test_for_in_instance_keys(self):
        i = run("""
class Point {
    var x = 1
    var y = 2
}
let p = Point.new()
let keys = []
for k in p {
    keys.push(k)
}
""")
        keys = val(i, "keys")
        assert sorted(keys) == ["x", "y"]

    def test_for_in_instance_private_excluded(self):
        i = run("""
class Node {
    var value = 10
    var __private = "hidden"
}
let n = Node.new()
let keys = []
for k in n {
    keys.push(k)
}
""")
        keys = val(i, "keys")
        assert "value" in keys
        assert "__private" not in keys

    def test_for_in_iterator_protocol_still_works(self):
        """Instances with next() still use iterator protocol."""
        i = run("""
class Range {
    var current = 0
    var max = 3
    fn next() {
        if self.current >= self.max {
            return {done: true, value: null}
        }
        let v = self.current
        self.current += 1
        return {done: false, value: v}
    }
}
let r = Range.new()
let items = []
for x in r {
    items.push(x)
}
""")
        assert val(i, "items") == [0, 1, 2]


# ---------------------------------------------------------------------------
# Fix 7 — Optional chaining with bracket index arr?.[i]
# ---------------------------------------------------------------------------


class TestOptionalChainBracket:
    def test_optional_index_non_null(self):
        i = run("""
let arr = [10, 20, 30]
let v = arr?.[1]
""")
        assert val(i, "v") == 20

    def test_optional_index_null(self):
        i = run("""
let arr = null
let v = arr?.[0]
""")
        assert val(i, "v") is None

    def test_optional_index_dict(self):
        i = run("""
let obj = {a: 1, b: 2}
let v = obj?.["a"]
""")
        assert val(i, "v") == 1

    def test_optional_index_null_dict(self):
        i = run("""
let obj = null
let v = obj?.["key"]
""")
        assert val(i, "v") is None


# ---------------------------------------------------------------------------
# Fix 8 — Spread on SpryIterator / SpryGenerator
# ---------------------------------------------------------------------------


class TestSpreadIterator:
    def test_spread_iterator_in_array(self):
        i = run("""
let it = [1, 2, 3].values()
let arr = [...it]
""")
        # .values() returns SpryIterator or list; just check spread works
        result = val(i, "arr")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_spread_list_still_works(self):
        i = run("""
let a = [1, 2]
let b = [3, 4]
let c = [...a, ...b]
""")
        assert val(i, "c") == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Fix 9 — Object.keys/values/entries on SpryInstance
# ---------------------------------------------------------------------------


class TestObjectKeysInstance:
    def test_object_keys_instance(self):
        i = run("""
class Point {
    var x = 1
    var y = 2
}
let p = Point.new()
let keys = Object.keys(p)
""")
        keys = val(i, "keys")
        assert sorted(keys) == ["x", "y"]

    def test_object_values_instance(self):
        i = run("""
class Point {
    var x = 3
    var y = 4
}
let p = Point.new()
let values = Object.values(p)
""")
        values = val(i, "values")
        assert sorted(values) == [3, 4]

    def test_object_entries_instance(self):
        i = run("""
class Point {
    var x = 5
    var y = 6
}
let p = Point.new()
let entries = Object.entries(p)
""")
        entries = val(i, "entries")
        d = {k: v for k, v in entries}
        assert d == {"x": 5, "y": 6}

    def test_object_keys_excludes_methods(self):
        i = run("""
class Animal {
    var name = "cat"
    fn speak() { return "meow" }
}
let a = Animal.new()
let keys = Object.keys(a)
""")
        keys = val(i, "keys")
        assert "name" in keys
        assert "speak" not in keys

    def test_object_keys_dict_still_works(self):
        i = run("""
let d = {foo: 1, bar: 2}
let keys = Object.keys(d)
""")
        keys = val(i, "keys")
        assert sorted(keys) == ["bar", "foo"]
