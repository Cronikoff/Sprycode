"""Phase 65 feature tests:
- `using` declaration with object that has `[Symbol.dispose]` method
- `using` declaration in blocks triggers disposal at block exit
- Multiple `using` declarations disposed in LIFO order
- `Symbol.iterator` protocol: custom objects with `[Symbol.iterator]()`
- `Object.create(proto)` creates object with prototype
- `Object.create(null)` creates object with no prototype
- `instanceof` with prototype chain
- Named function expressions self-reference
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
# using declaration — resource management
# ---------------------------------------------------------------------------

class TestUsingDeclarationDispose:
    def test_dispose_called_at_block_exit(self) -> None:
        i = run(
            "let disposed = false\n"
            "let res = { \"[Symbol.dispose]\": fn() { disposed = true } }\n"
            "{\n"
            "  using r = res\n"
            "}\n"
            "let v = disposed"
        )
        assert val(i) is True

    def test_resource_available_inside_block(self) -> None:
        i = run(
            "let res = { value: 42, \"[Symbol.dispose]\": fn() {} }\n"
            "let v = 0\n"
            "{\n"
            "  using r = res\n"
            "  v = r.value\n"
            "}\n"
        )
        assert val(i) == 42

    def test_dispose_not_called_before_block_exit(self) -> None:
        i = run(
            "let disposed = false\n"
            "let res = { \"[Symbol.dispose]\": fn() { disposed = true } }\n"
            "{\n"
            "  using r = res\n"
            "  disposed = false\n"
            "}\n"
            "let v = disposed"
        )
        assert val(i) is True

    def test_multiple_using_lifo_order(self) -> None:
        i = run(
            "let order = []\n"
            "let r1 = { \"[Symbol.dispose]\": fn() { order.push(1) } }\n"
            "let r2 = { \"[Symbol.dispose]\": fn() { order.push(2) } }\n"
            "{\n"
            "  using a = r1\n"
            "  using b = r2\n"
            "}\n"
            "let v = order"
        )
        assert val(i) == [2, 1]

    def test_three_using_lifo_order(self) -> None:
        i = run(
            "let order = []\n"
            "let r1 = { \"[Symbol.dispose]\": fn() { order.push(1) } }\n"
            "let r2 = { \"[Symbol.dispose]\": fn() { order.push(2) } }\n"
            "let r3 = { \"[Symbol.dispose]\": fn() { order.push(3) } }\n"
            "{\n"
            "  using a = r1\n"
            "  using b = r2\n"
            "  using c = r3\n"
            "}\n"
            "let v = order"
        )
        assert val(i) == [3, 2, 1]

    def test_using_with_class_instance(self) -> None:
        i = run(
            "let log = []\n"
            "class Connection {\n"
            "  constructor() { this.open = true }\n"
            "  \"[Symbol.dispose]\"() { this.open = false\n log.push(\"closed\") }\n"
            "}\n"
            "{\n"
            "  using conn = new Connection()\n"
            "  log.push(\"working\")\n"
            "}\n"
            "let v = log"
        )
        assert val(i) == ["working", "closed"]

    def test_using_dispose_with_value(self) -> None:
        i = run(
            "let calls = 0\n"
            "let res = { \"[Symbol.dispose]\": fn() { calls = calls + 1 } }\n"
            "{\n"
            "  using r = res\n"
            "}\n"
            "{\n"
            "  using r2 = res\n"
            "}\n"
            "let v = calls"
        )
        assert val(i) == 2


# ---------------------------------------------------------------------------
# Symbol.iterator protocol
# ---------------------------------------------------------------------------

class TestSymbolIteratorProtocol:
    def test_spread_custom_iterable(self) -> None:
        i = run(
            "class NumRange {\n"
            "  constructor() { this.lo = 1\n this.hi = 3 }\n"
            "  \"[Symbol.iterator]\"() {\n"
            "    let cur = this.lo\n"
            "    let hi = this.hi\n"
            "    return {\n"
            "      next: fn() {\n"
            "        if (cur <= hi) {\n"
            "          let v = cur\n"
            "          cur = cur + 1\n"
            "          return { value: v, done: false }\n"
            "        }\n"
            "        return { value: undefined, done: true }\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "}\n"
            "let r = new NumRange()\n"
            "let v = [...r]"
        )
        result = val(i)
        assert 1 in result
        assert 2 in result
        assert 3 in result

    def test_for_of_custom_iterable(self) -> None:
        i = run(
            "class Counter {\n"
            "  constructor() { this.max = 3 }\n"
            "  \"[Symbol.iterator]\"() {\n"
            "    let n = 1\n"
            "    let max = this.max\n"
            "    return {\n"
            "      next: fn() {\n"
            "        if (n <= max) {\n"
            "          let v = n\n"
            "          n = n + 1\n"
            "          return { value: v, done: false }\n"
            "        }\n"
            "        return { value: 0, done: true }\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "}\n"
            "let sum = 0\n"
            "for (let x of new Counter()) { sum = sum + x }\n"
            "let v = sum"
        )
        assert val(i) == 6

    def test_array_has_iterator(self) -> None:
        i = run(
            "let arr = [10, 20, 30]\n"
            "let v = 0\n"
            "for (let x of arr) { v = v + x }"
        )
        assert val(i) == 60

    def test_string_is_iterable(self) -> None:
        i = run('let v = [...\"abc\"]')
        assert val(i) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Object.create
# ---------------------------------------------------------------------------

class TestObjectCreate:
    def test_create_with_proto(self) -> None:
        i = run(
            "let proto = { greet: fn() { return \"hello\" } }\n"
            "let obj = Object.create(proto)\n"
            "let v = obj.greet()"
        )
        assert val(i) == "hello"

    def test_create_null(self) -> None:
        i = run(
            "let obj = Object.create(null)\n"
            "obj.x = 42\n"
            "let v = obj.x"
        )
        assert val(i) == 42

    def test_create_inherits_methods(self) -> None:
        i = run(
            "let animal = { speak: fn() { return \"...\" } }\n"
            "let dog = Object.create(animal)\n"
            "dog.speak = fn() { return \"woof\" }\n"
            "let v = dog.speak()"
        )
        assert val(i) == "woof"

    def test_create_with_properties(self) -> None:
        i = run(
            "let proto = { type: \"base\" }\n"
            "let child = Object.create(proto)\n"
            "child.name = \"child\"\n"
            "let v = child.name"
        )
        assert val(i) == "child"

    def test_get_prototype_of(self) -> None:
        i = run(
            "let proto = { x: 1 }\n"
            "let obj = Object.create(proto)\n"
            "let p = Object.getPrototypeOf(obj)\n"
            "let v = p.x"
        )
        assert val(i) == 1


# ---------------------------------------------------------------------------
# instanceof with prototype chain
# ---------------------------------------------------------------------------

class TestInstanceofChain:
    def test_instanceof_direct(self) -> None:
        i = run(
            "class Foo {}\n"
            "let f = new Foo()\n"
            "let v = f instanceof Foo"
        )
        assert val(i) is True

    def test_instanceof_superclass(self) -> None:
        i = run(
            "class Animal {}\n"
            "class Dog extends Animal {}\n"
            "let d = new Dog()\n"
            "let v = d instanceof Animal"
        )
        assert val(i) is True

    def test_instanceof_subclass(self) -> None:
        i = run(
            "class Animal {}\n"
            "class Dog extends Animal {}\n"
            "let d = new Dog()\n"
            "let v = d instanceof Dog"
        )
        assert val(i) is True

    def test_not_instanceof(self) -> None:
        i = run(
            "class Cat {}\n"
            "class Dog {}\n"
            "let d = new Dog()\n"
            "let v = d instanceof Cat"
        )
        assert val(i) is False

    def test_instanceof_deep_chain(self) -> None:
        i = run(
            "class A {}\n"
            "class B extends A {}\n"
            "class C extends B {}\n"
            "let c = new C()\n"
            "let v = c instanceof A"
        )
        assert val(i) is True


# ---------------------------------------------------------------------------
# Named function expressions self-reference
# ---------------------------------------------------------------------------

class TestNamedFunctionSelfReference:
    def test_fibonacci(self) -> None:
        i = run(
            "let fib = function fibonacci(n) {\n"
            "  if (n <= 1) { return n }\n"
            "  return fibonacci(n - 1) + fibonacci(n - 2)\n"
            "}\n"
            "let v = fib(6)"
        )
        assert val(i) == 8

    def test_countdown(self) -> None:
        i = run(
            "let result = []\n"
            "let c = function countdown(n) {\n"
            "  if (n < 0) { return }\n"
            "  result.push(n)\n"
            "  countdown(n - 1)\n"
            "}\n"
            "c(3)\n"
            "let v = result"
        )
        assert val(i) == [3, 2, 1, 0]


# ---------------------------------------------------------------------------
# Additional using declaration edge cases
# ---------------------------------------------------------------------------

class TestUsingEdgeCases:
    def test_using_in_nested_blocks(self) -> None:
        i = run(
            "let log = []\n"
            "let r1 = { \"[Symbol.dispose]\": fn() { log.push(\"outer\") } }\n"
            "let r2 = { \"[Symbol.dispose]\": fn() { log.push(\"inner\") } }\n"
            "{\n"
            "  using outer = r1\n"
            "  {\n"
            "    using inner = r2\n"
            "  }\n"
            "}\n"
            "let v = log"
        )
        assert val(i) == ["inner", "outer"]

    def test_using_value_accessible(self) -> None:
        i = run(
            "let res = { data: \"hello\", \"[Symbol.dispose]\": fn() {} }\n"
            "let captured = \"\"\n"
            "{\n"
            "  using r = res\n"
            "  captured = r.data\n"
            "}\n"
            "let v = captured"
        )
        assert val(i) == "hello"
