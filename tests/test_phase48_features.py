"""Tests for Phase 48 features:
- Generator lazy for-of: infinite generators with break now work correctly
- Private instance methods: #method() in class body
- Static private fields: static #field = value
- Static private methods: static #method() { }
- Object spread for SpryInstance: {...instance} copies non-method fields
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
# Generator lazy iteration (for-of with break on infinite generators)
# ---------------------------------------------------------------------------

class TestGeneratorLazyForOf:
    def test_infinite_gen_take_5(self) -> None:
        i = run("""
fn* count() {
  var i = 0
  while(true) { yield i; i = i + 1 }
}
let v = []
for(let x of count()) {
  v.push(x)
  if(v.length >= 5) break
}
""")
        assert val(i) == [0, 1, 2, 3, 4]

    def test_fibonacci_lazy(self) -> None:
        i = run("""
fn* fibonacci() {
  var a = 0, b = 1
  while(true) {
    yield a
    var tmp = b
    b = a + b
    a = tmp
  }
}
let v = []
for(let n of fibonacci()) {
  if(v.length >= 8) break
  v.push(n)
}
""")
        assert val(i) == [0, 1, 1, 2, 3, 5, 8, 13]

    def test_finite_gen_completes_normally(self) -> None:
        i = run("""
fn* range(n) {
  var i = 0
  while(i < n) { yield i; i = i + 1 }
}
let v = []
for(let x of range(4)) { v.push(x) }
""")
        assert val(i) == [0, 1, 2, 3]

    def test_gen_break_early(self) -> None:
        """Break mid-generator should not exhaust it."""
        i = run("""
fn* naturals() {
  var i = 1
  while(true) { yield i; i = i + 1 }
}
var v = 0
for(let n of naturals()) {
  v = v + n
  if(n >= 5) break
}
""")
        assert val(i) == 15  # 1+2+3+4+5

    def test_for_of_gen_destructure(self) -> None:
        i = run("""
fn* pairs() {
  var i = 0
  while(i < 3) { yield [i, i * i]; i = i + 1 }
}
let v = []
for(let [n, sq] of pairs()) { v.push(sq) }
""")
        assert val(i) == [0, 1, 4]

    def test_dict_iterator_lazy(self) -> None:
        """dict-iterator with next() is also iterated lazily."""
        i = run("""
fn makeIter(max) {
  var cur = 0
  return {
    next: () => {
      if(cur < max) {
        let r = {value: cur, done: false}
        cur = cur + 1
        return r
      }
      return {value: null, done: true}
    }
  }
}
let v = []
for(let x of makeIter(3)) { v.push(x) }
""")
        assert val(i) == [0, 1, 2]

    def test_class_symbol_iterator_lazy(self) -> None:
        """SpryInstance [Symbol.iterator]() is iterated lazily."""
        i = run("""
class Range {
  fn init(start, end) { this.start = start; this.end = end }
  [Symbol.iterator]() {
    var current = this.start
    var end = this.end
    return {
      next: () => {
        if(current <= end) {
          let val = current
          current = current + 1
          return {value: val, done: false}
        }
        return {value: null, done: true}
      }
    }
  }
}
let v = []
for(let n of new Range(1, 5)) { v.push(n) }
""")
        assert val(i) == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Private instance methods
# ---------------------------------------------------------------------------

class TestPrivateInstanceMethods:
    def test_basic_private_method(self) -> None:
        i = run("""
