"""Phase 19 feature tests.

Covers:
- DataView — read/write typed data at byte offsets in an ArrayBuffer
- Uint8ClampedArray — clamped 8-bit unsigned integer typed array
- BYTES_PER_ELEMENT on TypedArray namespaces + byteOffset / buffer on instances
- BigInt64Array / BigUint64Array typed arrays
- Error cause chaining — new Error("msg", { cause: prevErr })
- AggregateError — error with .errors list
- Atomics — synchronous atomic operations on integer TypedArrays
- SharedArrayBuffer — alias of ArrayBuffer for single-threaded use
"""

import math
import pytest
from sprycode.interpreter import Interpreter, SpryRuntimeError
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


def val(interp_or_src, name: str = "_result") -> object:
    if isinstance(interp_or_src, str):
        return run(f"let _result = {interp_or_src}").globals.get("_result")
    return interp_or_src.globals.get(name)


def eval_expr(src: str) -> object:
    return val(src)


# ===========================================================================
# DataView
# ===========================================================================

class TestDataViewBasics:
    def test_create_from_arraybuffer(self):
        i = run("let buf = ArrayBuffer.new(8)\nlet dv = DataView.new(buf)")
        dv = val(i, "dv")
        assert dv is not None

    def test_byte_length(self):
        i = run("let buf = ArrayBuffer.new(8)\nlet dv = DataView.new(buf)\nlet v = dv.byteLength")
        assert val(i, "v") == 8

    def test_byte_offset_default_zero(self):
        i = run("let buf = ArrayBuffer.new(8)\nlet dv = DataView.new(buf)\nlet v = dv.byteOffset")
        assert val(i, "v") == 0

    def test_buffer_property(self):
        i = run("let buf = ArrayBuffer.new(8)\nlet dv = DataView.new(buf)\nlet v = dv.buffer.byteLength")
        assert val(i, "v") == 8

    def test_set_and_get_uint8(self):
        i = run("""
let buf = ArrayBuffer.new(4)
let dv = DataView.new(buf)
dv.setUint8(0, 42)
let v = dv.getUint8(0)
""")
        assert val(i, "v") == 42

    def test_set_and_get_int8(self):
        i = run("""
let buf = ArrayBuffer.new(4)
let dv = DataView.new(buf)
dv.setInt8(0, -10)
let v = dv.getInt8(0)
""")
        assert val(i, "v") == -10

    def test_set_and_get_uint16(self):
        i = run("""
let buf = ArrayBuffer.new(4)
let dv = DataView.new(buf)
dv.setUint16(0, 1000)
let v = dv.getUint16(0)
""")
        assert val(i, "v") == 1000

    def test_set_and_get_int16(self):
        i = run("""
let buf = ArrayBuffer.new(4)
let dv = DataView.new(buf)
dv.setInt16(0, -500)
let v = dv.getInt16(0)
""")
        assert val(i, "v") == -500

    def test_set_and_get_int32(self):
        i = run("""
let buf = ArrayBuffer.new(8)
let dv = DataView.new(buf)
dv.setInt32(0, 123456)
let v = dv.getInt32(0)
""")
        assert val(i, "v") == 123456

    def test_set_and_get_uint32(self):
        i = run("""
let buf = ArrayBuffer.new(8)
let dv = DataView.new(buf)
dv.setUint32(0, 3000000000)
let v = dv.getUint32(0)
""")
        assert val(i, "v") == 3000000000

    def test_set_and_get_float32(self):
        i = run("""
let buf = ArrayBuffer.new(8)
let dv = DataView.new(buf)
dv.setFloat32(0, 1.5)
let v = dv.getFloat32(0)
""")
        assert abs(val(i, "v") - 1.5) < 1e-5

    def test_set_and_get_float64(self):
        i = run("""
let buf = ArrayBuffer.new(8)
let dv = DataView.new(buf)
dv.setFloat64(0, 3.141592653589793)
let v = dv.getFloat64(0)
""")
        assert abs(val(i, "v") - 3.141592653589793) < 1e-12

    def test_little_endian_uint16(self):
        i = run("""
let buf = ArrayBuffer.new(4)
let dv = DataView.new(buf)
dv.setUint16(0, 0x0102, true)
let lo = dv.getUint8(0)
let hi = dv.getUint8(1)
""")
        # little endian: low byte first
        assert val(i, "lo") == 0x02
        assert val(i, "hi") == 0x01

    def test_big_endian_uint16(self):
        i = run("""
let buf = ArrayBuffer.new(4)
let dv = DataView.new(buf)
dv.setUint16(0, 0x0102, false)
let lo = dv.getUint8(0)
let hi = dv.getUint8(1)
""")
        # big endian (default): high byte first
        assert val(i, "lo") == 0x01
        assert val(i, "hi") == 0x02

    def test_multiple_values_at_offsets(self):
        i = run("""
let buf = ArrayBuffer.new(8)
let dv = DataView.new(buf)
dv.setInt32(0, 100)
dv.setInt32(4, 200)
let a = dv.getInt32(0)
let b = dv.getInt32(4)
""")
        assert val(i, "a") == 100
        assert val(i, "b") == 200

    def test_dataview_callable_without_new(self):
        i = run("""
let buf = ArrayBuffer.new(4)
let dv = DataView(buf)
dv.setUint8(0, 99)
let v = dv.getUint8(0)
""")
        assert val(i, "v") == 99


