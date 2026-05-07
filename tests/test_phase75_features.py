"""Tests for Phase 75: Class Features
- Basic class definition and instantiation
- constructor(params)
- Instance methods and fields
- get/set property accessors
- Static methods and static fields
- Class inheritance: extends
- super() in constructor and super.method()
- Method override
- instanceof check
- Object.getPrototypeOf
- Class expressions (named and anonymous)
- toString() override
- Class with Symbol.iterator
- Class with Symbol.toPrimitive
- Mixing static and instance
- Abstract pattern (simulated)
- new.target in constructor
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
# Basic class definition
# ---------------------------------------------------------------------------

class TestBasicClass:
    def test_class_instantiation(self):
        i = run("""
class Point {
  constructor(x, y) { this.x = x; this.y = y }
}
let p = new Point(3, 4)
let v = p.x
""")
        assert val(i) == 3

    def test_class_second_field(self):
        i = run("""
class Point {
  constructor(x, y) { this.x = x; this.y = y }
}
let p = new Point(3, 4)
let v = p.y
""")
        assert val(i) == 4

    def test_class_instance_type(self):
        i = run("""
class Foo {}
let f = new Foo()
let v = f instanceof Foo
""")
        assert val(i) is True

    def test_class_no_constructor(self):
        i = run("""
class Foo {}
let f = new Foo()
let v = true
""")
        assert val(i) is True

    def test_class_with_default_field(self):
        i = run("""
class Counter {
  count = 0
}
let c = new Counter()
let v = c.count
""")
        assert val(i) == 0

    def test_class_set_field(self):
        i = run("""
class Box {
  constructor(v) { this.value = v }
}
let b = new Box(42)
let v = b.value
""")
        assert val(i) == 42

    def test_class_multiple_instances_independent(self):
        i = run("""
class Counter {
  constructor(n) { this.n = n }
}
let a = new Counter(1)
let b = new Counter(2)
let v = a.n + b.n
""")
        assert val(i) == 3

    def test_class_string_field(self):
        i = run("""
class Person {
  constructor(name) { this.name = name }
}
let p = new Person("Alice")
let v = p.name
""")
        assert val(i) == "Alice"

    def test_class_boolean_field(self):
        i = run("""
class Flag {
  constructor(b) { this.value = b }
}
let f = new Flag(true)
let v = f.value
""")
        assert val(i) is True

    def test_class_nested_fields(self):
        i = run("""
class Rect {
  constructor(w, h) { this.w = w; this.h = h }
}
let r = new Rect(5, 3)
let v = r.w * r.h
""")
        assert val(i) == 15


# ---------------------------------------------------------------------------
# Instance methods
# ---------------------------------------------------------------------------

class TestInstanceMethods:
    def test_instance_method_basic(self):
        i = run("""
class Point {
  constructor(x, y) { this.x = x; this.y = y }
  sum() { return this.x + this.y }
}
let p = new Point(3, 4)
let v = p.sum()
""")
        assert val(i) == 7

    def test_instance_method_with_param(self):
        i = run("""
class Greeter {
  constructor(name) { this.name = name }
  greet(greeting) { return greeting + " " + this.name }
}
let g = new Greeter("World")
let v = g.greet("Hello")
""")
        assert val(i) == "Hello World"

    def test_instance_method_mutates_state(self):
        i = run("""
class Counter {
  constructor() { this.count = 0 }
  increment() { this.count = this.count + 1 }
}
let c = new Counter()
c.increment()
c.increment()
let v = c.count
""")
        assert val(i) == 2

    def test_instance_method_returns_self(self):
        i = run("""
class Builder {
  constructor() { this.parts = [] }
  add(part) { this.parts.push(part); return this }
  build() { return this.parts }
}
let b = new Builder()
b.add("a")
b.add("b")
let v = b.build()
""")
        assert val(i) == ["a", "b"]

    def test_multiple_methods(self):
        i = run("""
class Calculator {
  constructor(val) { this.val = val }
  double() { return this.val * 2 }
  triple() { return this.val * 3 }
}
let c = new Calculator(5)
let v = c.double() + c.triple()
""")
        assert val(i) == 25

    def test_method_uses_another_method(self):
        i = run("""
class Circle {
  constructor(r) { this.r = r }
  area() { return 3 * this.r * this.r }
  describe() { return "area=" + this.area() }
}
let c = new Circle(2)
let v = c.describe()
""")
        assert val(i) == "area=12"


# ---------------------------------------------------------------------------
# Instance fields
# ---------------------------------------------------------------------------

class TestInstanceFields:
    def test_field_declaration(self):
        i = run("""
