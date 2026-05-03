"""Phase 34 feature tests.

Covers:
- `const` keyword: immutable binding identical to `let` (JS-compatible)
  - top-level declarations: const x = value
  - list destructuring: const [a, b] = [...]
  - object destructuring: const {x, y} = {...}
  - for-of loop: for (const item of iterable) { ... }
  - for-in loop: for (const key in obj) { ... }
  - C-style for init: for (const i = 0; ...) (treated as mutable loop var)
- `for (let i = 0; ...)` C-style loop immutability fix:
  - `let` in for-loop init creates a mutable loop counter (JS semantics)
- `constructor` method name in classes (alias for `init`):
  - `fn constructor(args) { ... }` is called on instantiation
  - `super(args)` calls parent constructor() or init()
  - `super.constructor()` resolves to parent constructor
- Semicolons in class body: ignored between member declarations
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


def val(source_or_interp: Any, name: str = "v") -> Any:
    if isinstance(source_or_interp, str):
        return run(source_or_interp).globals.get(name)
    return source_or_interp.globals.get(name)


# ---------------------------------------------------------------------------
# const keyword — top-level declarations
# ---------------------------------------------------------------------------


class TestConstDeclaration:
    def test_const_number(self) -> None:
        assert val("const x = 42; let v = x") == 42

    def test_const_string(self) -> None:
        assert val('const msg = "hello"; let v = msg') == "hello"

    def test_const_bool(self) -> None:
        assert val("const flag = true; let v = flag") is True

    def test_const_null(self) -> None:
        assert val("const n = null; let v = n") is None

    def test_const_expression(self) -> None:
        assert val("const a = 3; const b = 4; let v = a + b") == 7

    def test_const_array(self) -> None:
        assert val("const arr = [1, 2, 3]; let v = arr") == [1, 2, 3]

    def test_const_object(self) -> None:
        assert val("const obj = {x: 1, y: 2}; let v = obj.x + obj.y") == 3

    def test_const_function_call(self) -> None:
        assert val("fn double(n) { return n * 2 }; const x = double(21); let v = x") == 42

    def test_const_used_in_expression(self) -> None:
        assert val("const pi = 3.14159; let v = pi * 2") == pytest.approx(6.28318)

    def test_const_in_condition(self) -> None:
        assert val('const limit = 10; var v = "no"; if limit > 5 { v = "yes" }') == "yes"


# ---------------------------------------------------------------------------
# const keyword — destructuring
# ---------------------------------------------------------------------------


class TestConstDestructuring:
    def test_const_list_destructure(self) -> None:
        assert val("const [a, b] = [1, 2]; let v = a + b") == 3

    def test_const_list_destructure_three(self) -> None:
        i = run("const [a, b, c] = [10, 20, 30]")
        assert i.globals.get("a") == 10
        assert i.globals.get("b") == 20
        assert i.globals.get("c") == 30

    def test_const_list_destructure_with_rest(self) -> None:
        i = run("const [head, ...tail] = [1, 2, 3, 4]")
        assert i.globals.get("head") == 1
        assert i.globals.get("tail") == [2, 3, 4]

    def test_const_object_destructure(self) -> None:
        i = run("const {x, y} = {x: 10, y: 20}")
        assert i.globals.get("x") == 10
        assert i.globals.get("y") == 20

    def test_const_object_destructure_sum(self) -> None:
        assert val("const {a, b} = {a: 3, b: 7}; let v = a + b") == 10

    def test_const_object_destructure_with_rest(self) -> None:
        i = run("const {a, ...rest} = {a: 1, b: 2, c: 3}")
        assert i.globals.get("a") == 1
        assert i.globals.get("rest") == {"b": 2, "c": 3}


# ---------------------------------------------------------------------------
# const in for loops
# ---------------------------------------------------------------------------


class TestConstForLoops:
    def test_const_for_of(self) -> None:
        i = run("var arr = []; for (const item of [1, 2, 3]) { arr.push(item) }; let v = arr")
        assert val(i) == [1, 2, 3]

    def test_const_for_of_sum(self) -> None:
        assert val("var v = 0; for (const x of [1, 2, 3, 4]) { v += x }") == 10

    def test_const_for_in(self) -> None:
        i = run("var keys = []; for (const k in {a: 1, b: 2, c: 3}) { keys.push(k) }; let v = keys.length")
        assert val(i) == 3

    def test_const_for_in_values(self) -> None:
        i = run("var s = 0; const obj = {x: 1, y: 2, z: 3}; for (const k in obj) { s += obj[k] }; let v = s")
        assert val(i) == 6

    def test_const_for_cstyle(self) -> None:
        # const in C-style for init is treated as a mutable loop counter (JS semantics)
        assert val("var v = 0; for (const i = 0; i < 5; i++) { v++ }") == 5

    def test_const_for_of_string(self) -> None:
        i = run('var arr = []; for (const ch of ["a", "b", "c"]) { arr.push(ch) }; let v = arr')
        assert val(i) == ["a", "b", "c"]

    def test_const_for_of_nested(self) -> None:
        i = run("""
