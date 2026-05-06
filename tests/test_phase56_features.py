"""Tests for Phase 56 features:
- `function` keyword as JS-compat alias for `fn` (also `function*`, `async function`)
- Object.defineProperty with getter/setter stored lazily (not eagerly invoked)
- Object.getOwnPropertyDescriptor returns {get/set} for accessor properties
- Reflect.construct uses interpreter's _construct_class
- Reflect.getOwnPropertyDescriptor, setPrototypeOf, isExtensible, preventExtensions
- for await...of unwraps SpryPromise items
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
# `function` keyword (JS-compat alias for `fn`)
# ---------------------------------------------------------------------------

class TestFunctionKeyword:
    def test_function_declaration(self) -> None:
        i = run("""
function greet(name) { return "hello " + name }
let v = greet("world")
""")
        assert val(i) == "hello world"

    def test_function_with_multiple_params(self) -> None:
        i = run("""
function add(a, b) { return a + b }
let v = add(3, 4)
""")
        assert val(i) == 7

    def test_function_with_default_param(self) -> None:
        i = run("""
function greet(name = "stranger") { return "hello " + name }
let v = [greet("Alice"), greet()]
""")
        assert val(i) == ["hello Alice", "hello stranger"]

    def test_function_recursive(self) -> None:
        i = run("""
function factorial(n) {
  if (n <= 1) return 1
  return n * factorial(n - 1)
}
let v = factorial(5)
""")
        assert val(i) == 120

    def test_function_returns_function(self) -> None:
        i = run("""
function makeAdder(x) {
  return function(y) { return x + y }
}
let add5 = makeAdder(5)
let v = add5(3)
""")
        assert val(i) == 8

    def test_function_hoisting_same_scope(self) -> None:
        i = run("""
function double(n) { return n * 2 }
let v = double(21)
""")
        assert val(i) == 42

    def test_function_as_value(self) -> None:
        i = run("""
function square(x) { return x * x }
let callback = square
let v = callback(7)
""")
        assert val(i) == 49

    def test_function_is_function_type(self) -> None:
        i = run("""
function foo() {}
let v = typeof foo
""")
        assert val(i) == "function"

    def test_function_keyword_same_as_fn(self) -> None:
        i = run("""
function f1(x) { return x + 1 }
fn f2(x) { return x + 1 }
let v = f1(5) === f2(5)
""")
        assert val(i) is True

    def test_function_with_rest_param(self) -> None:
        i = run("""
function sum(...nums) {
  let total = 0
  for (let n of nums) { total += n }
  return total
}
let v = sum(1, 2, 3, 4)
""")
        assert val(i) == 10

    def test_async_function_keyword(self) -> None:
        i = run("""
async function fetchData() { return 42 }
let p = fetchData()
let v = p.value
""")
        assert val(i) == 42

    def test_async_function_throws(self) -> None:
        i = run("""
async function fail() { throw new Error("oops") }
let p = fail()
let v = p.state
""")
        assert val(i) == "rejected"

    def test_function_star_keyword(self) -> None:
        i = run("""
function* count() {
  yield 1
  yield 2
  yield 3
}
let g = count()
let a = g.next()
let b = g.next()
let c = g.next()
let d = g.next()
let v = [a.value, b.value, c.value, d.done]
""")
        assert val(i) == [1, 2, 3, True]

    def test_function_star_for_of(self) -> None:
        i = run("""
function* range(start, end) {
  let i = start
  while (i < end) {
    yield i
    i++
  }
}
let v = []
for (let x of range(1, 4)) {
  v.push(x)
}
""")
        assert val(i) == [1, 2, 3]

    def test_async_function_star_keyword(self) -> None:
        i = run("""
async function* asyncGen() {
  yield 1
  yield 2
}
let g = asyncGen()
let v = typeof g
""")
        assert val(i) == "object"

    def test_function_in_class(self) -> None:
        """function keyword used as method value (not class method syntax)."""
        i = run("""
class MyClass {
  constructor(x) { this.x = x }
  double() { return this.x * 2 }
}
let obj = new MyClass(7)
let v = obj.double()
""")
        assert val(i) == 14


# ---------------------------------------------------------------------------
# Object.defineProperty with getter / setter
# ---------------------------------------------------------------------------

class TestObjectDefinePropertyGetterSetter:
    def test_getter_is_invoked_on_access(self) -> None:
        i = run("""