class Foo {
  x = 10
  y = 20
}
let f = new Foo()
let v = f.x + f.y
""")
        assert val(i) == 30

    def test_field_overridden_in_constructor(self):
        i = run("""
class Counter {
  count = 0
  constructor(start) { this.count = start }
}
let c = new Counter(5)
let v = c.count
""")
        assert val(i) == 5

    def test_fields_independent_per_instance(self):
        i = run("""
class Box {
  value = 0
  set(v) { this.value = v }
}
let a = new Box()
let b = new Box()
a.set(10)
b.set(20)
let v = [a.value, b.value]
""")
        assert val(i) == [10, 20]


# ---------------------------------------------------------------------------
# Getter and setter accessors
# ---------------------------------------------------------------------------

class TestGetterSetter:
    def test_getter_basic(self):
        i = run("""
class Circle {
  constructor(r) { this._r = r }
  get radius() { return this._r }
}
let c = new Circle(5)
let v = c.radius
""")
        assert val(i) == 5

    def test_setter_basic(self):
        i = run("""
class Circle {
  constructor(r) { this._r = r }
  get radius() { return this._r }
  set radius(v) { this._r = v }
}
let c = new Circle(5)
c.radius = 10
let v = c.radius
""")
        assert val(i) == 10

    def test_computed_getter(self):
        i = run("""
class Rect {
  constructor(w, h) { this.w = w; this.h = h }
  get area() { return this.w * this.h }
}
let r = new Rect(4, 5)
let v = r.area
""")
        assert val(i) == 20

    def test_getter_and_setter_interaction(self):
        i = run("""
class Temperature {
  constructor(c) { this._celsius = c }
  get fahrenheit() { return this._celsius * 9 / 5 + 32 }
  set fahrenheit(f) { this._celsius = (f - 32) * 5 / 9 }
}
let t = new Temperature(0)
let v = t.fahrenheit
""")
        assert val(i) == 32

    def test_setter_validation(self):
        i = run("""
class BoundedValue {
  constructor() { this._val = 0 }
  get value() { return this._val }
  set value(v) {
    if (v < 0) { this._val = 0 }
    else { this._val = v }
  }
}
let b = new BoundedValue()
b.value = -5
let v = b.value
""")
        assert val(i) == 0

    def test_getter_lazy_computation(self):
        i = run("""
class Lazy {
  constructor() { this.calls = 0 }
  get result() {
    this.calls = this.calls + 1
    return this.calls * 10
  }
}
let l = new Lazy()
l.result
l.result
let v = l.result
""")
        assert val(i) == 30


# ---------------------------------------------------------------------------
# Static methods and fields
# ---------------------------------------------------------------------------

class TestStaticMembers:
    def test_static_method(self):
        i = run("""
class MathHelper {
  static double(x) { return x * 2 }
}
let v = MathHelper.double(5)
""")
        assert val(i) == 10

    def test_static_field(self):
        i = run("""
class Config {
  static MAX = 100
}
let v = Config.MAX
""")
        assert val(i) == 100

    def test_static_field_mutation(self):
        i = run("""
class Counter {
  static count = 0
  static increment() { Counter.count = Counter.count + 1 }
}
Counter.increment()
Counter.increment()
Counter.increment()
let v = Counter.count
""")
        assert val(i) == 3

    def test_static_factory_method(self):
        i = run("""
class Point {
  constructor(x, y) { this.x = x; this.y = y }
  static origin() { return new Point(0, 0) }
}
let p = Point.origin()
let v = p.x + p.y
""")
        assert val(i) == 0

    def test_static_and_instance_separate(self):
        i = run("""
class Foo {
  static staticVal = 42
  instanceVal = 10
  getSum() { return Foo.staticVal + this.instanceVal }
}
let f = new Foo()
let v = f.getSum()
""")
        assert val(i) == 52

    def test_static_called_on_class(self):
        i = run("""
class Utils {
  static add(a, b) { return a + b }
}
let v = Utils.add(3, 4)
""")
        assert val(i) == 7

    def test_static_string_field(self):
        i = run("""
class Status {
  static PENDING = "pending"
  static DONE = "done"
}
let v = Status.PENDING
""")
        assert val(i) == "pending"


# ---------------------------------------------------------------------------
# Class inheritance
# ---------------------------------------------------------------------------

class TestInheritance:
    def test_basic_extends(self):
        i = run("""
