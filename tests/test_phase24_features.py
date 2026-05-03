"""Phase 24 feature tests."""
from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import (
    Interpreter,
    SpryRuntimeError,
)
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


# ---------------------------------------------------------------------------
# FIX 1: for await..of
# ---------------------------------------------------------------------------


def test_for_await_of_generator() -> None:
    i = run("""
fn* gen() { yield 1\nyield 2\nyield 3 }
var s = 0
for await x of gen() { s = s + x }
let v = s
""")
    assert i.globals.get("v") == 6


def test_for_await_of_array() -> None:
    i = run("""
var s = 0
for await x of [10, 20, 30] { s = s + x }
let v = s
""")
    assert i.globals.get("v") == 60


def test_for_await_of_behaves_same_as_sync() -> None:
    i = run("""
var result = []
for await item of ["a", "b", "c"] { result.push(item) }
let v = result[1]
""")
    assert i.globals.get("v") == "b"


# ---------------------------------------------------------------------------
# FIX 2: Object literal getters and setters
# ---------------------------------------------------------------------------


def test_object_literal_getter() -> None:
    i = run("""
let o = { get x() { return 42 } }
let v = o.x
""")
    assert i.globals.get("v") == 42


def test_object_literal_getter_computed() -> None:
    i = run("""
let val = 100
let o = { get value() { return val * 2 } }
let v = o.value
""")
    assert i.globals.get("v") == 200


def test_object_literal_setter() -> None:
    i = run("""
var stored = 0
let o = { set x(v) { stored = v } }
o.x = 99
let v = stored
""")
    assert i.globals.get("v") == 99


def test_object_getter_setter_pair() -> None:
    i = run("""
var _v = 0
let o = {
  get value() { return _v },
  set value(x) { _v = x }
}
o.value = 55
let v = o.value
""")
    assert i.globals.get("v") == 55


# ---------------------------------------------------------------------------
# FIX 3: Class computed methods [Symbol.iterator]()
# ---------------------------------------------------------------------------


def test_class_computed_method_stored() -> None:
    i = run("""
class Coll {
  [Symbol.iterator]() {
    return { next: () => ({ value: 1, done: false }) }
  }
}
let c = new Coll()
let v = typeof c[Symbol.iterator]
""")
    assert i.globals.get("v") == "Function"


def test_class_computed_method_callable() -> None:
    i = run("""
class Counter {
  fn init() { self.val = 0 }
  [Symbol.iterator]() {
    self.val = self.val + 1
    return self.val
  }
}
let c = new Counter()
c[Symbol.iterator]()
let v = c[Symbol.iterator]()
""")
    assert i.globals.get("v") == 2


# ---------------------------------------------------------------------------
# FIX 4: Optional call ?.()
# ---------------------------------------------------------------------------


def test_optional_call_null_returns_none() -> None:
    i = run("let f = null\nlet v = f?.()")
    assert i.globals.get("v") is None


def test_optional_call_with_function() -> None:
    i = run("fn double(x) { return x * 2 }\nlet v = double?.(7)")
    assert i.globals.get("v") == 14


def test_optional_call_with_arrow_function() -> None:
    i = run("let f = x => x + 10\nlet v = f?.(5)")
    assert i.globals.get("v") == 15


def test_optional_call_with_lambda() -> None:
    i = run("let f = x => x * x\nlet v = f?.(6)")
    assert i.globals.get("v") == 36


def test_optional_call_on_undefined_safe() -> None:
    i = run("""
let obj = { f: null }
let v = obj.f?.()
""")
    assert i.globals.get("v") is None


# ---------------------------------------------------------------------------
# FIX 5: Regex flag string properties
# ---------------------------------------------------------------------------


def test_regex_flags_string() -> None:
    i = run("let r = /ab/gi\nlet v = r.flags")
    assert i.globals.get("v") == "gi"


def test_regex_flags_empty() -> None:
    i = run("let r = /hello/\nlet v = r.flags")
    assert i.globals.get("v") == ""


def test_regex_flags_multiline() -> None:
    i = run("let r = /abc/m\nlet v = r.flags")
    assert i.globals.get("v") == "m"


def test_regex_global_property() -> None:
    i = run("let r = /x/g\nlet v = r.global")
    assert i.globals.get("v") is True


def test_regex_ignorecase_property() -> None:
    i = run("let r = /x/i\nlet v = r.ignoreCase")
    assert i.globals.get("v") is True