# ===========================================================================
# Uint8ClampedArray
# ===========================================================================

class TestUint8ClampedArray:
    def test_create_with_length(self):
        i = run("let arr = Uint8ClampedArray.new(4)\nlet v = arr.length")
        assert val(i, "v") == 4

    def test_default_values_zero(self):
        i = run("let arr = Uint8ClampedArray.new(3)\nlet v = arr.get(0)")
        assert val(i, "v") == 0

    def test_set_and_get_normal(self):
        i = run("let arr = Uint8ClampedArray.new(4)\narr.set(0, 128)\nlet v = arr.get(0)")
        assert val(i, "v") == 128

    def test_clamp_below_zero(self):
        i = run("let arr = Uint8ClampedArray.new(4)\narr.set(0, -5)\nlet v = arr.get(0)")
        assert val(i, "v") == 0

    def test_clamp_above_255(self):
        i = run("let arr = Uint8ClampedArray.new(4)\narr.set(0, 300)\nlet v = arr.get(0)")
        assert val(i, "v") == 255

    def test_clamp_exactly_255(self):
        i = run("let arr = Uint8ClampedArray.new(4)\narr.set(0, 255)\nlet v = arr.get(0)")
        assert val(i, "v") == 255

    def test_clamp_exactly_zero(self):
        i = run("let arr = Uint8ClampedArray.new(4)\narr.set(0, 0)\nlet v = arr.get(0)")
        assert val(i, "v") == 0

    def test_create_from_list(self):
        i = run("let arr = Uint8ClampedArray.new([10, 300, -5, 128])\nlet v = arr.toList()")
        assert val(i, "v") == [10, 255, 0, 128]

    def test_bytes_per_element(self):
        i = run("let v = Uint8ClampedArray.BYTES_PER_ELEMENT")
        assert val(i, "v") == 1

    def test_byte_length(self):
        i = run("let arr = Uint8ClampedArray.new(8)\nlet v = arr.byteLength")
        assert val(i, "v") == 8

    def test_fill_clamped(self):
        i = run("let arr = Uint8ClampedArray.new(3)\narr.fill(300)\nlet v = arr.toList()")
        assert val(i, "v") == [255, 255, 255]

    def test_from_method(self):
        arr_ns = run("let arr = Uint8ClampedArray.from([0, 128, 300, -1])\nlet v = arr.toList()").globals.get("v")
        assert arr_ns == [0, 128, 255, 0]


# ===========================================================================
# TypedArray extensions — BYTES_PER_ELEMENT, byteOffset, buffer
# ===========================================================================

