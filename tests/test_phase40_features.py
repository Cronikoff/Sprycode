"""Phase 40 feature tests.

Covers:
- Class method shorthand ``name() { ... }`` without the ``fn`` keyword
  (JS-compatible class body syntax)
- Async and generator method shorthand in class bodies
  (``async name() { ... }`` / ``*name() { ... }``)
- Static method shorthand ``static name() { ... }`` without ``fn``
- Private fields with method-shorthand methods
- ``Object.fromEntries(SpryMap)`` — previously returned ``{}`` for Maps
- Nested template literals ``${`inner: ${x}`}`` — lexer now properly tracks
  expression depth so inner backtick strings don't terminate the outer template
- Template expressions with nested braces (ternary, object access, etc.)
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


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(source: str, name: str = "v") -> Any:
    return run(source).globals.get(name)


# ---------------------------------------------------------------------------
# Class method shorthand (no fn keyword)
# ---------------------------------------------------------------------------

class TestClassMethodShorthand:
    def test_simple_method(self):
        src = "class Foo { bar() { return 42 } }; let f = Foo.new(); let v = f.bar()"
        assert val(src) == 42

    def test_method_with_this(self):
        src = "class Foo { init() { this.x = 7 }; getX() { return this.x } }; let f = Foo.new(); let v = f.getX()"
        assert val(src) == 7

    def test_init_shorthand(self):
        src = "class Foo { init() { this.v = 99 } }; let f = Foo.new(); let v = f.v"
        assert val(src) == 99

    def test_method_with_params(self):
        src = "class Calc { add(a, b) { return a + b } }; let c = Calc.new(); let v = c.add(3, 4)"
        assert val(src) == 7

    def test_multiple_methods(self):
        src = """
class Counter {
  init() { this.n = 0 }
  inc() { this.n = this.n + 1 }
  get() { return this.n }
}
let c = Counter.new()
c.inc()
c.inc()
c.inc()
let v = c.get()
"""
        assert val(src) == 3

    def test_method_chaining(self):
        src = """
class Builder {
  init() { this.parts = [] }
  add(p) { this.parts.push(p); return this }
  build() { return this.parts.join('-') }
}
let b = Builder.new()
let v = b.add('a').add('b').add('c').build()
"""
        assert val(src) == "a-b-c"

    def test_shorthand_with_default_param(self):
        src = "class G { greet(name = 'World') { return 'Hi, ' + name } }; let g = G.new(); let v = g.greet()"
        assert val(src) == "Hi, World"

    def test_shorthand_with_rest_param(self):
        src = "class S { sum(...args) { var t = 0; for (let x of args) { t += x }; return t } }; let s = S.new(); let v = s.sum(1, 2, 3)"
        assert val(src) == 6

    def test_fn_and_shorthand_mixed(self):
        # fn keyword and shorthand methods in the same class
        src = """
class Mixed {
  fn init() { this.x = 10 }
  double() { return this.x * 2 }
}
let m = Mixed.new()
let v = m.double()
"""
        assert val(src) == 20

    def test_shorthand_toString(self):
        src = """
class Point {
  fn init(x, y) { this.x = x; this.y = y }
  toString() { return `(${this.x}, ${this.y})` }
}
let p = Point.new(3, 4)
let v = p.toString()
"""
        assert val(src) == "(3, 4)"

    def test_shorthand_generator(self):
        src = """
class Range {
  fn init(n) { this.n = n }
  *iter() {
    var i = 0
    while (i < this.n) {
      yield i
      i += 1
    }
  }
}
let r = Range.new(3)
let g = r.iter()
let a = g.next().value
let b = g.next().value
let c = g.next().value
let v = a + b + c
"""
        assert val(src) == 3  # 0+1+2

    def test_shorthand_overrides_inheritance(self):
        src = """
class Base {
  fn greet() { return 'base' }
}
class Child extends Base {
  greet() { return 'child' }
}
let c = Child.new()
let v = c.greet()
"""
        assert val(src) == "child"

    def test_keyword_as_method_name(self):
        # 'create' is a reserved keyword — should be usable as method name
        src = "class Foo { create(x) { return x * 3 } }; let f = Foo.new(); let v = f.create(5)"
        assert val(src) == 15

    def test_delete_as_method_name(self):
        src = "class Foo { delete(k) { return 'deleted:' + k } }; let f = Foo.new(); let v = f.delete('x')"
        assert val(src) == "deleted:x"

    def test_from_as_method_name(self):
        src = "class Foo { from(x) { return x + 1 } }; let f = Foo.new(); let v = f.from(9)"
        assert val(src) == 10


# ---------------------------------------------------------------------------
# Private class fields with method shorthands
# ---------------------------------------------------------------------------

class TestPrivateFieldsWithShorthand:
    def test_private_with_shorthand_inc(self):
        src = """
