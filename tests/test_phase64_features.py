"""Phase 64 feature tests:
- `function` keyword works like `fn` (declarations and expressions)
- `function* gen()` generator declarations
- `async function foo()` async declarations
- `new.target` returns the constructor name in class constructors
- `new.target` returns null outside constructor
- Subclass `new.target` in super constructor
- Named function expressions
"""
from __future__ import annotations
from typing import Any
import pytest
from sprycode.interpreter import Interpreter, SpryRuntimeError
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
# function keyword as alias for fn
# ---------------------------------------------------------------------------

class TestFunctionKeyword:
    def test_function_declaration(self) -> None:
        i = run("function add(x, y) { return x + y }\nlet v = add(3, 4)")
        assert val(i) == 7

    def test_function_no_args(self) -> None:
        i = run("function greet() { return \"hello\" }\nlet v = greet()")
        assert val(i) == "hello"

    def test_function_expression(self) -> None:
        i = run("let add = function(x, y) { return x + y }\nlet v = add(10, 5)")
        assert val(i) == 15

    def test_function_with_default(self) -> None:
        i = run("function greet(name = \"world\") { return \"hello \" + name }\nlet v = greet()")
        assert val(i) == "hello world"

    def test_function_recursive(self) -> None:
        i = run(
            "function factorial(n) {\n"
            "  if (n <= 1) { return 1 }\n"
            "  return n * factorial(n - 1)\n"
            "}\n"
            "let v = factorial(5)"
        )
        assert val(i) == 120

    def test_function_closes_over_variable(self) -> None:
        i = run(
            "let x = 10\n"
            "function getX() { return x }\n"
            "let v = getX()"
        )
        assert val(i) == 10

    def test_function_name_property(self) -> None:
        i = run("function myFn() { return 1 }\nlet v = myFn.name")
        assert val(i) == "myFn"

    def test_function_is_callable(self) -> None:
        i = run("function f() { return 99 }\nlet v = typeof f")
        assert val(i) == "function"


# ---------------------------------------------------------------------------
# Named function expressions
# ---------------------------------------------------------------------------

class TestNamedFunctionExpression:
    def test_callable_by_outer_name(self) -> None:
        i = run("let f = function myFunc() { return 42 }\nlet v = f()")
        assert val(i) == 42

    def test_name_accessible_inside(self) -> None:
        i = run("let f = function myFunc() { return myFunc.name }\nlet v = f()")
        assert val(i) == "myFunc"

    def test_recursive_named(self) -> None:
        i = run(
            "let fact = function factorial(n) {\n"
            "  if (n <= 1) { return 1 }\n"
            "  return n * factorial(n - 1)\n"
            "}\n"
            "let v = fact(5)"
        )
        assert val(i) == 120

    def test_name_is_set(self) -> None:
        i = run("let f = function namedFn() { return 1 }\nlet v = f.name")
        assert val(i) == "namedFn"


# ---------------------------------------------------------------------------
# function* generator declarations
# ---------------------------------------------------------------------------

class TestGeneratorFunctionKeyword:
    def test_basic_generator(self) -> None:
        i = run(
            "function* gen() {\n"
            "  yield 1\n"
            "  yield 2\n"
            "  yield 3\n"
            "}\n"
            "let v = [...gen()]"
        )
        assert val(i) == [1, 2, 3]

    def test_generator_for_of(self) -> None:
        i = run(
            "function* range(n) {\n"
            "  let i = 0\n"
            "  while (i < n) { yield i\n i = i + 1 }\n"
            "}\n"
            "let v = 0\n"
            "for (let x of range(3)) { v = v + x }"
        )
        assert val(i) == 3

    def test_generator_next(self) -> None:
        i = run(
            "function* gen() { yield 10; yield 20 }\n"
            "let g = gen()\n"
            "let a = g.next().value\n"
            "let b = g.next().value\n"
            "let v = a + b"
        )
        assert val(i) == 30

    def test_generator_infinite(self) -> None:
        i = run(
            "function* naturals() {\n"
            "  let n = 1\n"
            "  while (true) { yield n\n n = n + 1 }\n"
            "}\n"
            "let g = naturals()\n"
            "let v = [g.next().value, g.next().value, g.next().value]"
        )
        assert val(i) == [1, 2, 3]

    def test_generator_return_value(self) -> None:
        i = run(
            "function* gen() { yield 1 }\n"
            "let g = gen()\n"
            "g.next()\n"
            "let v = g.next().done"
        )
        assert val(i) is True


# ---------------------------------------------------------------------------
# async function declarations
# ---------------------------------------------------------------------------

class TestAsyncFunctionKeyword:
    def test_async_returns_promise(self) -> None:
        i = run("async function fetch() { return 42 }\nlet p = fetch()\nlet v = p.value")
        assert val(i) == 42

    def test_async_with_await(self) -> None:
        i = run(
            "async function compute() {\n"
            "  let x = await Promise.resolve(10)\n"
            "  return x * 2\n"
            "}\n"
            "let p = compute()\nlet v = p.value"
        )
        assert val(i) == 20

    def test_async_name(self) -> None:
        i = run("async function myAsync() { return 1 }\nlet v = myAsync.name")
        assert val(i) == "myAsync"

    def test_async_expression(self) -> None:
        i = run(
            "let f = async function() { return 99 }\n"
            "let p = f()\nlet v = p.value"
        )
        assert val(i) == 99


# ---------------------------------------------------------------------------
# new.target
# ---------------------------------------------------------------------------

class TestNewTarget:
    def test_new_target_in_constructor(self) -> None:
        i = run(
            "class Foo {\n"
            "  constructor() { this.t = new.target }\n"
            "}\n"
            "let obj = new Foo()\nlet v = obj.t"
        )
        assert val(i) == "Foo"

    def test_new_target_outside_constructor(self) -> None:
        i = run("let v = new.target")
        assert val(i) is None

    def test_new_target_in_function(self) -> None:
        i = run("function f() { return new.target }\nlet v = f()")
        assert val(i) is None

    def test_new_target_subclass_in_base(self) -> None:
        i = run(
            "class Base {\n"
            "  constructor() { this.target = new.target }\n"
            "}\n"
            "class Child extends Base {\n"
            "  constructor() { super() }\n"
            "}\n"
            "let c = new Child()\nlet v = c.target"
        )
        assert val(i) == "Child"

    def test_new_target_direct_class(self) -> None:
        i = run(
            "class Widget {\n"
            "  constructor() { this.t = new.target }\n"
            "}\n"
            "let w = new Widget()\nlet v = w.t"
        )
        assert val(i) == "Widget"

    def test_new_target_multiple_classes(self) -> None:
        i = run(
            "class A {\n"
            "  constructor() { this.t = new.target }\n"
            "}\n"
            "class B {\n"
            "  constructor() { this.t = new.target }\n"
            "}\n"
            "let a = new A()\nlet b = new B()\n"
            "let v = a.t + \",\" + b.t"
        )
        assert val(i) == "A,B"

    def test_new_target_restores_after_construction(self) -> None:
        i = run(
            "class Foo {\n"
            "  constructor() { this.t = new.target }\n"
            "}\n"
            "new Foo()\nlet v = new.target"
        )
        assert val(i) is None
