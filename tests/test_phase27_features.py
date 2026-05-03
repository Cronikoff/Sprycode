"""Phase 27: delete operator, 'in' index on arrays, for var i=0,j=10 comma,
   self.#x private access, encodeURIComponent/decodeURIComponent/encodeURI/decodeURI,
   String.raw tagged template, typeof Symbol."""

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


def v(interp: Interpreter, name: str = "v"):
    return interp.globals.get(name)


# ---------------------------------------------------------------------------
# Fix 2: delete obj.prop / delete obj[key]
# ---------------------------------------------------------------------------

def test_delete_member_removes_key():
    i = run("let o = {a: 1, b: 2}\ndelete o.a\nlet v = Object.keys(o)")
    assert v(i) == ["b"]


def test_delete_index_removes_key():
    i = run('let o = {a: 1, b: 2}\ndelete o["a"]\nlet v = Object.keys(o)')
    assert v(i) == ["b"]


def test_delete_nonexistent_is_ok():
    i = run("let o = {a: 1}\ndelete o.x\nlet v = Object.keys(o)")
    assert v(i) == ["a"]


def test_delete_instance_field():
    src = "class Point { fn init(x, y) { self.x = x\n self.y = y } }\nlet p = Point.new(1, 2)\ndelete p.x\nlet v = p.y"
    i = run(src)
    assert v(i) == 2


def test_delete_returns_true():
    i = run("let o = {a: 1}\nlet v = (delete o.a)")
    assert v(i) is True


def test_delete_multiple():
    i = run("let o = {a: 1, b: 2, c: 3}\ndelete o.a\ndelete o.b\nlet v = Object.keys(o)")
    assert v(i) == ["c"]


# ---------------------------------------------------------------------------
# Fix 3: 'in' operator for arrays — index-based like JS
# ---------------------------------------------------------------------------

def test_in_array_valid_index():
    i = run("let v = 0 in [10, 20, 30]")
    assert v(i) is True


def test_in_array_last_index():
    i = run("let v = 2 in [10, 20, 30]")
    assert v(i) is True


def test_in_array_out_of_bounds():
    i = run("let v = 5 in [10, 20, 30]")
    assert v(i) is False


def test_in_array_negative_index():
    i = run("let v = -1 in [10, 20, 30]")
    assert v(i) is False


def test_in_array_string_index():
    i = run('let v = "0" in [10, 20, 30]')
    assert v(i) is True


def test_in_object_present():
    i = run('let v = "a" in {a: 1, b: 2}')
    assert v(i) is True


def test_in_object_absent():
    i = run('let v = "c" in {a: 1, b: 2}')
    assert v(i) is False


def test_in_string():
    i = run('let v = "ell" in "hello"')
    assert v(i) is True


# ---------------------------------------------------------------------------
# Fix 4: for var i=0, j=10; ... — C-style for with comma declarations
# ---------------------------------------------------------------------------

def test_for_comma_two_vars():
    i = run("var v = 0\nfor var i = 0, j = 10; i < 3; i++ { v = v + j }")
    assert v(i) == 30


def test_for_comma_three_vars():
    i = run("var v = 0\nfor var a = 0, b = 5, c = 10; a < 2; a++ { v = v + b + c }")
    assert v(i) == 30  # (5+10) * 2


def test_for_comma_both_incremented():
    src = "var s = 0\nfor var i = 0, j = 0; i < 3; i++ { j = j + 1\n s = s + i + j }"
    i = run(src)
    # j increments inside loop body; s = sum of (i + j) where j is local
    # i=0,j=1 → s=1; i=1,j=2 → s=4; i=2,j=3 → s=9
    assert i.globals.get("s") == 9


def test_for_comma_vars_visible_in_body():
    i = run("var v = 0\nfor var i = 1, j = 2; i < 4; i++ { v = i * j }")
    assert v(i) == 6  # last iteration: i=3, j=2


# ---------------------------------------------------------------------------
# Fix 5: self.#x private field access in methods
# ---------------------------------------------------------------------------

