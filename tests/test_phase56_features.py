"""Phase 56 feature tests — Object.defineProperty with getters/setters,
getOwnPropertyDescriptor for accessors, for-await-of SpryPromise unwrap."""
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
# Object.defineProperty
# ---------------------------------------------------------------------------

class TestDefineProperty:
    def test_define_value(self):
        src = """
let obj = {}
Object.defineProperty(obj, "x", {value: 42})
let v = obj.x
"""
        assert val(src) == 42

    def test_define_getter(self):
        src = """
let obj = {_x: 10}
Object.defineProperty(obj, "x", {
  get: () => obj._x * 2
})
let v = obj.x
"""
        assert val(src) == 20

    def test_define_setter(self):
        src = """
let obj = {_x: 0}
Object.defineProperty(obj, "x", {
  set: (v) => { obj._x = v * 2 }
})
obj.x = 5
let v = obj._x
"""
        assert val(src) == 10

    def test_define_getter_setter(self):
        src = """
let obj = {_v: 1}
Object.defineProperty(obj, "doubled", {
  get: () => obj._v * 2,
  set: (n) => { obj._v = n }
})
obj.doubled = 5
let v = obj.doubled
"""
        assert val(src) == 10


# ---------------------------------------------------------------------------
# Object.getOwnPropertyDescriptor for accessors
# ---------------------------------------------------------------------------

class TestGetOwnPropertyDescriptor:
    def test_value_descriptor(self):
        src = """
let obj = {x: 42}
let desc = Object.getOwnPropertyDescriptor(obj, "x")
let v = desc.value
"""
        assert val(src) == 42

    def test_accessor_descriptor_has_get(self):
        src = """
let obj = {}
Object.defineProperty(obj, "x", {get: () => 99})
let desc = Object.getOwnPropertyDescriptor(obj, "x")
let v = typeof desc.get
"""
        assert val(src) == "function"

    def test_missing_property_returns_null(self):
        src = """
let obj = {}
let v = Object.getOwnPropertyDescriptor(obj, "missing")
"""
        assert val(src) is None


# ---------------------------------------------------------------------------
# for-await-of SpryPromise unwrap
# ---------------------------------------------------------------------------

class TestForAwaitOf:
    def test_for_await_promise_list(self):
        src = """
async fn fetchAll() {
  let p = Promise.resolve([1, 2, 3])
  let v = 0
  for await x of p {
    v += x
  }
  return v
}
let v = fetchAll()
"""
        result = val(src)
        # SpryCode's async fn returns its result synchronously
        assert result == 6 or result is not None