let o = {}
Object.defineProperty(o, "x", { get() { return 42 } })
let v = o.x
""")
        assert val(i) == 42

    def test_getter_invoked_each_access(self) -> None:
        i = run("""
let count = 0
let o = {}
Object.defineProperty(o, "x", { get() { count++; return count * 10 } })
let a = o.x
let b = o.x
let v = [a, b, count]
""")
        assert val(i) == [10, 20, 2]

    def test_getter_with_closure(self) -> None:
        i = run("""
let hidden = 99
let o = {}
Object.defineProperty(o, "hidden", { get() { return hidden } })
let v = o.hidden
""")
        assert val(i) == 99

    def test_setter_is_invoked_on_assign(self) -> None:
        i = run("""
let stored = 0
let o = {}
Object.defineProperty(o, "x", {
  get() { return stored },
  set(val) { stored = val * 2 }
})
o.x = 5
let v = stored
""")
        assert val(i) == 10

    def test_getter_setter_combo(self) -> None:
        i = run("""
let _n = 0
let o = {}
Object.defineProperty(o, "n", {
  get() { return _n },
  set(val) { _n = val }
})
o.n = 42
let v = o.n
""")
        assert val(i) == 42

    def test_value_property_descriptor(self) -> None:
        i = run("""
let o = {}
Object.defineProperty(o, "x", { value: 99 })
let v = o.x
""")
        assert val(i) == 99

    def test_defineProperty_on_class_instance(self) -> None:
        i = run("""
class Foo {
  constructor() { this._x = 0 }
}
let f = new Foo()
Object.defineProperty(f, "double", { value: 42 })
let v = f.double
""")
        assert val(i) == 42

    def test_defineProperty_chaining(self) -> None:
        i = run("""
let o = {}
Object.defineProperty(o, "a", { value: 1 })
Object.defineProperty(o, "b", { value: 2 })
let v = [o.a, o.b]
""")
        assert val(i) == [1, 2]

    def test_getter_no_eager_invoke(self) -> None:
        """Getter is NOT called at defineProperty time — only on access."""
        i = run("""
let called = false
let o = {}
Object.defineProperty(o, "x", { get() { called = true; return 42 } })
let v = called
""")
        assert val(i) is False  # not called yet

    def test_getter_then_called(self) -> None:
        i = run("""
let called = false
let o = {}
Object.defineProperty(o, "x", { get() { called = true; return 42 } })
let _ = o.x  // now it's called
let v = called
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# Object.getOwnPropertyDescriptor with accessor properties
# ---------------------------------------------------------------------------

class TestGetOwnPropertyDescriptorAccessor:
    def test_value_descriptor(self) -> None:
        i = run("""
let o = {x: 42}
let d = Object.getOwnPropertyDescriptor(o, "x")
let v = d.value
""")
        assert val(i) == 42

    def test_value_descriptor_writable(self) -> None:
        i = run("""
let o = {x: 42}
let d = Object.getOwnPropertyDescriptor(o, "x")
let v = d.writable
""")
        assert val(i) is True

    def test_getter_descriptor_type(self) -> None:
        i = run("""
let o = {}
Object.defineProperty(o, "x", { get() { return 42 } })
let d = Object.getOwnPropertyDescriptor(o, "x")
let v = typeof d.get
""")
        assert val(i) == "function"

    def test_getter_descriptor_no_value(self) -> None:
        i = run("""
let o = {}
Object.defineProperty(o, "x", { get() { return 42 } })
let d = Object.getOwnPropertyDescriptor(o, "x")
let v = "value" in d
""")
        assert val(i) is False

    def test_getter_accessor_can_be_called(self) -> None:
        i = run("""
let o = {}
Object.defineProperty(o, "x", { get() { return 99 } })
let d = Object.getOwnPropertyDescriptor(o, "x")
let v = d.get()
""")
        assert val(i) == 99

    def test_nonexistent_returns_undefined(self) -> None:
        i = run("""
let o = {x: 1}
let d = Object.getOwnPropertyDescriptor(o, "y")
let v = d
""")
        assert val(i) is None

    def test_getter_setter_descriptor(self) -> None:
        i = run("""
let _x = 0
let o = {}
Object.defineProperty(o, "x", {
  get() { return _x },
  set(v) { _x = v }
})
let d = Object.getOwnPropertyDescriptor(o, "x")
let v = [typeof d.get, typeof d.set]
""")
        assert val(i) == ["function", "function"]


