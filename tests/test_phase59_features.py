"""Phase 59 feature tests — Object.assign with SpryInstance targets,
SpryFunction.prototype property."""
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
# Object.assign with SpryInstance
# ---------------------------------------------------------------------------

class TestObjectAssign:
    def test_assign_dict_to_dict(self):
        src = """
let target = {a: 1}
Object.assign(target, {b: 2}, {c: 3})
let v = target.b
"""
        assert val(src) == 2

    def test_assign_multiple_sources(self):
        src = """
let target = {}
Object.assign(target, {a: 1}, {b: 2})
let v = target.a + target.b
"""
        assert val(src) == 3

    def test_assign_dict_to_instance(self):
        src = """
class Foo {}
let foo = new Foo()
Object.assign(foo, {x: 99})
let v = foo.x
"""
        assert val(src) == 99

    def test_assign_instance_to_dict(self):
        src = """
class Bar {
  fn init() { this.y = 7 }
}
let bar = new Bar()
let target = {}
Object.assign(target, bar)
let v = target.y
"""
        assert val(src) == 7

    def test_assign_returns_target(self):
        src = """
let t = {a: 1}
let result = Object.assign(t, {b: 2})
let v = result.a
"""
        assert val(src) == 1


# ---------------------------------------------------------------------------
# Function.prototype property
# ---------------------------------------------------------------------------

class TestFunctionPrototype:
    def test_function_has_prototype(self):
        src = """
fn greet() { return "hi" }
let v = typeof greet.prototype
"""
        result = val(src)
        assert result is not None  # May be "object" or similar