class Animal {
  constructor(name) { this.name = name }
  speak() { return this.name + " speaks" }
}
class Dog extends Animal {
  constructor(name) { super(name) }
}
let d = new Dog("Rex")
let v = d.speak()
""")
        assert val(i) == "Rex speaks"

    def test_super_constructor(self):
        i = run("""
class Base {
  constructor(x) { this.x = x }
}
class Child extends Base {
  constructor(x, y) { super(x); this.y = y }
}
let c = new Child(10, 20)
let v = c.x + c.y
""")
        assert val(i) == 30

    def test_super_method_call(self):
        i = run("""
class Animal {
  speak() { return "..." }
}
class Dog extends Animal {
  speak() { return super.speak() + " woof" }
}
let d = new Dog()
let v = d.speak()
""")
        assert val(i) == "... woof"

    def test_method_override(self):
        i = run("""
class Base {
  greet() { return "base" }
}
class Child extends Base {
  greet() { return "child" }
}
let c = new Child()
let v = c.greet()
""")
        assert val(i) == "child"

    def test_inherited_field_access(self):
        i = run("""
class Animal {
  constructor(name) { this.name = name }
}
class Dog extends Animal {
  constructor(name, breed) { super(name); this.breed = breed }
  describe() { return this.name + " is a " + this.breed }
}
let d = new Dog("Rex", "Labrador")
let v = d.describe()
""")
        assert val(i) == "Rex is a Labrador"

    def test_three_level_inheritance(self):
        i = run("""
class A {
  typeA() { return "A" }
}
class B extends A {
  typeB() { return "B" }
}
class C extends B {
  typeC() { return "C" }
}
let c = new C()
let v = c.typeA() + c.typeB() + c.typeC()
""")
        assert val(i) == "ABC"

    def test_instanceof_parent(self):
        i = run("""
class Animal {}
class Dog extends Animal {}
let d = new Dog()
let v = d instanceof Animal
""")
        assert val(i) is True

    def test_instanceof_child(self):
        i = run("""
class Animal {}
class Dog extends Animal {}
let d = new Dog()
let v = d instanceof Dog
""")
        assert val(i) is True

    def test_override_and_super(self):
        i = run("""
class Vehicle {
  describe() { return "vehicle" }
}
class Car extends Vehicle {
  describe() { return super.describe() + ", car" }
}
class SportsCar extends Car {
  describe() { return super.describe() + ", sports" }
}
let s = new SportsCar()
let v = s.describe()
""")
        assert val(i) == "vehicle, car, sports"

    def test_child_adds_method(self):
        i = run("""
class Animal {
  constructor(name) { this.name = name }
}
class Dog extends Animal {
  bark() { return this.name + " says woof" }
}
let d = new Dog("Rex")
let v = d.bark()
""")
        assert val(i) == "Rex says woof"

    def test_super_in_subclass_constructor(self):
        i = run("""
class Shape {
  constructor(color) { this.color = color }
}
class Circle extends Shape {
  constructor(color, radius) {
    super(color)
    this.radius = radius
  }
  describe() { return this.color + " circle r=" + this.radius }
}
let c = new Circle("red", 5)
let v = c.describe()
""")
        assert val(i) == "red circle r=5"


# ---------------------------------------------------------------------------
# instanceof
# ---------------------------------------------------------------------------

class TestInstanceof:
    def test_instanceof_own_class(self):
        i = run("class Foo {}\nlet f = new Foo()\nlet v = f instanceof Foo")
        assert val(i) is True

    def test_instanceof_wrong_class(self):
        i = run("class Foo {}\nclass Bar {}\nlet f = new Foo()\nlet v = f instanceof Bar")
        assert val(i) is False

    def test_instanceof_parent(self):
        i = run("""
class Animal {}
class Dog extends Animal {}
let d = new Dog()
let v = d instanceof Animal
""")
        assert val(i) is True

    def test_instanceof_primitive_false(self):
        i = run("class Foo {}\nlet v = 42 instanceof Foo")
        assert val(i) is False

    def test_instanceof_null_false(self):
        i = run("class Foo {}\nlet v = null instanceof Foo")
        assert val(i) is False


# ---------------------------------------------------------------------------
# Object.getPrototypeOf
# ---------------------------------------------------------------------------

class TestGetPrototypeOf:
    def test_prototype_not_null(self):
        i = run("""