class Counter {
  #count = 0
  inc() { this.#count = this.#count + 1 }
  get() { return this.#count }
}
let c = Counter.new()
c.inc()
c.inc()
let v = c.get()
"""
        assert val(src) == 2

    def test_private_with_fn_init_shorthand_method(self):
        src = """
class Greeter {
  #name
  fn init(name) { this.#name = name }
  greet() { return 'Hello, ' + this.#name }
}
let g = Greeter.new('World')
let v = g.greet()
"""
        assert val(src) == "Hello, World"

    def test_private_field_default_and_shorthand(self):
        src = """
class Acc {
  #total = 0
  add(n) { this.#total += n; return this }
  total() { return this.#total }
}
let a = Acc.new()
a.add(10).add(20).add(5)
let v = a.total()
"""
        assert val(src) == 35


# ---------------------------------------------------------------------------
# Static method shorthand (no fn keyword)
# ---------------------------------------------------------------------------

class TestStaticMethodShorthand:
    def test_static_simple(self):
        src = "class Math2 { static square(x) { return x * x } }; let v = Math2.square(5)"
        assert val(src) == 25

    def test_static_keyword_name(self):
        # 'create' keyword as static method name
        src = "class F { static create(x) { return x * 2 } }; let v = F.create(7)"
        assert val(src) == 14

    def test_static_with_instance_methods(self):
        src = """
class Animal {
  static species() { return 'mammal' }
  fn init(name) { this.name = name }
  speak() { return this.name + ' says hello' }
}
let a = Animal.new('Cat')
let v = Animal.species() + ':' + a.speak()
"""
        assert val(src) == "mammal:Cat says hello"

    def test_static_factory(self):
        src = """
class Box {
  fn init(val) { this.val = val }
  static of(v) { return Box.new(v) }
  get() { return this.val }
}
let b = Box.of(99)
let v = b.get()
"""
        assert val(src) == 99

    def test_static_multi_args(self):
        src = "class M { static add(a, b, c) { return a + b + c } }; let v = M.add(1, 2, 3)"
        assert val(src) == 6

    def test_fn_and_shorthand_static_mixed(self):
        src = """
class Mix {
  static fn double(x) { return x * 2 }
  static triple(x) { return x * 3 }
}
let v = Mix.double(4) + Mix.triple(3)
"""
        assert val(src) == 17


# ---------------------------------------------------------------------------
# Object.fromEntries with SpryMap
# ---------------------------------------------------------------------------

class TestObjectFromEntries:
    def test_from_map(self):
        src = "let v = Object.fromEntries(new Map([['a',1],['b',2]]))"
        assert val(src) == {"a": 1, "b": 2}

    def test_from_map_empty(self):
        src = "let v = Object.fromEntries(new Map())"
        assert val(src) == {}

    def test_from_map_single(self):
        src = "let v = Object.fromEntries(new Map([['key','val']]))"
        assert val(src) == {"key": "val"}

    def test_from_list(self):
        # List of [key, value] pairs — existing behaviour preserved
        src = "let v = Object.fromEntries([['x',10],['y',20]])"
        assert val(src) == {"x": 10, "y": 20}

    def test_from_map_round_trip(self):
        src = """
let m = new Map()
m.set('a', 1)
m.set('b', 2)
let v = Object.fromEntries(m)
"""
        assert val(src) == {"a": 1, "b": 2}

    def test_from_object_entries(self):
        src = "let obj = {x: 1, y: 2}; let v = Object.fromEntries(Object.entries(obj))"
        assert val(src) == {"x": 1, "y": 2}


# ---------------------------------------------------------------------------
# Nested template literals
# ---------------------------------------------------------------------------

class TestNestedTemplateLiterals:
    def test_one_level_nesting(self):
        src = "let x = 5; let v = `result: ${`inner: ${x}`}`"
        assert val(src) == "result: inner: 5"

    def test_side_by_side_nested(self):
        src = "let a = 2; let b = 3; let v = `${`${a}`}-${`${b}`}`"
        assert val(src) == "2-3"

    def test_nested_with_expression(self):
        src = "let n = 42; let v = `value is ${`the answer: ${n}`}`"
        assert val(src) == "value is the answer: 42"

    def test_nested_preserves_other_content(self):
        src = "let x = 1; let v = `before ${`mid ${x} end`} after`"
        assert val(src) == "before mid 1 end after"

    def test_nested_string_interpolation(self):
        src = "let name = 'Alice'; let v = `greet: ${`Hello, ${name}!`}`"
        assert val(src) == "greet: Hello, Alice!"

    def test_basic_template_still_works(self):
        src = "let n = 99; let v = `number: ${n}`"
        assert val(src) == "number: 99"

    def test_template_with_nested_braces_ternary(self):
        src = "let x = true; let v = `${x ? 'yes' : 'no'}`"
        assert val(src) == "yes"

    def test_template_with_bracket_access(self):
        src = "let obj = {a: 1}; let v = `has a: ${obj['a']}`"
        assert val(src) == "has a: 1"

    def test_template_with_method_chain(self):
        src = "let arr = [1,2,3]; let v = `items: ${arr.map(x => x * 2).join(', ')}`"
        assert val(src) == "items: 2, 4, 6"

    def test_template_object_literal_in_expr(self):
        src = "let v = `keys: ${Object.keys({a:1,b:2}).join(',')}`"
        assert val(src) == "keys: a,b"

    def test_tagged_template_still_works(self):
        src = "fn tag(s, ...v) { return s[0] + v[0] * 2 + s[1] }; let x = 5; let v = tag`val: ${x} end`"
        assert val(src) == "val: 10 end"

    def test_template_in_class_toString(self):
        src = """
class Point {
  fn init(x, y) { this.x = x; this.y = y }
  toString() { return `(${this.x}, ${this.y})` }
}
let p = Point.new(3, 4)
let v = p.toString()
"""
        assert val(src) == "(3, 4)"
