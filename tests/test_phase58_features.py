"""Phase 58 feature tests.

Covers:
- `function fn(...)` / `fn` used as identifier after `function` keyword
- for-cstyle body without braces (single statement): `for (...) stmt`
- Plain dict with `[Symbol.iterator]` — for-of and spread support
- `Object.preventExtensions` / `Object.isExtensible` on `_ObjectNamespace`
- `Error.captureStackTrace` stub
- `strings.raw` property in tagged template literals
"""

import pytest
from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


# ---------------------------------------------------------------------------
# `fn` / `function` as identifier after function keyword
# ---------------------------------------------------------------------------

def test_function_keyword_fn_name_call():
    """function fn(x) should define a function named 'fn' callable as fn(...)."""
    i = run("""
function fn(x) { return x * 2 }
let v = fn(5)
""")
    assert i.globals["v"] == 10


def test_function_keyword_fn_obj_destruct_param():
    """function fn({x, y}) should parse fn as the name and {x,y} as destructured param."""
    i = run("""
function fn({x, y}) { return x + y }
let v = fn({x: 3, y: 4})
""")
    assert i.globals["v"] == 7


def test_function_keyword_fn_arr_destruct_param():
    """function fn([a, b]) should parse fn as name and [a,b] as destructured param."""
    i = run("""
function fn([a, b]) { return a * b }
let v = fn([6, 7])
""")
    assert i.globals["v"] == 42


def test_function_keyword_fn_name_rest_param():
    """function fn(...args) — fn as name with rest param."""
    i = run("""
function fn(...args) { return args.length }
let v = fn(1, 2, 3, 4)
""")
    assert i.globals["v"] == 4


def test_function_keyword_fn_name_default_param():
    """function fn(x, y = 10) — fn as name with default param."""
    i = run("""
function fn(x, y = 10) { return x + y }
let v = fn(5)
""")
    assert i.globals["v"] == 15


def test_function_keyword_fn_name_multiline():
    """function fn(...) used across multiple calls."""
    i = run("""
function fn(a, b, c) { return a + b + c }
let v = fn(1, 2, 3)
""")
    assert i.globals["v"] == 6


def test_fn_anonymous_expression_still_works():
    """fn(x) { body } anonymous function expression should still work."""
    i = run("""
let double = fn(x) { return x * 2 }
let v = double(7)
""")
    assert i.globals["v"] == 14


def test_fn_anonymous_arrow_still_works():
    """fn(x) => expr anonymous arrow form should still work."""
    i = run("""
let triple = fn(x) => x * 3
let v = triple(4)
""")
    assert i.globals["v"] == 12


def test_fn_as_variable_name_called():
    """'fn' used as a variable name (assigned an arrow function) and called."""
    i = run("""
let fn = x => x + 100
let v = fn(5)
""")
    assert i.globals["v"] == 105


# ---------------------------------------------------------------------------
# for-cstyle single-statement body (no braces)
# ---------------------------------------------------------------------------

def test_for_cstyle_no_braces_simple():
    """for (let i = 0; i < 3; i++) v.push(i) — no braces."""
    i = run("""
let v = []
for (let i = 0; i < 3; i++) v.push(i)
""")
    assert i.globals["v"] == [0, 1, 2]


def test_for_cstyle_no_braces_generator():
    """for-cstyle without braces inside a generator function."""
    i = run("""
function* range(n) {
  for (let i = 0; i < n; i++) yield i
}
let v = []
for (let x of range(5)) { v.push(x) }
""")
    assert i.globals["v"] == [0, 1, 2, 3, 4]


def test_for_cstyle_no_braces_if_inside():
    """for-cstyle with if as single body (no braces on if)."""
    i = run("""
let v = []
for (let i = 0; i < 5; i++) if (i % 2 === 0) v.push(i)
""")
    assert i.globals["v"] == [0, 2, 4]


def test_for_cstyle_no_braces_nested_continue():
    """for-cstyle without braces, body with continue."""
    i = run("""
let v = []
for (let i = 0; i < 5; i++) {
  if (i === 2) continue
  v.push(i)
}
""")
    assert i.globals["v"] == [0, 1, 3, 4]


# ---------------------------------------------------------------------------
# Plain dict with [Symbol.iterator]
# ---------------------------------------------------------------------------

def test_dict_symbol_iterator_spread():
    """Spread a dict that has [Symbol.iterator] defined."""
    i = run("""
let obj = {}
obj[Symbol.iterator] = function() {
  let n = 0
  return {
    next() {
      n++
      return n <= 3 ? {value: n, done: false} : {value: undefined, done: true}
    }
  }
}
let v = [...obj]
""")
    assert i.globals["v"] == [1, 2, 3]


def test_dict_symbol_iterator_for_of():
    """for...of over a dict that has [Symbol.iterator]."""
    i = run("""
let obj = {}
obj[Symbol.iterator] = function() {
  let items = [10, 20, 30]
  let idx = 0
  return {
    next: function() {
      return idx < items.length
        ? {value: items[idx++], done: false}
        : {value: undefined, done: true}
    }
  }
}
let v = []
for (let x of obj) { v.push(x) }
""")
    assert i.globals["v"] == [10, 20, 30]