class TestTypedArrayExtensions:
    def test_int8array_bytes_per_element(self):
        i = run("let v = Int8Array.BYTES_PER_ELEMENT")
        assert val(i, "v") == 1

    def test_uint8array_bytes_per_element(self):
        i = run("let v = Uint8Array.BYTES_PER_ELEMENT")
        assert val(i, "v") == 1

    def test_int16array_bytes_per_element(self):
        i = run("let v = Int16Array.BYTES_PER_ELEMENT")
        assert val(i, "v") == 2

    def test_uint16array_bytes_per_element(self):
        i = run("let v = Uint16Array.BYTES_PER_ELEMENT")
        assert val(i, "v") == 2

    def test_int32array_bytes_per_element(self):
        i = run("let v = Int32Array.BYTES_PER_ELEMENT")
        assert val(i, "v") == 4

    def test_uint32array_bytes_per_element(self):
        i = run("let v = Uint32Array.BYTES_PER_ELEMENT")
        assert val(i, "v") == 4

    def test_float32array_bytes_per_element(self):
        i = run("let v = Float32Array.BYTES_PER_ELEMENT")
        assert val(i, "v") == 4

    def test_float64array_bytes_per_element(self):
        i = run("let v = Float64Array.BYTES_PER_ELEMENT")
        assert val(i, "v") == 8

    def test_instance_byte_offset_default(self):
        i = run("let arr = Int32Array.new(4)\nlet v = arr.byteOffset")
        assert val(i, "v") == 0

    def test_instance_buffer_returns_buffer(self):
        i = run("let arr = Int32Array.new(4)\nlet v = arr.buffer.byteLength")
        assert val(i, "v") == 16

    def test_subarray_byte_offset(self):
        i = run("""
let arr = Int32Array.new([1, 2, 3, 4])
let sub = arr.subarray(1, 3)
let v = sub.byteOffset
""")
        assert val(i, "v") == 4  # 1 element * 4 bytes/elem

    def test_instance_bytes_per_element(self):
        i = run("let arr = Float64Array.new(2)\nlet v = arr.BYTES_PER_ELEMENT")
        assert val(i, "v") == 8

    def test_bigint64array_exists(self):
        i = run("let arr = BigInt64Array.new(2)\nlet v = arr.BYTES_PER_ELEMENT")
        assert val(i, "v") == 8

    def test_biguint64array_exists(self):
        i = run("let arr = BigUint64Array.new(3)\nlet v = arr.length")
        assert val(i, "v") == 3

    def test_arraybuffer_isview_typed_array(self):
        i = run("let arr = Uint8Array.new(4)\nlet v = ArrayBuffer.isView(arr)")
        assert val(i, "v") is True

    def test_arraybuffer_isview_dataview(self):
        i = run("""
let buf = ArrayBuffer.new(8)
let dv = DataView.new(buf)
let v = ArrayBuffer.isView(dv)
""")
        assert val(i, "v") is True

    def test_arraybuffer_isview_plain_buffer(self):
        i = run("let buf = ArrayBuffer.new(8)\nlet v = ArrayBuffer.isView(buf)")
        assert val(i, "v") is False


# ===========================================================================
# SharedArrayBuffer
# ===========================================================================

class TestSharedArrayBuffer:
    def test_create(self):
        i = run("let sab = SharedArrayBuffer.new(16)\nlet v = sab.byteLength")
        assert val(i, "v") == 16

    def test_create_callable(self):
        i = run("let sab = SharedArrayBuffer(8)\nlet v = sab.byteLength")
        assert val(i, "v") == 8

    def test_use_with_typed_array(self):
        i = run("""
let sab = SharedArrayBuffer.new(16)
let arr = Int32Array.new(sab)
arr.set(0, 42)
let v = arr.get(0)
""")
        assert val(i, "v") == 42

    def test_use_with_dataview(self):
        i = run("""
let sab = SharedArrayBuffer.new(8)
let dv = DataView.new(sab)
dv.setInt32(0, 999)
let v = dv.getInt32(0)
""")
        assert val(i, "v") == 999

    def test_repr(self):
        from sprycode.interpreter import SprySharedArrayBuffer
        sab = SprySharedArrayBuffer(4)
        assert "4" in repr(sab)


