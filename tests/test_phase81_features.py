"""Tests for Phase 81: TypedArrays and ArrayBuffer."""
from __future__ import annotations
from typing import Any
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


def val(i: Interpreter, name: str = "v") -> Any:
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# ArrayBuffer
# ---------------------------------------------------------------------------

def test_arraybuffer_creates():
    i = run("var v = new ArrayBuffer(16);")
    assert val(i) is not None


def test_arraybuffer_bytelength():
    i = run("var buf = new ArrayBuffer(16); var v = buf.byteLength;")
    assert val(i) == 16


def test_arraybuffer_zero():
    i = run("var buf = new ArrayBuffer(0); var v = buf.byteLength;")
    assert val(i) == 0


def test_arraybuffer_isview_false():
    i = run("var buf = new ArrayBuffer(8); var v = ArrayBuffer.isView(buf);")
    assert val(i) == False


def test_arraybuffer_isview_typed():
    i = run("var arr = new Uint8Array(4); var v = ArrayBuffer.isView(arr);")
    assert val(i) == True


def test_arraybuffer_instanceof():
    i = run("var buf = new ArrayBuffer(4); var v = buf instanceof ArrayBuffer;")
    assert val(i) == True


# ---------------------------------------------------------------------------
# Uint8Array
# ---------------------------------------------------------------------------

def test_uint8array_from_buffer():
    i = run("var buf = new ArrayBuffer(8); var arr = new Uint8Array(buf); var v = arr.length;")
    assert val(i) == 8


def test_uint8array_from_length():
    i = run("var arr = new Uint8Array(10); var v = arr.length;")
    assert val(i) == 10


def test_uint8array_from_array():
    i = run("var arr = new Uint8Array([1,2,3]); var v = arr[1];")
    assert val(i) == 2


def test_uint8array_bytelength():
    i = run("var arr = new Uint8Array(8); var v = arr.byteLength;")
    assert val(i) == 8


def test_uint8array_default_zero():
    i = run("var arr = new Uint8Array(4); var v = arr[0];")
    assert val(i) == 0


def test_uint8array_set_element():
    i = run("var arr = new Uint8Array(4); arr[0] = 255; var v = arr[0];")
    assert val(i) == 255


def test_uint8array_set_multiple():
    i = run("var arr = new Uint8Array(3); arr[0]=1; arr[1]=2; arr[2]=3; var v = arr[1];")
    assert val(i) == 2


def test_uint8array_instanceof():
    i = run("var arr = new Uint8Array(4); var v = arr instanceof Uint8Array;")
    assert val(i) == True


def test_uint8array_typeof_object():
    i = run("var arr = new Uint8Array(4); var v = typeof arr;")
    assert val(i) == "object"


# ---------------------------------------------------------------------------
# Int32Array
# ---------------------------------------------------------------------------

def test_int32array_from_length():
    i = run("var arr = new Int32Array(4); var v = arr.length;")
    assert val(i) == 4


def test_int32array_bytelength():
    i = run("var arr = new Int32Array(4); var v = arr.byteLength;")
    assert val(i) == 16


def test_int32array_set_get():
    i = run("var arr = new Int32Array(4); arr[0] = 1000000; var v = arr[0];")
    assert val(i) == 1000000


def test_int32array_instanceof():
    i = run("var arr = new Int32Array(4); var v = arr instanceof Int32Array;")
    assert val(i) == True


def test_int32array_negative_values():
    i = run("var arr = new Int32Array(2); arr[0] = -42; var v = arr[0];")
    assert val(i) == -42


# ---------------------------------------------------------------------------
# Float64Array
# ---------------------------------------------------------------------------

def test_float64array_from_array():
    i = run("var arr = new Float64Array([1.5, 2.5]); var v = arr[0];")
    assert val(i) == 1.5


def test_float64array_bytelength():
    i = run("var arr = new Float64Array(2); var v = arr.byteLength;")
    assert val(i) == 16


def test_float64array_length():
    i = run("var arr = new Float64Array([1.5, 2.5, 3.5]); var v = arr.length;")
    assert val(i) == 3


def test_float64array_set_float():
    i = run("var arr = new Float64Array(2); arr[1] = 3.14; var v = arr[1];")
    assert val(i) == 3.14


# ---------------------------------------------------------------------------
# Various TypedArray types
# ---------------------------------------------------------------------------

def test_uint16array_creates():
    i = run("var arr = new Uint16Array(4); var v = arr.length;")
    assert val(i) == 4


def test_float32array_creates():
    i = run("var arr = new Float32Array([1.0, 2.0]); var v = arr.length;")
    assert val(i) == 2


def test_uint32array_creates():
    i = run("var arr = new Uint32Array(3); var v = arr.byteLength;")
    assert val(i) == 12


def test_int8array_creates():
    i = run("var arr = new Int8Array(4); var v = arr.length;")
    assert val(i) == 4


