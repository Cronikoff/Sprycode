"""Tests for Phase 92: OOP Patterns
- Singleton, factory, method chaining, toString/valueOf, equals/clone
- Mixin via Object.assign prototype, abstract method, template method
- Computed method names, Symbol.toPrimitive/iterator, private fields
- Getters/setters, static getters, class extending Error
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


# ── Singleton Pattern ──────────────────────────────────────────────────────────

class TestSingleton:
    def test_same_instance(self):
        i = run('''
class Singleton {
  static _instance = null;
  static getInstance() {
    if (Singleton._instance === null) {
      Singleton._instance = new Singleton();
    }
    return Singleton._instance;
  }
}
let a = Singleton.getInstance();
let b = Singleton.getInstance();
let v = a === b;
''')
        assert val(i) is True

    def test_singleton_state(self):
        i = run('''
class Config {
  static _inst = null;
  constructor() { this.debug = false; }
  static get() {
    if (Config._inst === null) Config._inst = new Config();
    return Config._inst;
  }
}
Config.get().debug = true;
let v = Config.get().debug;
''')
        assert val(i) is True


# ── Factory Method ─────────────────────────────────────────────────────────────

class TestFactory:
    def test_factory_dog(self):
        i = run('''
class Animal { constructor(type) { this.type = type; } }
class Dog extends Animal { constructor() { super("dog"); } }
class Cat extends Animal { constructor() { super("cat"); } }
class AnimalFactory {
  static create(type) {
    if (type === "dog") return new Dog();
    return new Cat();
  }
}
let v = AnimalFactory.create("dog") instanceof Dog;
''')
        assert val(i) is True

    def test_factory_cat(self):
        i = run('''
class Animal { constructor(type) { this.type = type; } }
class Dog extends Animal { constructor() { super("dog"); } }
class Cat extends Animal { constructor() { super("cat"); } }
class AnimalFactory {
  static create(type) {
    if (type === "dog") return new Dog();
    return new Cat();
  }
}
let v = AnimalFactory.create("cat").type;
''')
        assert val(i) == "cat"

    def test_factory_returns_correct_type(self):
        i = run('''
class Shape { }
class Circle extends Shape { constructor(r) { super(); this.r = r; } }
class Square extends Shape { constructor(s) { super(); this.s = s; } }
class ShapeFactory {
  static make(type, size) {
    if (type === "circle") return new Circle(size);
    return new Square(size);
  }
}
let v = ShapeFactory.make("circle", 5).r;
''')
        assert val(i) == 5


# ── Method Chaining ────────────────────────────────────────────────────────────

class TestMethodChaining:
    def test_chained_add_mult(self):
        i = run('''
class Builder {
  constructor() { this.val = 0; }
  add(n) { this.val += n; return this; }
  mult(n) { this.val *= n; return this; }
}
let b = new Builder();
b.add(3).mult(2);
let v = b.val;
''')
        assert val(i) == 6

    def test_chained_three_calls(self):
        i = run('''
class Fluent {
  constructor() { this.x = 0; }
  inc() { this.x++; return this; }
}
let f = new Fluent();
f.inc().inc().inc();
let v = f.x;
''')
        assert val(i) == 3

    def test_query_builder_chain(self):
        i = run('''
class Query {
  constructor() { this.parts = []; }
  from(tbl) { this.parts.push("FROM " + tbl); return this; }
  limit(n) { this.parts.push("LIMIT " + n); return this; }
  build() { return this.parts.join(" "); }
}
let q = new Query();
let v = q.from("users").limit(10).build();
''')
        assert val(i) == "FROM users LIMIT 10"


# ── toString Override ──────────────────────────────────────────────────────────

class TestToString:
    def test_point_toString(self):
        i = run('''
class Point {
  constructor(x, y) { this.x = x; this.y = y; }
  toString() { return "(" + this.x + "," + this.y + ")"; }
}
let p = new Point(3, 4);
let v = p.toString();
''')
        assert val(i) == "(3,4)"

    def test_toString_called_explicitly(self):
        i = run('''
class Color {
  constructor(r, g, b) { this.r = r; this.g = g; this.b = b; }
  toString() { return "rgb(" + this.r + "," + this.g + "," + this.b + ")"; }
}
let c = new Color(255, 0, 128);
let v = c.toString();
''')
        assert val(i) == "rgb(255,0,128)"


# ── valueOf Override ───────────────────────────────────────────────────────────

class TestValueOf:
    def test_weight_valueOf(self):
        i = run('''
class Weight {
  constructor(kg) { this.kg = kg; }
  valueOf() { return this.kg; }
}
let w = new Weight(70);
let v = w + 5;
''')
        assert val(i) == 75

    def test_money_valueOf(self):
        i = run('''
class Money {
  constructor(amount) { this.amount = amount; }
  valueOf() { return this.amount; }
}
let m = new Money(100);
let v = m * 2;
''')
        assert val(i) == 200


# ── Equals Pattern ─────────────────────────────────────────────────────────────

class TestEquals:
    def test_equals_true(self):
        i = run('''
class Point {
  constructor(x, y) { this.x = x; this.y = y; }
  equals(o) { return this.x === o.x && this.y === o.y; }
}
let p1 = new Point(1, 2);
let p2 = new Point(1, 2);
let v = p1.equals(p2);
''')
        assert val(i) is True

    def test_equals_false(self):
        i = run('''
class Point {
  constructor(x, y) { this.x = x; this.y = y; }
  equals(o) { return this.x === o.x && this.y === o.y; }
}
let p1 = new Point(1, 2);
let p2 = new Point(3, 4);
let v = p1.equals(p2);
''')
        assert val(i) is False


# ── Clone Pattern ──────────────────────────────────────────────────────────────

class TestClone:
    def test_clone_value(self):
        i = run('''
class Point {
  constructor(x, y) { this.x = x; this.y = y; }
  clone() { return new Point(this.x, this.y); }
}
let p1 = new Point(3, 4);
let p2 = p1.clone();
let v = p2.x;
''')
        assert val(i) == 3

    def test_clone_independent(self):
        i = run('''
class Box {
  constructor(w, h) { this.w = w; this.h = h; }
  clone() { return new Box(this.w, this.h); }
}
let b1 = new Box(10, 20);
let b2 = b1.clone();
b2.w = 99;
let v = b1.w;
''')
        assert val(i) == 10


# ── Mixin Pattern ──────────────────────────────────────────────────────────────

class TestMixin:
    def test_mixin_method_accessible(self):
        i = run('''
let mix = { greet() { return "hi " + this.name; } };
class Person {
  constructor(name) { this.name = name; }
}
Object.assign(Person.prototype, mix);
let p = new Person("Alice");
let v = p.greet();
''')
        assert val(i) == "hi Alice"

    def test_mixin_serialize(self):
        i = run('''
let Serializable = { serialize() { return JSON.stringify({x: this.x}); } };
class Data {
  constructor(x) { this.x = x; }
}
Object.assign(Data.prototype, Serializable);
let d = new Data(42);
let v = d.serialize();
''')
        assert val(i) == '{"x":42}'

    def test_mixin_multiple_methods(self):
        i = run('''
let Logger = {
  log() { return "log: " + this.name; },
  warn() { return "warn: " + this.name; }
};
class Service {
  constructor(name) { this.name = name; }
}
Object.assign(Service.prototype, Logger);
let s = new Service("auth");
let v = s.log();
''')
        assert val(i) == "log: auth"


# ── Abstract Method Pattern ────────────────────────────────────────────────────

class TestAbstractMethod:
    def test_abstract_overridden(self):
        i = run('''
class Shape {
  area() { throw new Error("Abstract method"); }
}
class Square extends Shape {
  constructor(s) { super(); this.s = s; }
  area() { return this.s * this.s; }
}
let sq = new Square(4);
let v = sq.area();
''')
        assert val(i) == 16

    def test_abstract_throws(self):
        i = run('''
class Shape {
  area() { throw new Error("Abstract"); }
}
let v = false;
try {
  let s = new Shape();
  s.area();
} catch(e) {
  v = true;
}
''')
        assert val(i) is True


# ── Template Method Pattern ────────────────────────────────────────────────────

class TestTemplateMethod:
    def test_template_base(self):
        i = run('''
class Game {
  run() {
    this.start();
    this.play();
    return this.score;
  }
  start() { this.score = 0; }
  play() { this.score = 42; }
}
let g = new Game();
let v = g.run();
''')
        assert val(i) == 42

    def test_template_overridden(self):
        i = run('''
class Sorter {
  run(arr) {
    let data = this.prepare(arr);
    return this.sort(data);
  }
  prepare(arr) { return [...arr]; }
  sort(arr) { return arr.sort(); }
}
let s = new Sorter();
let v = s.run([3,1,2]);
''')
        assert val(i) == [1, 2, 3]


# ── Computed Method Names ──────────────────────────────────────────────────────

class TestComputedMethodName:
    def test_symbol_key_method(self):
        i = run('''
let sym = Symbol("greet");
class Foo {
  [sym]() { return "hello"; }
}
let f = new Foo();
let v = f[sym]();
''')
        assert val(i) == "hello"

    def test_string_computed_key(self):
        i = run('''
let key = "sayHi";
class Bar {
  [key]() { return "hi"; }
}
let b = new Bar();
let v = b[key]();
''')
        assert val(i) == "hi"


# ── Symbol.toPrimitive ─────────────────────────────────────────────────────────

class TestSymbolToPrimitive:
    def test_numeric_hint(self):
        i = run('''
class Money {
  constructor(n) { this.n = n; }
  [Symbol.toPrimitive](hint) {
    if (hint === "number") return this.n;
    return String(this.n);
  }
}
let m = new Money(100);
let v = +m;
''')
        assert val(i) == 100

    def test_string_hint(self):
        i = run('''
class Money {
  constructor(n) { this.n = n; }
  [Symbol.toPrimitive](hint) {
    if (hint === "number") return this.n;
    return "money:" + this.n;
  }
}
let m = new Money(50);
let v = String(m);
''')
        assert val(i) == "money:50"


# ── Symbol.iterator ────────────────────────────────────────────────────────────

class TestSymbolIterator:
    def test_range_spread(self):
        i = run('''
class Range {
  constructor(lo, hi) { this.lo = lo; this.hi = hi; }
  [Symbol.iterator]() {
    let cur = this.lo;
    let hi = this.hi;
    return {
      next() {
        if (cur <= hi) return { value: cur++, done: false };
        return { value: undefined, done: true };
      }
    };
  }
}
let r = new Range(1, 3);
let v = [...r];
''')
        assert val(i) == [1, 2, 3]

    def test_range_for_of(self):
        i = run('''
class Range {
  constructor(lo, hi) { this.lo = lo; this.hi = hi; }
  [Symbol.iterator]() {
    let cur = this.lo;
    let hi = this.hi;
    return {
      next() {
        if (cur <= hi) return { value: cur++, done: false };
        return { value: undefined, done: true };
      }
    };
  }
}
let r = new Range(1, 4);
let v = 0;
for (let x of r) { v += x; }
''')
        assert val(i) == 10


# ── Private Naming Convention ──────────────────────────────────────────────────

class TestPrivateNaming:
    def test_counter_private_field(self):
        i = run('''
class Counter {
  constructor() { this._count = 0; }
  inc() { this._count++; return this; }
  getCount() { return this._count; }
}
let c = new Counter();
c.inc(); c.inc();
let v = c.getCount();
''')
        assert val(i) == 2

    def test_private_field_readable(self):
        i = run('''
class Vault {
  constructor(s) { this._s = s; }
  reveal() { return this._s; }
}
let s = new Vault("hello");
let v = s.reveal();
''')
        assert val(i) == "hello"


# ── Getters and Setters ────────────────────────────────────────────────────────

class TestGetterSetter:
    def test_getter_computed(self):
        i = run('''
class Circle {
  constructor(r) { this.r = r; }
  get area() { return Math.PI * this.r * this.r; }
}
let c = new Circle(1);
let v = Math.abs(c.area - Math.PI) < 0.001;
''')
        assert val(i) is True

    def test_temperature_getter(self):
        i = run('''
class Temp {
  constructor(c) { this._c = c; }
  get f() { return this._c * 9 / 5 + 32; }
}
let t = new Temp(0);
let v = t.f;
''')
        assert val(i) == 32.0

    def test_setter_validates(self):
        i = run('''
class Age {
  constructor() { this._age = 0; }
  get age() { return this._age; }
  set age(v) { if (v >= 0) this._age = v; }
}
let a = new Age();
a.age = 25;
let v = a.age;
''')
        assert val(i) == 25

    def test_setter_rejects_invalid(self):
        i = run('''
class Age {
  constructor() { this._age = 0; }
  get age() { return this._age; }
  set age(v) { if (v >= 0) this._age = v; }
}
let a = new Age();
a.age = -5;
let v = a.age;
''')
        assert val(i) == 0

    def test_getter_setter_roundtrip(self):
        i = run('''
class Temp {
  constructor(c) { this._c = c; }
  get f() { return this._c * 9 / 5 + 32; }
  set f(val) { this._c = (val - 32) * 5 / 9; }
}
let t = new Temp(100);
t.f = 32;
let v = Math.round(t._c);
''')
        assert val(i) == 0


# ── Static Getters ─────────────────────────────────────────────────────────────

class TestStaticGetter:
    def test_static_pi(self):
        i = run('''
class MathUtils {
  static get PI() { return 3.14159; }
}
let v = MathUtils.PI;
''')
        assert val(i) == pytest.approx(3.14159)

    def test_static_version(self):
        i = run('''
class App {
  static get VERSION() { return "1.0.0"; }
}
let v = App.VERSION;
''')
        assert val(i) == "1.0.0"


# ── Class Extending Error ──────────────────────────────────────────────────────

class TestClassExtendsError:
    def test_extends_error_message(self):
        i = run('''
class AppError extends Error {
  constructor(msg, code) { super(msg); this.code = code; }
}
let err = new AppError("not found", 404);
let v = err.message;
''')
        assert val(i) == "not found"

    def test_extends_error_code(self):
        i = run('''
class AppError extends Error {
  constructor(msg, code) { super(msg); this.code = code; }
}
let err = new AppError("not found", 404);
let v = err.code;
''')
        assert val(i) == 404

    def test_extends_error_instanceof(self):
        i = run('''
class AppError extends Error {
  constructor(msg) { super(msg); }
}
let err = new AppError("fail");
let v = err instanceof Error;
''')
        assert val(i) is True

    def test_extends_error_caught(self):
        i = run('''
class NetworkError extends Error {
  constructor(msg, status) { super(msg); this.status = status; }
}
let v = null;
try { throw new NetworkError("timeout", 503); }
catch(e) { v = e.status; }
''')
        assert val(i) == 503