def test_private_field_read():
    src = "class C { var #x = 42\n fn getX() { return self.#x } }\nlet v = C.new().getX()"
    i = run(src)
    assert v(i) == 42


def test_private_field_write():
    src = """class C {
  var #x = 0
  fn setX(val) { self.#x = val }
  fn getX() { return self.#x }
}
let c = C.new()
c.setX(99)
let v = c.getX()"""
    i = run(src)
    assert v(i) == 99


def test_private_field_increment():
    src = """class Counter {
  var #count = 0
  fn inc() { self.#count = self.#count + 1 }
  fn get() { return self.#count }
}
let c = Counter.new()
c.inc()
c.inc()
c.inc()
let v = c.get()"""
    i = run(src)
    assert v(i) == 3


def test_private_field_multiple():
    src = """class Rect {
  var #w = 0
  var #h = 0
  fn init(w, h) { self.#w = w\n self.#h = h }
  fn area() { return self.#w * self.#h }
}
let r = Rect.new(4, 5)
let v = r.area()"""
    i = run(src)
    assert v(i) == 20


# ---------------------------------------------------------------------------
# Fix 6: encodeURIComponent / decodeURIComponent / encodeURI / decodeURI
# ---------------------------------------------------------------------------

def test_encode_uri_component_space():
    i = run('let v = encodeURIComponent("hello world")')
    assert v(i) == "hello%20world"


def test_encode_uri_component_special():
    i = run('let v = encodeURIComponent("a=1&b=2")')
    assert v(i) == "a%3D1%26b%3D2"


def test_decode_uri_component_space():
    i = run('let v = decodeURIComponent("hello%20world")')
    assert v(i) == "hello world"


def test_decode_uri_component_roundtrip():
    i = run('let v = decodeURIComponent(encodeURIComponent("foo bar&baz=1"))')
    assert v(i) == "foo bar&baz=1"


def test_encode_uri_preserves_delimiters():
    i = run('let v = encodeURI("http://example.com/path?a=1&b=2")')
    assert v(i) == "http://example.com/path?a=1&b=2"


def test_encode_uri_encodes_spaces():
    i = run('let v = encodeURI("http://example.com/hello world")')
    assert v(i) == "http://example.com/hello%20world"


def test_decode_uri_basic():
    i = run('let v = decodeURI("http://example.com/hello%20world")')
    assert v(i) == "http://example.com/hello world"


def test_decode_uri_roundtrip():
    i = run('let v = decodeURI(encodeURI("http://example.com/path with spaces"))')
    assert v(i) == "http://example.com/path with spaces"


# ---------------------------------------------------------------------------
# Fix 7: String.raw tagged template
# ---------------------------------------------------------------------------

def test_string_raw_newline():
    # String.raw should preserve \\n as literal backslash-n, not newline
    src = r"""let tag = String.raw
let v = tag`hello\nworld`"""
    i = run(src)
    assert v(i) == r"hello\nworld"
    assert "\n" not in v(i)


def test_string_raw_tab():
    src = r"""let tag = String.raw
let v = tag`foo\tbar`"""
    i = run(src)
    assert v(i) == r"foo\tbar"


def test_string_raw_no_escapes_passthrough():
    src = r"""let tag = String.raw
let v = tag`hello world`"""
    i = run(src)
    assert v(i) == "hello world"


def test_string_raw_interpolation():
    src = r"""let tag = String.raw
let name = "Alice"
let v = tag`Hello ${name}\n`"""
    i = run(src)
    assert v(i) == r"Hello Alice\n"


# ---------------------------------------------------------------------------
# typeof Symbol
# ---------------------------------------------------------------------------

def test_typeof_symbol():
    i = run('let s = Symbol("foo")\nlet v = typeof s')
    assert v(i) == "Symbol"


def test_typeof_symbol_for():
    i = run('let s = Symbol.for("key")\nlet v = typeof s')
    assert v(i) == "Symbol"