# ---------------------------------------------------------------------------
# Reflect.construct
# ---------------------------------------------------------------------------

class TestReflectConstruct:
    def test_construct_basic(self) -> None:
        i = run("""
class Foo {
  constructor(x) { this.x = x }
}
let f = Reflect.construct(Foo, [42])
let v = f.x
""")
        assert val(i) == 42

    def test_construct_multiple_args(self) -> None:
        i = run("""
class Point {
  constructor(x, y) { this.x = x; this.y = y }
}
let p = Reflect.construct(Point, [3, 4])
let v = [p.x, p.y]
""")
        assert val(i) == [3, 4]

    def test_construct_creates_instance(self) -> None:
        i = run("""
class Foo {}
let f = Reflect.construct(Foo, [])
let v = f instanceof Foo
""")
        assert val(i) is True

    def test_construct_empty_args(self) -> None:
        i = run("""
class Bar {
  constructor() { this.val = 99 }
}
let b = Reflect.construct(Bar, [])
let v = b.val
""")
        assert val(i) == 99

    def test_construct_with_methods(self) -> None:
        i = run("""
class Counter {
  constructor(start) { this.count = start }
  increment() { this.count++ }
}
let c = Reflect.construct(Counter, [10])
c.increment()
let v = c.count
""")
        assert val(i) == 11

    def test_construct_inheriting_class(self) -> None:
        i = run("""
class Animal {
  constructor(name) { this.name = name }
}
class Dog extends Animal {
  constructor(name) { super(name); this.type = "dog" }
}
let d = Reflect.construct(Dog, ["Rex"])
let v = [d.name, d.type]
""")
        assert val(i) == ["Rex", "dog"]


# ---------------------------------------------------------------------------
# Reflect.getOwnPropertyDescriptor
# ---------------------------------------------------------------------------

class TestReflectGetOwnPropertyDescriptor:
    def test_value_descriptor(self) -> None:
        i = run("""
let o = {x: 42}
let d = Reflect.getOwnPropertyDescriptor(o, "x")
let v = d.value
""")
        assert val(i) == 42

    def test_descriptor_keys(self) -> None:
        i = run("""
let o = {x: 42}
let d = Reflect.getOwnPropertyDescriptor(o, "x")
let v = [d.writable, d.enumerable, d.configurable]
""")
        assert val(i) == [True, True, True]

    def test_getter_descriptor(self) -> None:
        i = run("""
let o = {}
Object.defineProperty(o, "x", { get() { return 42 } })
let d = Reflect.getOwnPropertyDescriptor(o, "x")
let v = typeof d.get
""")
        assert val(i) == "function"

    def test_nonexistent_returns_null(self) -> None:
        i = run("""
let o = {x: 1}
let d = Reflect.getOwnPropertyDescriptor(o, "z")
let v = d
""")
        assert val(i) is None

    def test_on_instance(self) -> None:
        i = run("""
class Foo {
  constructor() { this.x = 99 }
}
let f = new Foo()
let d = Reflect.getOwnPropertyDescriptor(f, "x")
let v = d.value
""")
        assert val(i) == 99


# ---------------------------------------------------------------------------
# Reflect.setPrototypeOf / isExtensible / preventExtensions
# ---------------------------------------------------------------------------