class Foo {
  #x = 10
  #double() { return this.#x * 2 }
  compute() { return this.#double() }
}
let f = new Foo()
let v = f.compute()
""")
        assert val(i) == 20

    def test_private_method_with_param(self) -> None:
        i = run("""
class Calc {
  #base = 100
  #add(n) { return this.#base + n }
  result(n) { return this.#add(n) }
}
let c = new Calc()
let v = c.result(42)
""")
        assert val(i) == 142

    def test_private_method_chained(self) -> None:
        i = run("""
class Pipeline {
  #step1(x) { return x * 2 }
  #step2(x) { return x + 10 }
  process(x) { return this.#step2(this.#step1(x)) }
}
let p = new Pipeline()
let v = p.process(5)
""")
        assert val(i) == 20

    def test_private_method_not_accessible_externally(self) -> None:
        """Private methods should not be accessible from outside (attribute error)."""
        with pytest.raises(Exception):
            run("""
class Secret {
  #hidden() { return 42 }
  expose() { return this.#hidden() }
}
let s = new Secret()
s.#hidden()
""")

    def test_private_method_accesses_private_field(self) -> None:
        i = run("""
class BankAccount {
  #balance = 0
  deposit(amount) { this.#balance = this.#balance + amount }
  withdraw(amount) {
    if(amount > 0 && amount <= this.#balance) {
      this.#balance = this.#balance - amount
      return true
    }
    return false
  }
  getBalance() { return this.#balance }
}
let acct = new BankAccount()
acct.deposit(100)
let ok = acct.withdraw(30)
let v = [acct.getBalance()]
""")
        assert val(i) == [70]

    def test_private_method_in_subclass(self) -> None:
        i = run("""
class Base {
  #greet() { return 'hello from base' }
  hello() { return this.#greet() }
}
class Child extends Base {
  greetChild() { return 'child here' }
}
let c = new Child()
let v = [c.hello(), c.greetChild()]
""")
        assert val(i) == ['hello from base', 'child here']


# ---------------------------------------------------------------------------
# Static private fields
# ---------------------------------------------------------------------------

class TestStaticPrivateFields:
    def test_basic_static_private_field(self) -> None:
        i = run("""
class Counter {
  static #count = 0
  static inc() { Counter.#count++ }
  static get() { return Counter.#count }
}
Counter.inc()
Counter.inc()
Counter.inc()
let v = Counter.get()
""")
        assert val(i) == 3

    def test_static_private_field_mutation(self) -> None:
        i = run("""
class IdGen {
  static #next = 1
  static nextId() {
    let id = IdGen.#next
    IdGen.#next = IdGen.#next + 1
    return id
  }
}
let v = [IdGen.nextId(), IdGen.nextId(), IdGen.nextId()]
""")
        assert val(i) == [1, 2, 3]

    def test_static_private_not_shared_with_instance(self) -> None:
        """Static private field should not appear on instance."""
        i = run("""
class MyClass {
  static #shared = 99
  static getShared() { return MyClass.#shared }
  fn init() { this.value = 1 }
}
let obj = new MyClass()
let v = [MyClass.getShared(), obj.value]
""")
        assert val(i) == [99, 1]

    def test_static_private_field_default_zero(self) -> None:
        i = run("""
class Tracker {
  static #hits = 0
  static hit() { Tracker.#hits = Tracker.#hits + 1 }
  static count() { return Tracker.#hits }
}
for(var i=0;i<5;i++) { Tracker.hit() }
let v = Tracker.count()
""")
        assert val(i) == 5


# ---------------------------------------------------------------------------
# Static private methods
# ---------------------------------------------------------------------------

class TestStaticPrivateMethods:
    def test_basic_static_private_method(self) -> None:
        i = run("""
class MathUtil {
  static #double(x) { return x * 2 }
  static doubled(x) { return MathUtil.#double(x) }
}
let v = MathUtil.doubled(7)
""")
        assert val(i) == 14

    def test_static_private_method_uses_static_private_field(self) -> None:
        i = run("""
class Circle {
  static #PI = 3.14159
  static #sq(x) { return x * x }
  static area(r) { return Circle.#PI * Circle.#sq(r) }
}
let v = Math.round(Circle.area(2) * 100) / 100
""")
        assert val(i) == 12.57

    def test_static_private_method_multiple(self) -> None:
        i = run("""
class Validator {
  static #isPositive(n) { return n > 0 }
  static #isSmall(n) { return n < 100 }
  static isValid(n) { return Validator.#isPositive(n) && Validator.#isSmall(n) }
}
let v = [Validator.isValid(50), Validator.isValid(-1), Validator.isValid(200)]
""")
        assert val(i) == [True, False, False]


# ---------------------------------------------------------------------------
# Object spread for SpryInstance
# ---------------------------------------------------------------------------

class TestInstanceSpread:
    def test_basic_spread(self) -> None:
        i = run("""
class Point {
  fn init(x, y) { this.x = x; this.y = y }
}
let p = new Point(1, 2)
let v = {...p}
""")
        assert val(i) == {"x": 1, "y": 2}

    def test_spread_with_extra_keys(self) -> None:
        i = run("""
class Point {
  fn init(x, y) { this.x = x; this.y = y }
}
let p = new Point(3, 4)
let v = {...p, z: 5}
""")
        assert val(i) == {"x": 3, "y": 4, "z": 5}

    def test_spread_override(self) -> None:
        i = run("""
class Config {
  fn init() { this.host = 'localhost'; this.port = 3000 }
}
let defaults = new Config()
let v = {...defaults, port: 8080}
""")
        assert val(i) == {"host": "localhost", "port": 8080}

    def test_spread_does_not_copy_methods(self) -> None:
        """Spread should only copy data fields, not methods."""
        i = run("""
class Foo {
  fn init() { this.x = 1 }
  bar() { return 42 }
}
let f = new Foo()
let v = Object.keys({...f})
""")
        assert val(i) == ["x"]

    def test_spread_merge_two_instances(self) -> None:
        i = run("""
class A {
  fn init() { this.a = 1; this.b = 2 }
}
class B {
  fn init() { this.b = 20; this.c = 3 }
}
let a = new A()
let b = new B()
let v = {...a, ...b}
""")
        assert val(i) == {"a": 1, "b": 20, "c": 3}

    def test_spread_plain_dict_still_works(self) -> None:
        i = run("""
let a = {x: 1, y: 2}
let v = {...a, z: 3}
""")
        assert val(i) == {"x": 1, "y": 2, "z": 3}

    def test_spread_in_function_call_style(self) -> None:
        i = run("""
class Vec {
  fn init(x, y) { this.x = x; this.y = y }
}
fn sum(d) { return d.x + d.y + (d.z ?? 0) }
let v_vec = new Vec(3, 4)
let v = sum({...v_vec, z: 5})
""")
        assert val(i) == 12


# ---------------------------------------------------------------------------
# Integration: all features together
# ---------------------------------------------------------------------------

class TestPhase48Integration:
    def test_class_with_private_fields_and_methods(self) -> None:
        i = run("""
class Stack {
  #data = []
  #isEmpty() { return this.#data.length == 0 }
  push(x) { this.#data.push(x) }
  pop() {
    if(this.#isEmpty()) return null
    return this.#data.pop()
  }
  size() { return this.#data.length }
}
let s = new Stack()
s.push(1)
s.push(2)
s.push(3)
let a = s.pop()
let v = [a, s.size()]
""")
        assert val(i) == [3, 2]

    def test_static_private_singleton(self) -> None:
        i = run("""
class Singleton {
  static #instance = null
  fn init(x) { this.x = x }
  static getInstance(x) {
    if(Singleton.#instance == null) {
      Singleton.#instance = new Singleton(x)
    }
    return Singleton.#instance
  }
}
let a = Singleton.getInstance(42)
let b = Singleton.getInstance(99)
let v = [a.x, b.x, a === b]
""")
        # Both should be the same instance with x=42
        assert val(i) == [42, 42, True]

    def test_infinite_gen_with_early_return_value(self) -> None:
        i = run("""
fn* evens() {
  var n = 0
  while(true) { yield n; n = n + 2 }
}
let first10 = []
for(let x of evens()) {
  first10.push(x)
  if(first10.length >= 5) break
}
let v = first10
""")
        assert val(i) == [0, 2, 4, 6, 8]

    def test_spread_and_private_combined(self) -> None:
        i = run("""
class Person {
  #secret = 'hidden'
  fn init(name, age) { this.name = name; this.age = age }
  getSecret() { return this.#secret }
}
let alice = new Person('Alice', 30)
let snapshot = {...alice}
let v = [snapshot.name, snapshot.age, Object.keys(snapshot)]
""")
        assert val(i) == ["Alice", 30, ["name", "age"]]