var result = []
for (const pair of [[1, 2], [3, 4]]) {
    result.push(pair[0] + pair[1])
}
let v = result
""")
        assert val(i) == [3, 7]


# ---------------------------------------------------------------------------
# for (let i = 0; ...) immutability fix
# ---------------------------------------------------------------------------


class TestLetCStyleFor:
    def test_let_cstyle_sum(self) -> None:
        assert val("var v = 0; for (let i = 0; i < 5; i++) { v += i }") == 10

    def test_let_cstyle_count(self) -> None:
        assert val("var v = 0; for (let i = 0; i < 10; i++) { v++ }") == 10

    def test_let_cstyle_decrement(self) -> None:
        assert val("var v = 0; for (let i = 10; i > 0; i--) { v++ }") == 10

    def test_let_cstyle_step(self) -> None:
        assert val("var v = 0; for (let i = 0; i < 20; i += 2) { v++ }") == 10

    def test_let_cstyle_collect(self) -> None:
        i = run("var arr = []; for (let i = 0; i < 5; i++) { arr.push(i) }; let v = arr")
        assert val(i) == [0, 1, 2, 3, 4]

    def test_let_cstyle_nested(self) -> None:
        i = run("""
var count = 0
for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
        count++
    }
}
let v = count
""")
        assert val(i) == 9

    def test_let_cstyle_break(self) -> None:
        i = run("""
var v = 0
for (let i = 0; i < 100; i++) {
    if (i == 5) { break }
    v++
}
""")
        assert val(i) == 5

    def test_let_cstyle_continue(self) -> None:
        i = run("""
var arr = []
for (let i = 0; i < 6; i++) {
    if (i % 2 == 0) { continue }
    arr.push(i)
}
let v = arr
""")
        assert val(i) == [1, 3, 5]

    def test_let_cstyle_multiple_inits(self) -> None:
        # Multiple comma-separated declarations
        i = run("""
var v = 0
for (let i = 0, j = 10; i < 5; i++, j--) {
    v += i + j
}
""")
        # i=0..4, j=10..6: (0+10)+(1+9)+(2+8)+(3+7)+(4+6) = 10+10+10+10+10 = 50
        assert val(i) == 50


# ---------------------------------------------------------------------------
# constructor method in classes
# ---------------------------------------------------------------------------


class TestConstructorMethod:
    def test_constructor_sets_field(self) -> None:
        assert val("class Point { fn constructor(x) { this.x = x } }; let p = Point.new(7); let v = p.x") == 7

    def test_constructor_multiple_fields(self) -> None:
        i = run("""
class Point {
    fn constructor(x, y) {
        this.x = x
        this.y = y
    }
}
let p = Point.new(3, 4)
let vx = p.x
let vy = p.y
""")
        assert i.globals.get("vx") == 3
        assert i.globals.get("vy") == 4

    def test_constructor_with_method(self) -> None:
        i = run("""
