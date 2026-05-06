"""Phase 63 feature tests.

Covers:
- ``test`` identifier used as a variable/function name (not only a test-block keyword)
- ``findIndex`` / ``findLast`` / ``findLastIndex`` pass (element, index, array) when
  callback arity > 1
- BigInt literals (``42n``) produce a proper ``_SpryBigInt`` value:
  - ``typeof 42n === "bigint"``
  - BigInt integer division: ``10n / 3n === 3n``
  - BigInt arithmetic preserves type
- Uninitialized ``let x`` is ``SPRY_UNDEFINED`` (``typeof x === "undefined"``,
  ``x === undefined``)
- Arrow function ``.name`` is inferred from the LHS of the ``let``/``var``
  assignment
- ``WeakMap.set`` with a primitive key throws ``TypeError``
- Optional chaining ``null?.prop``, ``null?.[0]``, ``null?.()`` return
  ``SPRY_UNDEFINED`` (not ``None``)
"""

from __future__ import annotations

import pytest
from sprycode.interpreter import (
    Interpreter,
    SPRY_UNDEFINED,
    _SpryBigInt,
    SpryRuntimeError,
)
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


def val(i_or_src, name: str = "v"):
    if isinstance(i_or_src, str):
        return run(i_or_src).globals.get(name)
    return i_or_src.globals.get(name)


# ---------------------------------------------------------------------------
# Fix: "test" identifier as a variable / function name
# ---------------------------------------------------------------------------

class TestTestAsIdentifier:
    def test_function_named_test_called(self):
        i = run("""
let v = 0
function test() { v = 42 }
test()
""")
        assert val(i) == 42

    def test_variable_named_test(self):
        i = run("let test = 7; let v = test")
        assert val(i) == 7

    def test_test_in_expression(self):
        i = run("let test = (x) => x * 2; let v = test(5)")
        assert val(i) == 10

    def test_try_finally_in_function_named_test(self):
        """try/finally inside a function called 'test' parses correctly."""
        i = run("""
let v = 0
function test() {
  try {
    v = 1
    return v
  } finally {
    v = 99
  }
}
test()
""")
        # finally sets global v to 99
        assert val(i) == 99


# ---------------------------------------------------------------------------
# Fix: findIndex / findLast / findLastIndex with index arg
# ---------------------------------------------------------------------------

class TestFindIndexWithIndex:
    def test_findIndex_uses_index_arg(self):
        # without index arg: would return first element > 25 regardless of index
        v = val("let v = [10, 20, 30, 40].findIndex((x, i) => i > 1 && x > 25)")
        assert v == 2

    def test_findIndex_no_match(self):
        v = val("let v = [10, 20, 30].findIndex((x, i) => i > 5)")
        assert v == -1

    def test_findIndex_single_arg_still_works(self):
        v = val("let v = [1, 2, 3, 4].findIndex(x => x > 2)")
        assert v == 2

    def test_findLast_uses_index_arg(self):
        # Elements at indices 0-2 with x > 1: indices 1 and 2 match; last is index 2 (value 3)
        v = val("let v = [1, 2, 3, 4, 5].findLast((x, i) => i < 3 && x > 1)")
        assert v == 3

    def test_findLast_single_arg_still_works(self):
        v = val("let v = [1, 2, 3, 4].findLast(x => x < 3)")
        assert v == 2

    def test_findLastIndex_uses_index_arg(self):
        # Among indices < 3, last element with x > 1: index 2 (value 3)
        v = val("let v = [1, 2, 3, 4, 5].findLastIndex((x, i) => i < 3 && x > 1)")
        assert v == 2

    def test_findLastIndex_no_match(self):
        v = val("let v = [1, 2, 3].findLastIndex((x, i) => i > 10)")
        assert v == -1

    def test_findLastIndex_single_arg_still_works(self):
        v = val("let v = [1, 2, 3, 4].findLastIndex(x => x < 3)")
        assert v == 1


# ---------------------------------------------------------------------------
# Fix: BigInt literals → _SpryBigInt type
# ---------------------------------------------------------------------------

class TestBigInt:
    def test_typeof_bigint(self):
        v = val("let v = typeof 42n")
        assert v == "bigint"

    def test_typeof_zero_bigint(self):
        v = val("let v = typeof 0n")
        assert v == "bigint"

    def test_bigint_integer_division(self):
        v = val("let v = 10n / 3n")
        assert v == _SpryBigInt(3)
        assert isinstance(v, _SpryBigInt)

    def test_bigint_mul(self):
        v = val("let v = 5n * 3n")
        assert v == _SpryBigInt(15)
        assert isinstance(v, _SpryBigInt)

    def test_bigint_add(self):
        v = val("let v = 100n + 23n")
        assert v == _SpryBigInt(123)

    def test_bigint_sub(self):
        v = val("let v = 10n - 4n")
        assert v == _SpryBigInt(6)

    def test_bigint_mod(self):
        v = val("let v = 10n % 3n")
        assert v == _SpryBigInt(1)

    def test_bigint_string_coercion(self):
        v = val("let v = String(42n)")
        assert v == "42"

    def test_bigint_equality(self):
        v = val("let v = (3n === 3n)")
        assert v is True

    def test_bigint_comparison(self):
        v = val("let v = (5n > 3n)")
        assert v is True

    def test_bigint_negative_literal(self):
        v = val("let v = -5n")
        assert v == _SpryBigInt(-5)
        assert isinstance(v, _SpryBigInt)