def test_int16array_creates():
    i = run("var arr = new Int16Array(4); var v = arr.byteLength;")
    assert val(i) == 8


# ---------------------------------------------------------------------------
# .fill()
# ---------------------------------------------------------------------------

def test_fill_all():
    i = run("var arr = new Uint8Array(4); arr.fill(7); var v = arr[2];")
    assert val(i) == 7


def test_fill_range():
    i = run("var arr = new Uint8Array(5); arr.fill(9, 1, 3); var v = arr[1];")
    assert val(i) == 9


def test_fill_range_untouched():
    i = run("var arr = new Uint8Array(5); arr.fill(9, 1, 3); var v = arr[0];")
    assert val(i) == 0


def test_fill_returns_array():
    i = run("var arr = new Uint8Array(4); var v = arr.fill(1) === arr;")
    assert val(i) == True


# ---------------------------------------------------------------------------
# .set() bulk copy
# ---------------------------------------------------------------------------

def test_set_bulk_no_offset():
    i = run("var arr = new Uint8Array(4); arr.set([1,2,3,4]); var v = arr[0];")
    assert val(i) == 1


def test_set_bulk_with_offset():
    i = run("var arr = new Uint8Array(5); arr.set([4,5,6], 1); var v = arr[2];")
    assert val(i) == 5


def test_set_bulk_offset_end():
    i = run("var arr = new Uint8Array(5); arr.set([10,20], 3); var v = arr[4];")
    assert val(i) == 20


# ---------------------------------------------------------------------------
# .slice()
# ---------------------------------------------------------------------------

def test_slice_basic():
    i = run("var arr = new Uint8Array([1,2,3,4,5]); var s = arr.slice(1,3); var v = s.length;")
    assert val(i) == 2


def test_slice_values():
    i = run("var arr = new Uint8Array([10,20,30,40]); var s = arr.slice(1,3); var v = s[0];")
    assert val(i) == 20


def test_slice_from_zero():
    i = run("var arr = new Uint8Array([1,2,3]); var s = arr.slice(0,2); var v = s[1];")
    assert val(i) == 2


def test_slice_is_new_array():
    i = run("""
var arr = new Uint8Array([1,2,3,4]);
var s = arr.slice(0,2);
s[0] = 99;
var v = arr[0];
""")
    assert val(i) == 1  # original unchanged


# ---------------------------------------------------------------------------
# .buffer
# ---------------------------------------------------------------------------

def test_buffer_property_type():
    i = run("var arr = new Uint8Array(4); var v = typeof arr.buffer;")
    assert val(i) == "object"


def test_buffer_bytelength():
    i = run("var arr = new Uint8Array(4); var v = arr.buffer.byteLength;")
    assert val(i) == 4


def test_view_from_arraybuffer():
    i = run("var buf = new ArrayBuffer(8); var arr = new Uint8Array(buf); var v = arr.byteLength;")
    assert val(i) == 8


# ---------------------------------------------------------------------------
# Array.from / spread
# ---------------------------------------------------------------------------

def test_array_from_typed():
    i = run("var arr = new Uint8Array([1,2,3]); var v = Array.from(arr);")
    assert val(i) == [1, 2, 3]


def test_spread_typed_array():
    i = run("var arr = new Uint8Array([4,5,6]); var v = [...arr];")
    assert val(i) == [4, 5, 6]


def test_array_from_int32():
    i = run("var arr = new Int32Array([10,20,30]); var v = Array.from(arr);")
    assert val(i) == [10, 20, 30]


def test_spread_float64():
    i = run("var arr = new Float64Array([1.1, 2.2]); var v = [...arr];")
    assert val(i) == [1.1, 2.2]


# ---------------------------------------------------------------------------
# BYTES_PER_ELEMENT
# ---------------------------------------------------------------------------

def test_bytes_per_element_uint8():
    i = run("var v = Uint8Array.BYTES_PER_ELEMENT;")
    assert val(i) == 1


def test_bytes_per_element_int32():
    i = run("var v = Int32Array.BYTES_PER_ELEMENT;")
    assert val(i) == 4


def test_bytes_per_element_float64():
    i = run("var v = Float64Array.BYTES_PER_ELEMENT;")
    assert val(i) == 8


def test_bytes_per_element_uint16():
    i = run("var v = Uint16Array.BYTES_PER_ELEMENT;")
    assert val(i) == 2


# ---------------------------------------------------------------------------
# Iteration
# ---------------------------------------------------------------------------

def test_for_of_typed_array():
    i = run("""
var arr = new Uint8Array([1,2,3]);
var sum = 0;
for (var x of arr) { sum += x; }
var v = sum;
""")
    assert val(i) == 6


def test_typed_array_spread_in_sum():
    i = run("""
var arr = new Uint8Array([10,20,30]);
var list = [...arr];
var v = list[0] + list[1] + list[2];
""")
    assert val(i) == 60