class Counter {
    fn constructor(start) {
        this.count = start
    }
    fn increment() {
        this.count = this.count + 1
    }
    fn get() {
        return this.count
    }
}
let c = Counter.new(10)
c.increment()
c.increment()
let v = c.get()
""")
        assert val(i) == 12

    def test_constructor_inherits(self) -> None:
        i = run("""
class Animal {
    fn constructor(name) {
        this.name = name
    }
}
class Dog extends Animal {
    fn constructor(name, breed) {
        super(name)
        this.breed = breed
    }
}
let d = Dog.new("Rex", "Labrador")
let vname = d.name
let vbreed = d.breed
""")
        assert i.globals.get("vname") == "Rex"
        assert i.globals.get("vbreed") == "Labrador"

    def test_constructor_and_init_equivalent(self) -> None:
        # Both styles should work
        src_init = "class A { fn init(n) { this.n = n } }; let v = A.new(1).n"
        src_ctor = "class B { fn constructor(n) { this.n = n } }; let v = B.new(1).n"
        assert val(src_init) == val(src_ctor)

    def test_constructor_no_args(self) -> None:
        i = run("""
class Greeter {
    fn constructor() {
        this.greeting = "hello"
    }
}
let g = Greeter.new()
let v = g.greeting
""")
        assert val(i) == "hello"

    def test_constructor_super_call(self) -> None:
        i = run("""
class Shape {
    fn constructor(color) {
        this.color = color
    }
}
class Circle extends Shape {
    fn constructor(color, radius) {
        super(color)
        this.radius = radius
    }
    fn area() {
        return 3.14159 * this.radius * this.radius
    }
}
let c = Circle.new("red", 5)
let vcolor = c.color
let vradius = c.radius
""")
        assert i.globals.get("vcolor") == "red"
        assert i.globals.get("vradius") == 5

    def test_constructor_three_levels(self) -> None:
        i = run("""
class A {
    fn constructor(x) { this.x = x }
}
class B extends A {
    fn constructor(x, y) { super(x); this.y = y }
}
class C extends B {
    fn constructor(x, y, z) { super(x, y); this.z = z }
}
let obj = C.new(1, 2, 3)
let vx = obj.x
let vy = obj.y
let vz = obj.z
""")
        assert i.globals.get("vx") == 1
        assert i.globals.get("vy") == 2
        assert i.globals.get("vz") == 3


# ---------------------------------------------------------------------------
# Semicolons in class body
# ---------------------------------------------------------------------------


class TestClassBodySemicolons:
    def test_semicolon_between_methods(self) -> None:
        i = run("""
class Foo {
    fn a() { return 1 };
    fn b() { return 2 }
}
let v = Foo.new().a() + Foo.new().b()
""")
        assert val(i) == 3

    def test_semicolon_after_field(self) -> None:
        i = run("""
class Foo {
    var x = 10;
    fn getX() { return this.x }
}
let v = Foo.new().getX()
""")
        assert val(i) == 10

    def test_multiple_semicolons_between_members(self) -> None:
        i = run("""
class Foo {
    fn a() { return 1 };;
    fn b() { return 2 };;
    fn c() { return 3 }
}
let obj = Foo.new()
let v = obj.a() + obj.b() + obj.c()
""")
        assert val(i) == 6

    def test_semicolon_at_end_of_body(self) -> None:
        i = run("""
class Foo {
    fn greet() { return "hi" };
}
let v = Foo.new().greet()
""")
        assert val(i) == "hi"

    def test_inline_class_semicolons(self) -> None:
        # Single-line class with semicolons between methods
        assert val("class X { fn a() { return 10 }; fn b() { return 20 } }; let v = X.new().a() + X.new().b()") == 30

    def test_semicolon_between_var_and_method(self) -> None:
        i = run("""
class Config {
    var maxRetries = 3;
    var delay = 30;
    fn getDelay() { return this.delay }
}
let v = Config.new().getDelay()
""")
        assert val(i) == 30