def test_regex_multiline_property() -> None:
    i = run("let r = /x/m\nlet v = r.multiline")
    assert i.globals.get("v") is True


def test_regex_lastindex_property() -> None:
    i = run("let r = /x/g\nlet v = r.lastIndex")
    assert i.globals.get("v") == 0


# ---------------------------------------------------------------------------
# FIX 6: Safe typeof for undeclared variables
# ---------------------------------------------------------------------------


def test_typeof_undeclared_returns_undefined() -> None:
    i = run("let v = typeof TOTALLY_UNDECLARED_VAR_XYZ123")
    assert i.globals.get("v") == "undefined"


def test_typeof_null_returns_null() -> None:
    i = run("let v = typeof null")
    assert i.globals.get("v") == "Null"


def test_typeof_number_returns_int() -> None:
    i = run("let v = typeof 42")
    assert i.globals.get("v") == "Int"


def test_typeof_string_returns_text() -> None:
    i = run('let v = typeof "hello"')
    assert i.globals.get("v") == "Text"


def test_typeof_declared_null_is_null() -> None:
    i = run("let x = null\nlet v = typeof x")
    assert i.globals.get("v") == "Null"


# ---------------------------------------------------------------------------
# FIX 7: await unwraps Promise.allSettled
# ---------------------------------------------------------------------------


def test_await_promise_allsettled_unwraps() -> None:
    i = run("""
let r = await Promise.allSettled([Promise.resolve(1), Promise.resolve(2)])
let v = r[0].value
""")
    assert i.globals.get("v") == 1


def test_await_promise_allsettled_rejected() -> None:
    i = run("""
let r = await Promise.allSettled([Promise.reject("oops"), Promise.resolve(42)])
let v = r[1].value
""")
    assert i.globals.get("v") == 42


def test_await_promise_resolve_unwraps() -> None:
    i = run("""
let p = Promise.resolve(100)
let v = await p
""")
    assert i.globals.get("v") == 100


# ---------------------------------------------------------------------------
# FIX 8: globalThis.undefined
# ---------------------------------------------------------------------------


def test_globalthis_undefined_is_none() -> None:
    i = run("let v = globalThis.undefined")
    assert i.globals.get("v") is None


def test_globalthis_undefined_comparison() -> None:
    i = run("let v = globalThis.undefined == null")
    assert i.globals.get("v") is True


def test_globalthis_undefined_typeof() -> None:
    i = run("let v = typeof globalThis.undefined")
    assert i.globals.get("v") == "Null"


# ---------------------------------------------------------------------------
# FIX 9: Class static getters and setters
# ---------------------------------------------------------------------------


def test_class_static_getter() -> None:
    i = run("""
class MathHelper {
  static get pi() { return 3.14159 }
}
let v = MathHelper.pi
""")
    assert i.globals.get("v") == pytest.approx(3.14159)


def test_class_static_getter_computed() -> None:
    i = run("""
let factor = 2
class Scale {
  static get double() { return factor * 100 }
}
let v = Scale.double
""")
    assert i.globals.get("v") == 200


def test_class_static_getter_with_method() -> None:
    i = run("""
class Config {
  static get version() { return "1.0" }
  static fn greet() { return "hi" }
}
let v = Config.version
let w = Config.greet()
""")
    assert i.globals.get("v") == "1.0"
    assert i.globals.get("w") == "hi"


# ---------------------------------------------------------------------------
# FIX 10: array.flat(Infinity)
# ---------------------------------------------------------------------------


def test_flat_infinity() -> None:
    i = run("let arr = [[1, [2, [3, [4]]]]]\nlet v = arr.flat(Infinity)")
    assert i.globals.get("v") == [1, 2, 3, 4]


def test_flat_infinity_deeply_nested() -> None:
    i = run("let arr = [[[[[1]]]]]\nlet v = arr.flat(Infinity)")
    assert i.globals.get("v") == [1]


def test_flat_depth_1() -> None:
    i = run("let arr = [[1, [2, 3]], [4]]\nlet v = arr.flat(1)")
    assert i.globals.get("v") == [1, [2, 3], 4]


def test_flat_default_depth() -> None:
    i = run("let arr = [[1, 2], [3, 4]]\nlet v = arr.flat()")
    assert i.globals.get("v") == [1, 2, 3, 4]