def test_dict_symbol_iterator_this_binding():
    """[Symbol.iterator] function can access dict fields via this."""
    i = run("""
let range = { start: 1, end: 4 }
range[Symbol.iterator] = function() {
  let cur = this.start
  let end = this.end
  return {
    next: function() {
      return cur <= end
        ? {value: cur++, done: false}
        : {value: undefined, done: true}
    }
  }
}
let v = [...range]
""")
    assert i.globals["v"] == [1, 2, 3, 4]


def test_dict_symbol_iterator_array_from():
    """Array.from works with a dict [Symbol.iterator]."""
    i = run("""
let counter = {}
counter[Symbol.iterator] = function() {
  let i = 0
  return {
    next() { return i < 4 ? {value: i++, done: false} : {value: undefined, done: true} }
  }
}
let v = Array.from(counter)
""")
    assert i.globals["v"] == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# Object.preventExtensions / Object.isExtensible
# ---------------------------------------------------------------------------

def test_object_is_extensible_fresh():
    """Fresh objects are extensible."""
    i = run("""
let o = {x: 1}
let v = Object.isExtensible(o)
""")
    assert i.globals["v"] is True


def test_object_prevent_extensions():
    """Object.preventExtensions makes object not extensible."""
    i = run("""
let o = {x: 1}
Object.preventExtensions(o)
let v = Object.isExtensible(o)
""")
    assert i.globals["v"] is False


def test_object_prevent_extensions_returns_obj():
    """Object.preventExtensions returns the object."""
    i = run("""
let o = {x: 42}
let v = Object.preventExtensions(o).x
""")
    assert i.globals["v"] == 42


def test_object_frozen_not_extensible():
    """Object.freeze also makes an object not extensible."""
    i = run("""
let o = Object.freeze({x: 1})
let v = Object.isExtensible(o)
""")
    assert i.globals["v"] is False


def test_object_is_extensible_instance():
    """isExtensible works on SpryInstance too."""
    i = run("""
class Box { constructor(v) { this.v = v } }
let b = new Box(1)
let before = Object.isExtensible(b)
Object.preventExtensions(b)
let after = Object.isExtensible(b)
let v = [before, after]
""")
    assert i.globals["v"] == [True, False]


# ---------------------------------------------------------------------------
# Error.captureStackTrace stub
# ---------------------------------------------------------------------------

def test_error_capture_stack_trace_type():
    """Error.captureStackTrace should be a callable (function)."""
    i = run("""
let v = typeof Error.captureStackTrace
""")
    assert i.globals["v"] == "function"


def test_error_capture_stack_trace_callable():
    """Error.captureStackTrace(obj) should not throw."""
    i = run("""
class MyError extends Error {
  constructor(msg) {
    super(msg)
    Error.captureStackTrace(this)
  }
}
let e = new MyError("oops")
let v = e.message
""")
    assert i.globals["v"] == "oops"


def test_error_capture_stack_trace_two_args():
    """Error.captureStackTrace(obj, ctor) should not throw."""
    i = run("""
function Err(msg) {
  this.message = msg
  Error.captureStackTrace(this, Err)
}
let e = new Err("bad")
let v = e.message
""")
    assert i.globals["v"] == "bad"


# ---------------------------------------------------------------------------
# strings.raw in tagged templates
# ---------------------------------------------------------------------------

def test_tagged_template_raw_property():
    """Tag function can access strings.raw[0] for raw string parts."""
    i = run(r"""
function tag(strings) {
  return strings.raw[0]
}
let v = tag`hello\nworld`
""")
    assert i.globals["v"] == r"hello\nworld"


def test_tagged_template_cooked_vs_raw():
    """strings[0] is cooked (escape processed), strings.raw[0] is not."""
    i = run(r"""
function tag(strings) {
  return [strings[0], strings.raw[0]]
}
let v = tag`hello\nworld`
""")
    cooked, raw = i.globals["v"]
    assert cooked == "hello\nworld"
    assert raw == r"hello\nworld"


def test_tagged_template_raw_multiple_parts():
    """strings.raw has multiple parts when template has interpolations."""
    i = run(r"""
let x = "world"
function tag(strings, ...vals) {
  return strings.raw
}
let v = tag`hello\n${x}\tthere`
""")
    parts = i.globals["v"]
    assert parts[0] == r"hello\n"
    assert parts[1] == r"\tthere"


def test_string_raw_still_works():
    """String.raw tag still works correctly via strings.raw."""
    i = run(r"""
let v = String.raw`hello\nworld`
""")
    assert i.globals["v"] == r"hello\nworld"


def test_string_raw_with_interpolation():
    """String.raw with interpolation preserves raw parts."""
    i = run(r"""
let name = "World"
let v = String.raw`Hello\t${name}!\n`
""")
    assert i.globals["v"] == r"Hello\tWorld!\n"


def test_tagged_template_receives_values():
    """Tag function receives evaluated expression values correctly."""
    i = run("""
function tag(strings, ...vals) {
  return vals
}
let a = 1
let b = 2
let v = tag`a=${a} b=${b} sum=${a+b}`
""")
    assert i.globals["v"] == [1, 2, 3]


def test_tagged_template_raw_join():
    """Tag function that joins raw parts to reconstruct template."""
    i = run(r"""
function highlight(strings, ...vals) {
  let result = ""
  for (let i = 0; i < strings.raw.length; i++) {
    result += strings.raw[i]
    if (i < vals.length) { result += "[" + vals[i] + "]" }
  }
  return result
}
let x = 42
let v = highlight`value is\t${x}\ndone`
""")
    assert i.globals["v"] == r"value is\t[42]\ndone"