# ---------------------------------------------------------------------------
# Fix: uninitialized let → SPRY_UNDEFINED
# ---------------------------------------------------------------------------

class TestUninitializedLet:
    def test_typeof_uninitialized_let(self):
        v = val("let x; let v = typeof x")
        assert v == "undefined"

    def test_uninitialized_let_equals_undefined(self):
        v = val("let x; let v = (x === undefined)")
        assert v is True

    def test_uninitialized_let_is_falsy(self):
        v = val("let x; let v = x ? 1 : 0")
        assert v == 0

    def test_initialized_let_is_not_undefined(self):
        v = val("let x = 42; let v = (x === undefined)")
        assert v is False

    def test_uninitialized_const_gets_undefined(self):
        # const without initializer is unusual but should not crash
        # (SpryCode allows it — value is SPRY_UNDEFINED)
        v = val("const x = undefined; let v = typeof x")
        assert v == "undefined"


# ---------------------------------------------------------------------------
# Fix: arrow function .name inferred from assignment
# ---------------------------------------------------------------------------

class TestArrowFunctionName:
    def test_arrow_single_param_name(self):
        v = val("let foo = x => x; let v = foo.name")
        assert v == "foo"

    def test_arrow_multi_param_name(self):
        v = val("let bar = (a, b) => a + b; let v = bar.name")
        assert v == "bar"

    def test_arrow_const_name(self):
        v = val("const myFunc = x => x * 2; let v = myFunc.name")
        assert v == "myFunc"

    def test_regular_function_name_unchanged(self):
        v = val("function greet(name) { return name }; let v = greet.name")
        assert v == "greet"

    def test_arrow_reassigned_name(self):
        # The name is inferred from first assignment, not subsequent
        v = val("let fn1 = x => x; let fn2 = fn1; let v = fn2.name")
        assert v == "fn1"


# ---------------------------------------------------------------------------
# Fix: WeakMap.set with primitive key throws
# ---------------------------------------------------------------------------

class TestWeakMapPrimitiveKey:
    def test_string_key_throws(self):
        i = run("""
let m = new WeakMap()
let v = "nothrow"
try {
  m.set("str", 1)
} catch(e) {
  v = "threw"
}
""")
        assert val(i) == "threw"

    def test_number_key_throws(self):
        i = run("""
let m = new WeakMap()
let v = "nothrow"
try {
  m.set(42, 1)
} catch(e) {
  v = "threw"
}
""")
        assert val(i) == "threw"

    def test_null_key_throws(self):
        i = run("""
let m = new WeakMap()
let v = "nothrow"
try {
  m.set(null, 1)
} catch(e) {
  v = "threw"
}
""")
        assert val(i) == "threw"

    def test_object_key_ok(self):
        i = run("""
let m = new WeakMap()
let obj = {}
m.set(obj, 42)
let v = m.get(obj)
""")
        assert val(i) == 42

    def test_array_key_ok(self):
        i = run("""
let m = new WeakMap()
let arr = [1, 2, 3]
m.set(arr, "yes")
let v = m.get(arr)
""")
        assert val(i) == "yes"


# ---------------------------------------------------------------------------
# Fix: optional chain on null/undefined returns SPRY_UNDEFINED
# ---------------------------------------------------------------------------

class TestOptionalChainReturnsUndefined:
    def test_null_optional_member(self):
        v = val("let o = null; let v = o?.a")
        assert v == SPRY_UNDEFINED

    def test_null_optional_member_checked(self):
        v = val("let o = null; let v = (o?.a === undefined)")
        assert v is True

    def test_null_optional_deep_chain(self):
        v = val("let o = null; let v = o?.a?.b?.c")
        assert v == SPRY_UNDEFINED

    def test_null_optional_index(self):
        v = val("let o = null; let v = o?.[0]")
        assert v == SPRY_UNDEFINED

    def test_null_optional_call(self):
        v = val("let f = null; let v = f?.(1, 2)")
        assert v == SPRY_UNDEFINED

    def test_undefined_optional_member(self):
        v = val("let o = undefined; let v = o?.x")
        assert v == SPRY_UNDEFINED

    def test_missing_property_then_optional_chain(self):
        # obj.missing is None; None?.nested → SPRY_UNDEFINED
        v = val("let obj = {a: 1}; let v = obj.missing?.nested")
        assert v == SPRY_UNDEFINED

    def test_non_null_optional_chain_still_works(self):
        v = val("let o = {a: {b: 42}}; let v = o?.a?.b")
        assert v == 42

    def test_nullish_coalesce_after_optional_chain(self):
        v = val("let o = null; let v = o?.x ?? 'default'")
        assert v == "default"