# ===========================================================================
# Error cause chaining
# ===========================================================================

class TestErrorCause:
    def test_error_with_cause(self):
        i = run("""
let inner = Error.new("inner problem")
let outer = Error.new("outer problem", { cause: inner })
let v = outer.cause.message
""")
        assert val(i, "v") == "inner problem"

    def test_error_cause_is_null_when_not_set(self):
        i = run("""
let err = Error.new("oops")
let v = err.cause
""")
        assert val(i, "v") is None

    def test_typeerror_with_cause(self):
        i = run("""
let inner = Error.new("root cause")
let outer = TypeError.new("type mismatch", { cause: inner })
let v = outer.cause.message
""")
        assert val(i, "v") == "root cause"

    def test_rangeerror_with_cause(self):
        i = run("""
let root = Error.new("root")
let err = RangeError.new("out of range", { cause: root })
let v = err.cause.name
""")
        assert val(i, "v") == "Error"

    def test_cause_is_arbitrary_value(self):
        i = run("""
let err = Error.new("failed", { cause: 42 })
let v = err.cause
""")
        assert val(i, "v") == 42

    def test_error_callable_with_cause(self):
        i = run("""
let inner = Error("inner")
let outer = Error("outer", { cause: inner })
let v = outer.cause.message
""")
        assert val(i, "v") == "inner"

    def test_error_message_unchanged_with_cause(self):
        i = run("""
let inner = Error.new("cause msg")
let outer = Error.new("main msg", { cause: inner })
let v = outer.message
""")
        assert val(i, "v") == "main msg"

    def test_error_name_unchanged(self):
        i = run("""
let err = TypeError.new("bad type", { cause: Error.new("root") })
let v = err.name
""")
        assert val(i, "v") == "TypeError"

    def test_error_cause_chaining(self):
        i = run("""
let e1 = Error.new("level 1")
let e2 = Error.new("level 2", { cause: e1 })
let e3 = Error.new("level 3", { cause: e2 })
let v = e3.cause.cause.message
""")
        assert val(i, "v") == "level 1"

    def test_error_no_options_arg(self):
        i = run("""
let err = Error.new("simple")
let v = err.message
""")
        assert val(i, "v") == "simple"


# ===========================================================================
# AggregateError
# ===========================================================================

class TestAggregateError:
    def test_create(self):
        i = run("""
let err = AggregateError.new([Error.new("a"), Error.new("b")], "multiple errors")
let v = err.message
""")
        assert val(i, "v") == "multiple errors"

    def test_errors_list(self):
        i = run("""
let err = AggregateError.new([Error.new("first"), Error.new("second")], "two errors")
let v = len(err.errors)
""")
        assert val(i, "v") == 2

    def test_errors_messages(self):
        i = run("""
let e1 = Error.new("one")
let e2 = Error.new("two")
let agg = AggregateError.new([e1, e2], "collected")
let v = agg.errors[0].message
""")
        assert val(i, "v") == "one"

    def test_name_is_aggregate_error(self):
        i = run("""
let agg = AggregateError.new([], "empty")
let v = agg.name
""")
        assert val(i, "v") == "AggregateError"

    def test_empty_errors(self):
        i = run("""
let agg = AggregateError.new([], "no errors")
let v = len(agg.errors)
""")
        assert val(i, "v") == 0

    def test_callable(self):
        i = run("""
let agg = AggregateError([Error.new("a")], "one error")
let v = len(agg.errors)
""")
        assert val(i, "v") == 1

    def test_aggregate_error_with_cause(self):
        i = run("""
let root = Error.new("root")
let agg = AggregateError.new([root], "wrapped", { cause: root })
let v = agg.cause.message
""")
        assert val(i, "v") == "root"

    def test_aggregate_error_in_catch(self):
        i = run("""
var caught = ""
try {
    throw AggregateError.new([Error.new("x")], "agg")
} catch e {
    caught = e.name
}
let v = caught
""")
        assert val(i, "v") == "AggregateError"

    def test_second_error_message(self):
        i = run("""
let agg = AggregateError.new([Error.new("first"), Error.new("second"), Error.new("third")], "many")
let v = agg.errors[2].message
""")
        assert val(i, "v") == "third"


