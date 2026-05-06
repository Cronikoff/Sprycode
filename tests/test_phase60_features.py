"""Phase 60 feature tests — static method inheritance."""
import pytest
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.interpreter import Interpreter


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(src: str, name: str = "v"):
    return run(src).globals.get(name)


# ---------------------------------------------------------------------------
# Static method inheritance
# ---------------------------------------------------------------------------

class TestStaticMethodInheritance:
    def test_static_method_inherited(self):
        src = """
class Animal {
  static fn describe() { return "I am an animal" }
}
class Dog extends Animal {}
let v = Dog.describe()
"""
        assert val(src) == "I am an animal"

    def test_static_field_inherited(self):
        src = """
class Vehicle {
  static let count = 0
}
class Car extends Vehicle {}
let v = Car.count
"""
        assert val(src) == 0

    def test_overridden_static_method(self):
        src = """
class Base {
  static fn greet() { return "hello from Base" }
}
class Child extends Base {
  static fn greet() { return "hello from Child" }
}
let v = Child.greet()
"""
        assert val(src) == "hello from Child"

    def test_deep_static_inheritance(self):
        src = """
class A {
  static fn ping() { return "pong" }
}
class B extends A {}
class C extends B {}
let v = C.ping()
"""
        assert val(src) == "pong"