class TestReflectExtensions:
    def test_isExtensible_new_object(self) -> None:
        i = run("let v = Reflect.isExtensible({})")
        assert val(i) is True

    def test_preventExtensions_makes_not_extensible(self) -> None:
        i = run("""
let o = {}
Reflect.preventExtensions(o)
let v = Reflect.isExtensible(o)
""")
        assert val(i) is False

    def test_preventExtensions_returns_obj(self) -> None:
        i = run("""
let o = {x: 1}
let ret = Reflect.preventExtensions(o)
let v = ret.x
""")
        assert val(i) == 1

    def test_setPrototypeOf_returns_true(self) -> None:
        i = run("""
let o = {}
let v = Reflect.setPrototypeOf(o, {})
""")
        assert val(i) is True

    def test_setPrototypeOf_on_dict(self) -> None:
        i = run("""
let o = {}
let proto = { foo: 42 }
Reflect.setPrototypeOf(o, proto)
let v = typeof o
""")
        assert val(i) == "object"

    def test_isExtensible_on_instance(self) -> None:
        i = run("""
class Foo {}
let f = new Foo()
let v = Reflect.isExtensible(f)
""")
        assert val(i) is True

    def test_setPrototypeOf_null_proto(self) -> None:
        i = run("""
let o = {}
let v = Reflect.setPrototypeOf(o, null)
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# for await...of with SpryPromise unwrapping
# ---------------------------------------------------------------------------

class TestForAwaitOf:
    def test_unwraps_resolved_promises(self) -> None:
        i = run("""
async fn go() {
  let results = []
  for await (let x of [Promise.resolve(1), Promise.resolve(2), Promise.resolve(3)]) {
    results.push(x)
  }
  return results
}
let v = go().value
""")
        assert val(i) == [1, 2, 3]

    def test_unwraps_mixed_values(self) -> None:
        i = run("""
async fn go() {
  let results = []
  for await (let x of [1, Promise.resolve(2), 3]) {
    results.push(x)
  }
  return results
}
let v = go().value
""")
        assert val(i) == [1, 2, 3]

    def test_sum_of_async_values(self) -> None:
        i = run("""
async fn go() {
  let sum = 0
  for await (let x of [Promise.resolve(10), Promise.resolve(20), Promise.resolve(12)]) {
    sum += x
  }
  return sum
}
let v = go().value
""")
        assert val(i) == 42

    def test_empty_array(self) -> None:
        i = run("""
async fn go() {
  let results = []
  for await (let x of []) {
    results.push(x)
  }
  return results
}
let v = go().value
""")
        assert val(i) == []

    def test_break_in_for_await(self) -> None:
        i = run("""
async fn go() {
  let results = []
  for await (let x of [Promise.resolve(1), Promise.resolve(2), Promise.resolve(3)]) {
    results.push(x)
    if (x >= 2) break
  }
  return results
}
let v = go().value
""")
        assert val(i) == [1, 2]

    def test_destructuring_in_for_await(self) -> None:
        i = run("""
async fn go() {
  let keys = []
  for await (let [k, v] of [Promise.resolve(["a", 1]), Promise.resolve(["b", 2])]) {
    keys.push(k)
  }
  return keys
}
let v = go().value
""")
        assert val(i) == ["a", "b"]

    def test_function_keyword_in_async(self) -> None:
        i = run("""
async function fetchAll() {
  let results = []
  for await (let x of [Promise.resolve(1), Promise.resolve(2)]) {
    results.push(x)
  }
  return results
}
let v = fetchAll().value
""")
        assert val(i) == [1, 2]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase56Integration:
    def test_function_keyword_class_factory(self) -> None:
        i = run("""
function createPoint(x, y) {
  return { x: x, y: y, toString() { return x + "," + y } }
}
let p = createPoint(3, 4)
let v = p.x + p.y
""")
        assert val(i) == 7

    def test_computed_getter_in_class(self) -> None:
        i = run("""
class Temperature {
  constructor(celsius) { this._c = celsius }
  get celsius() { return this._c }
  get fahrenheit() { return this._c * 9 / 5 + 32 }
}
let t = new Temperature(100)
let v = t.fahrenheit
""")
        assert val(i) == 212.0

    def test_reflect_construct_with_defineProperty(self) -> None:
        i = run("""
class Config {
  constructor(opts) {
    this._opts = opts
  }
  get debug() { return this._opts.debug }
}
let c = Reflect.construct(Config, [{debug: true}])
let v = c.debug
""")
        assert val(i) is True

    def test_defineProperty_with_descriptor_inspection(self) -> None:
        i = run("""
let obj = {}
let _val = 0
Object.defineProperty(obj, "count", {
  get() { return _val },
  set(v) { _val = v }
})
obj.count = 5
let d = Object.getOwnPropertyDescriptor(obj, "count")
let v = [obj.count, typeof d.get, typeof d.set]
""")
        assert val(i) == [5, "function", "function"]

    def test_function_and_async_together(self) -> None:
        i = run("""
function double(x) { return x * 2 }
async function asyncDouble(x) { return double(x) }
let p = asyncDouble(21)
let v = p.value
""")
        assert val(i) == 42

    def test_reflect_full_workflow(self) -> None:
        i = run("""
class Box {
  constructor(value) { this.value = value }
  getValue() { return this.value }
}
let b = Reflect.construct(Box, [42])
let d = Reflect.getOwnPropertyDescriptor(b, "value")
let keys = Reflect.ownKeys(b)
let v = [b.getValue(), d.value, "value" in Object.fromEntries(keys.map(k => [k, true]))]
""")
        assert val(i) == [42, 42, True]