# ===========================================================================
# Atomics
# ===========================================================================

class TestAtomics:
    def test_atomics_load(self):
        i = run("""
let arr = Int32Array.new([10, 20, 30])
let v = Atomics.load(arr, 1)
""")
        assert val(i, "v") == 20

    def test_atomics_store(self):
        i = run("""
let arr = Int32Array.new(3)
Atomics.store(arr, 0, 99)
let v = arr.get(0)
""")
        assert val(i, "v") == 99

    def test_atomics_add(self):
        i = run("""
let arr = Int32Array.new([5, 0, 0])
let old = Atomics.add(arr, 0, 3)
let newv = arr.get(0)
""")
        assert val(i, "old") == 5
        assert val(i, "newv") == 8

    def test_atomics_sub(self):
        i = run("""
let arr = Int32Array.new([10, 0, 0])
let old = Atomics.sub(arr, 0, 4)
let newv = arr.get(0)
""")
        assert val(i, "old") == 10
        assert val(i, "newv") == 6

    def test_atomics_and(self):
        i = run("""
let arr = Int32Array.new([0b1111, 0, 0])
let old = Atomics.and(arr, 0, 0b1010)
let newv = arr.get(0)
""")
        assert val(i, "old") == 0b1111
        assert val(i, "newv") == 0b1010

    def test_atomics_or(self):
        i = run("""
let arr = Int32Array.new([0b0101, 0, 0])
let old = Atomics.or(arr, 0, 0b1010)
let newv = arr.get(0)
""")
        assert val(i, "old") == 0b0101
        assert val(i, "newv") == 0b1111

    def test_atomics_xor(self):
        i = run("""
let arr = Int32Array.new([0b1100, 0, 0])
let old = Atomics.xor(arr, 0, 0b1010)
let newv = arr.get(0)
""")
        assert val(i, "old") == 0b1100
        assert val(i, "newv") == 0b0110

    def test_atomics_exchange(self):
        i = run("""
let arr = Int32Array.new([42, 0, 0])
let old = Atomics.exchange(arr, 0, 100)
let newv = arr.get(0)
""")
        assert val(i, "old") == 42
        assert val(i, "newv") == 100

    def test_atomics_compare_exchange_match(self):
        i = run("""
let arr = Int32Array.new([5, 0, 0])
let old = Atomics.compareExchange(arr, 0, 5, 99)
let newv = arr.get(0)
""")
        assert val(i, "old") == 5
        assert val(i, "newv") == 99

    def test_atomics_compare_exchange_no_match(self):
        i = run("""
let arr = Int32Array.new([5, 0, 0])
let old = Atomics.compareExchange(arr, 0, 10, 99)
let newv = arr.get(0)
""")
        assert val(i, "old") == 5
        assert val(i, "newv") == 5  # not changed

    def test_atomics_is_lock_free(self):
        i = run("let v = Atomics.isLockFree(4)")
        assert val(i, "v") is True

    def test_atomics_is_lock_free_3(self):
        i = run("let v = Atomics.isLockFree(3)")
        assert val(i, "v") is False

    def test_atomics_wait_ok(self):
        i = run("""
let arr = Int32Array.new([0])
let v = Atomics.wait(arr, 0, 0)
""")
        assert val(i, "v") == "ok"

    def test_atomics_wait_not_equal(self):
        i = run("""
let arr = Int32Array.new([5])
let v = Atomics.wait(arr, 0, 0)
""")
        assert val(i, "v") == "not-equal"

    def test_atomics_notify(self):
        i = run("""
let arr = Int32Array.new([0])
let v = Atomics.notify(arr, 0, 1)
""")
        assert val(i, "v") == 0