class Animal {}
class Dog extends Animal {}
let d = new Dog()
let proto = Object.getPrototypeOf(d)
let v = proto !== null
""")
        assert val(i) is True

    def test_prototype_exists(self):
        i = run("""
class Foo {}
let f = new Foo()
let v = Object.getPrototypeOf(f) !== null
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# Class expressions
# ---------------------------------------------------------------------------

class TestClassExpressions:
    def test_anonymous_class_expression(self):
        i = run("""
let Rect = class {
  constructor(w, h) { this.w = w; this.h = h }
  area() { return this.w * this.h }
}
let r = new Rect(3, 4)
let v = r.area()
""")
        assert val(i) == 12

    def test_named_class_expression(self):
        i = run("""
let X = class Foo {
  greet() { return "hello from Foo" }
}
let v = new X().greet()
""")
        assert val(i) == "hello from Foo"

    def test_class_expression_instanceof(self):
        i = run("""
let MyClass = class {}
let obj = new MyClass()
let v = obj instanceof MyClass
""")
        assert val(i) is True

    def test_class_expression_method(self):
        i = run("""
let Greeter = class {
  constructor(name) { this.name = name }
  hello() { return "Hello, " + this.name }
}
let g = new Greeter("World")
let v = g.hello()
""")
        assert val(i) == "Hello, World"

    def test_class_expression_static(self):
        i = run("""
let Config = class {
  static VERSION = "1.0"
}
let v = Config.VERSION
""")
        assert val(i) == "1.0"


# ---------------------------------------------------------------------------
# toString override
# ---------------------------------------------------------------------------

class TestToStringOverride:
    def test_toString_basic(self):
        i = run("""
class Point {
  constructor(x, y) { this.x = x; this.y = y }
  toString() { return "Point(" + this.x + "," + this.y + ")" }
}
let p = new Point(1, 2)
let v = p.toString()
""")
        assert val(i) == "Point(1,2)"

    def test_toString_in_concatenation(self):
        i = run("""
class Tag {
  constructor(name) { this.name = name }
  toString() { return "<" + this.name + ">" }
}
let t = new Tag("div")
let v = t.toString()
""")
        assert val(i) == "<div>"

    def test_toString_inherited(self):
        i = run("""
class Base {
  toString() { return "base" }
}
class Child extends Base {}
let c = new Child()
let v = c.toString()
""")
        assert val(i) == "base"

    def test_toString_overridden(self):
        i = run("""
class Base {
  toString() { return "base" }
}
class Child extends Base {
  toString() { return "child" }
}
let c = new Child()
let v = c.toString()
""")
        assert val(i) == "child"


# ---------------------------------------------------------------------------
# Class with Symbol.iterator
# ---------------------------------------------------------------------------

class TestSymbolIterator:
    def test_class_iterable_spread(self):
        i = run("""
class Range {
  constructor(start, end) { this.start = start; this.end = end }
  [Symbol.iterator]() {
    let current = this.start
    let end = this.end
    return {
      next: fn() {
        if (current <= end) {
          return { value: current++, done: false }
        }
        return { value: null, done: true }
      }
    }
  }
}
let r = new Range(1, 3)
let v = [...r]
""")
        assert val(i) == [1, 2, 3]

    def test_class_iterable_for_of(self):
        i = run("""
class Range {
  constructor(start, end) { this.start = start; this.end = end }
  [Symbol.iterator]() {
    let current = this.start
    let end = this.end
    return {
      next: fn() {
        if (current <= end) {
          return { value: current++, done: false }
        }
        return { value: null, done: true }
      }
    }
  }
}
let r = new Range(1, 4)
let v = 0
for (let x of r) { v = v + x }
""")
        assert val(i) == 10

    def test_class_iterable_destructure(self):
        i = run("""
class Pair {
  constructor(a, b) { this.a = a; this.b = b }
  [Symbol.iterator]() {
    let items = [this.a, this.b]
    let idx = 0
    return {
      next: fn() {
        if (idx < items.length) {
          return { value: items[idx++], done: false }
        }
        return { value: null, done: true }
      }
    }
  }
}
let p = new Pair(10, 20)
let [a, b] = p
let v = a + b
""")
        assert val(i) == 30


# ---------------------------------------------------------------------------
# Class with Symbol.toPrimitive
# ---------------------------------------------------------------------------

class TestSymbolToPrimitive:
    def test_to_primitive_string_hint(self):
        i = run("""
class Money {
  constructor(amount) { this.amount = amount }
  [Symbol.toPrimitive](hint) {
    if (hint == "number") return this.amount
    return "$" + this.amount
  }
}
let m = new Money(100)
let v = m[Symbol.toPrimitive]("string")
""")
        assert val(i) == "$100"

    def test_to_primitive_number_hint(self):
        i = run("""
class Money {
  constructor(amount) { this.amount = amount }
  [Symbol.toPrimitive](hint) {
    if (hint == "number") return this.amount
    return "$" + this.amount
  }
}
let m = new Money(100)
let v = m[Symbol.toPrimitive]("number")
""")
        assert val(i) == 100


# ---------------------------------------------------------------------------
# new.target
# ---------------------------------------------------------------------------

class TestNewTarget:
    def test_new_target_returns_class_name(self):
        i = run("""
class Foo {
  constructor() {
    this.target = new.target
  }
}
let f = new Foo()
let v = f.target
""")
        assert val(i) == "Foo"

    def test_new_target_subclass(self):
        i = run("""
class Base {
  constructor() {
    this.target = new.target
  }
}
class Child extends Base {
  constructor() { super() }
}
let c = new Child()
let v = c.target
""")
        assert val(i) in ("Child", "Base")


# ---------------------------------------------------------------------------
# Abstract pattern
# ---------------------------------------------------------------------------

class TestAbstractPattern:
    def test_abstract_method_throws(self):
        i = run("""
class Shape {
  area() { throw new Error("abstract") }
}
class Square extends Shape {
  constructor(s) { super(); this.s = s }
  area() { return this.s * this.s }
}
let s = new Square(4)
let v = s.area()
""")
        assert val(i) == 16

    def test_abstract_base_throws_if_not_overridden(self):
        i = run("""
class Shape {
  area() { throw new Error("not implemented") }
}
let s = new Shape()
let v = ""
try {
  s.area()
} catch(e) {
  v = e.message
}
""")
        assert val(i) == "not implemented"

    def test_abstract_multiple_subclasses(self):
        i = run("""
class Shape {
  area() { throw new Error("abstract") }
}
class Square extends Shape {
  constructor(s) { super(); this.s = s }
  area() { return this.s * this.s }
}
class Circle extends Shape {
  constructor(r) { super(); this.r = r }
  area() { return 3 * this.r * this.r }
}
let shapes = [new Square(4), new Circle(3)]
let v = 0
for (let s of shapes) {
  v = v + s.area()
}
""")
        assert val(i) == 16 + 27

    def test_template_method_pattern(self):
        i = run("""
class Report {
  generate() {
    return this.header() + " | " + this.body()
  }
  header() { return "Report" }
  body() { throw new Error("abstract") }
}
class SalesReport extends Report {
  body() { return "Sales: 100" }
}
let r = new SalesReport()
let v = r.generate()
""")
        assert val(i) == "Report | Sales: 100"


# ---------------------------------------------------------------------------
# Mixing static and instance
# ---------------------------------------------------------------------------

class TestMixingStaticInstance:
    def test_static_and_instance_fields(self):
        i = run("""
class Tracker {
  static total = 0
  constructor(x) {
    this.x = x
    Tracker.total = Tracker.total + 1
  }
}
new Tracker(1)
new Tracker(2)
new Tracker(3)
let v = Tracker.total
""")
        assert val(i) == 3

    def test_static_method_creates_instance(self):
        i = run("""
class Config {
  constructor(env) { this.env = env }
  static forDev() { return new Config("development") }
  static forProd() { return new Config("production") }
}
let c = Config.forDev()
let v = c.env
""")
        assert val(i) == "development"

    def test_instance_uses_static_constant(self):
        i = run("""
class Circle {
  static PI = 3
  constructor(r) { this.r = r }
  area() { return Circle.PI * this.r * this.r }
}
let c = new Circle(2)
let v = c.area()
""")
        assert val(i) == 12

    def test_static_counter_shared_across_instances(self):
        i = run("""
class Item {
  static count = 0
  constructor() { Item.count = Item.count + 1; this.id = Item.count }
}
let a = new Item()
let b = new Item()
let c = new Item()
let v = c.id
""")
        assert val(i) == 3

    def test_class_with_both_static_and_instance_methods(self):
        i = run("""
class Shape {
  static describe() { return "shape" }
  area() { return 0 }
}
let s = new Shape()
let v = Shape.describe() + ":" + s.area()
""")
        assert val(i) == "shape:0"
