"""Phase 17 feature tests.

Covers:
- Infinity / NaN globals and JS-like division semantics
- Generator send protocol (yield as expression, next(value))
- _ (underscore) as valid lambda parameter
- map/filter/forEach with (value, index) callbacks
- String.raw tagged template
- Tagged templates (general)
- Object.assign mutates in-place
- with {obj} { body } scoped bindings
- BigInt literals (42n)
- for {x, y} of list (object destructuring in for-of)
- Class fn get / fn set (getters and setters)
- Number.isFinite / Number.isNaN
- List.forEach method
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


def val(interp: Interpreter, name: str) -> object:
    return interp.globals.get(name)


def eval_expr(src: str) -> object:
    """Evaluate a single expression and return the result."""
    return run(f"let _result = {src}").globals.get("_result")


# ===========================================================================
# Infinity and NaN globals
# ===========================================================================


class TestInfinityNaN:
    def test_infinity_global(self):
        assert math.isinf(eval_expr("Infinity")) and eval_expr("Infinity") > 0

    def test_negative_infinity(self):
        assert math.isinf(eval_expr("-Infinity")) and eval_expr("-Infinity") < 0

    def test_nan_global(self):
        assert math.isnan(eval_expr("NaN"))

    def test_division_by_zero_positive(self):
        result = eval_expr("1 / 0")
        assert math.isinf(result) and result > 0

    def test_division_by_zero_negative(self):
        result = eval_expr("-1 / 0")
        assert math.isinf(result) and result < 0

    def test_zero_divided_by_zero(self):
        assert math.isnan(eval_expr("0 / 0"))

    def test_modulo_by_zero(self):
        assert math.isnan(eval_expr("5 % 0"))

    def test_infinity_plus_one(self):
        result = eval_expr("Infinity + 1")
        assert math.isinf(result) and result > 0

    def test_infinity_times_negative(self):
        result = eval_expr("Infinity * -1")
        assert math.isinf(result) and result < 0

    def test_isnan_global(self):
        assert eval_expr("isNaN(NaN)") is True
        assert eval_expr("isNaN(0/0)") is True
        assert eval_expr("isNaN(1)") is False

    def test_isfinite_global(self):
        assert eval_expr("isFinite(1)") is True
        assert eval_expr("isFinite(Infinity)") is False
        assert eval_expr("isFinite(NaN)") is False

    def test_number_isnan(self):
        assert eval_expr("Number.isNaN(NaN)") is True
        assert eval_expr("Number.isNaN(0/0)") is True
        assert eval_expr("Number.isNaN(1)") is False

    def test_number_isfinite(self):
        assert eval_expr("Number.isFinite(1)") is True
        assert eval_expr("Number.isFinite(Infinity)") is False
        assert eval_expr("Number.isFinite(NaN)") is False

    def test_infinity_in_try_does_not_throw(self):
        # 1/0 → Infinity (no exception raised)
        i = run("var v = false\ntry {\n  let x = 1 / 0\n} catch err {\n  v = true\n}")
        assert val(i, "v") is False

    def test_nan_comparison(self):
        # NaN is never equal to anything including itself
        assert eval_expr("NaN == NaN") is False
        assert eval_expr("NaN != NaN") is True


# ===========================================================================
# Number namespace extras
# ===========================================================================


class TestNumberNamespace:
    def test_epsilon(self):
        result = eval_expr("Number.EPSILON")
        assert 0 < result < 1e-10

    def test_max_safe_integer(self):
        assert eval_expr("Number.MAX_SAFE_INTEGER") == 2 ** 53 - 1

    def test_min_safe_integer(self):
        assert eval_expr("Number.MIN_SAFE_INTEGER") == -(2 ** 53 - 1)

    def test_positive_infinity_const(self):
        result = eval_expr("Number.POSITIVE_INFINITY")
        assert math.isinf(result) and result > 0

    def test_negative_infinity_const(self):
        result = eval_expr("Number.NEGATIVE_INFINITY")
        assert math.isinf(result) and result < 0

    def test_number_nan_const(self):
        assert math.isnan(eval_expr("Number.NaN"))

    def test_is_integer(self):
        assert eval_expr("Number.isInteger(42)") is True
        assert eval_expr("Number.isInteger(42.5)") is False

    def test_parse_int(self):
        assert eval_expr("Number.parseInt(\"42\")") == 42

    def test_parse_float(self):
        assert eval_expr("Number.parseFloat(\"3.14\")") == pytest.approx(3.14)

    def test_to_fixed(self):
        assert eval_expr("(3.14159).toFixed(2)") == "3.14"


# ===========================================================================
# Generator send protocol — yield as expression
# ===========================================================================


class TestGeneratorSend:
    def test_basic_send(self):
        src = """
fn* gen() {
  let r = yield 1
  yield r + 10
}
let g = gen()
g.next()
let res = g.next(5)
let v = res.value
"""
        i = run(src)
        assert val(i, "v") == 15

    def test_send_zero(self):
        src = """
fn* gen() {
  let r = yield 100
  yield r * 2
}
let g = gen()
g.next()
let res = g.next(0)
let v = res.value
"""
        i = run(src)
        assert val(i, "v") == 0

    def test_send_string(self):
        src = """
fn* gen() {
  let r = yield "start"
  yield r + " world"
}
let g = gen()
g.next()
let res = g.next("hello")
let v = res.value
"""
        i = run(src)
        assert val(i, "v") == "hello world"

    def test_first_next_returns_first_yield(self):
        src = """
fn* gen() {
  let r = yield 42
  yield r
}
let g = gen()
let res = g.next()
let v = res.value
"""
        i = run(src)
        assert val(i, "v") == 42

    def test_send_multiple_yields(self):
        src = """
fn* gen() {
  let a = yield 1
  let b = yield a + 1
  yield a + b
}
let g = gen()
g.next()
g.next(10)
let res = g.next(5)
let v = res.value
"""
        i = run(src)
        assert val(i, "v") == 15  # a=10, b=5, a+b=15

    def test_generator_yield_as_stmt_still_works(self):
        # Simple yield-as-statement generators (no send) still work correctly
        src = "fn* gen() { yield 1\nyield 2\nyield 3 }\nlet v = [x for x in gen()]"
        i = run(src)
        assert val(i, "v") == [1, 2, 3]

    def test_done_after_exhaustion(self):
        src = """
fn* gen() { yield 1 }
let g = gen()
g.next()
let r = g.next()
let v = r.done
"""
        i = run(src)
        assert val(i, "v") is True


# ===========================================================================
# _ (underscore) as lambda parameter
# ===========================================================================


class TestUnderscoreParam:
    def test_underscore_in_map_index(self):
        i = run("let v = [10,20,30].map((_, i) => i)")
        assert val(i, "v") == [0, 1, 2]

    def test_underscore_ignored_value(self):
        i = run("let v = [\"a\",\"b\",\"c\"].map((_, i) => i * 2)")
        assert val(i, "v") == [0, 2, 4]

    def test_underscore_single_param(self):
        i = run("let v = [1,2,3].map(_ => 99)")
        assert val(i, "v") == [99, 99, 99]

    def test_underscore_in_filter(self):
        i = run("let v = [10,20,30,40].filter((_, i) => i % 2 == 0)")
        assert val(i, "v") == [10, 30]

    def test_underscore_in_reduce(self):
        i = run("let v = [1,2,3,4].reduce((acc, _) => acc + 1, 0)")
        assert val(i, "v") == 4


# ===========================================================================
# map/filter/forEach with (value, index) callbacks
# ===========================================================================


class TestMapFilterIndex:
    def test_map_with_index(self):
        i = run("let v = [10,20,30].map((x, i) => x + i)")
        assert val(i, "v") == [10, 21, 32]

    def test_map_value_only(self):
        i = run("let v = [1,2,3].map(x => x * 2)")
        assert val(i, "v") == [2, 4, 6]

    def test_map_fn_value_only(self):
        i = run("let v = [1,2,3].map(fn(x) => x * 3)")
        assert val(i, "v") == [3, 6, 9]

    def test_filter_with_index(self):
        i = run("let v = [1,2,3,4,5].filter((_, i) => i < 3)")
        assert val(i, "v") == [1, 2, 3]

    def test_filter_value_only(self):
        i = run("let v = [1,2,3,4,5].filter(x => x > 2)")
        assert val(i, "v") == [3, 4, 5]

    def test_foreach_with_index(self):
        src = "var v = 0\nlet arr = [10,20,30]\narr.forEach((x, i) => { v = v + i })"
        i = run(src)
        assert val(i, "v") == 3  # 0+1+2

    def test_foreach_value_only(self):
        src = "var v = 0\nlet arr = [1,2,3]\narr.forEach(x => { v = v + x })"
        i = run(src)
        assert val(i, "v") == 6

    def test_map_returns_new_list(self):
        i = run("let a = [1,2,3]\nlet v = a.map(x => x + 1)")
        assert val(i, "v") == [2, 3, 4]

    def test_map_preserves_original(self):
        i = run("let a = [1,2,3]\nlet b = a.map(x => x * 10)\nlet v = a")
        assert val(i, "v") == [1, 2, 3]


# ===========================================================================
# String.raw tagged template
# ===========================================================================


class TestStringRaw:
    def test_string_raw_no_interpolation(self):
        i = run("let v = String.raw`hello world`")
        assert val(i, "v") == "hello world"

    def test_string_raw_with_interpolation(self):
        src = "let n = 42\nlet v = String.raw`value is ${n}`"
        i = run(src)
        assert val(i, "v") == "value is 42"

    def test_string_raw_multiple_interpolations(self):
        src = "let a = 1\nlet b = 2\nlet v = String.raw`${a} + ${b}`"
        i = run(src)
        assert val(i, "v") == "1 + 2"


# ===========================================================================
# Tagged templates (general)
# ===========================================================================


class TestTaggedTemplates:
    def test_custom_tag_function(self):
        src = "fn tag(parts, a) { return parts[0] + str(a) + parts[1] }\nlet v = tag`x=${99}y`"
        i = run(src)
        assert val(i, "v") == "x=99y"

    def test_tag_multiple_interpolations(self):
        src = """
fn tag(parts, a, b) {
  return parts[0] + str(a) + parts[1] + str(b) + parts[2]
}
let v = tag`hello ${1} and ${2} world`
"""
        i = run(src)
        assert val(i, "v") == "hello 1 and 2 world"

    def test_tag_receives_string_parts_list(self):
        src = """
fn tag(parts, a, b) { return parts.length }
let v = tag`a${1}b${2}c`
"""
        i = run(src)
        assert val(i, "v") == 3  # ["a", "b", "c"]


# ===========================================================================
# Object.assign
# ===========================================================================


class TestObjectAssign:
    def test_assign_adds_keys(self):
        i = run("let a = {x: 1}\nObject.assign(a, {y: 2})\nlet v = a.y")
        assert val(i, "v") == 2

    def test_assign_multiple_sources(self):
        i = run("let a = {x: 1}\nObject.assign(a, {y: 2}, {z: 3})\nlet v = a.z")
        assert val(i, "v") == 3

    def test_assign_overwrites_keys(self):
        i = run("let a = {x: 1}\nObject.assign(a, {x: 99})\nlet v = a.x")
        assert val(i, "v") == 99

    def test_assign_returns_target(self):
        i = run("let a = {x: 1}\nlet b = Object.assign(a, {y: 2})\nlet v = b.x + b.y")
        assert val(i, "v") == 3

    def test_assign_mutates_in_place(self):
        i = run("let a = {x: 1}\nObject.assign(a, {y: 2})\nlet v = a.y")
        assert val(i, "v") == 2


# ===========================================================================
# with {obj} { body } scoped bindings
# ===========================================================================


class TestWith:
    def test_with_simple(self):
        i = run("let v = with {x: 1, y: 2} { x + y }")
        assert val(i, "v") == 3

    def test_with_nested_access(self):
        i = run("let v = with {a: 10} { a * a }")
        assert val(i, "v") == 100

    def test_with_multiple_keys(self):
        i = run("let v = with {a: 1, b: 2, c: 3} { a + b + c }")
        assert val(i, "v") == 6

    def test_with_expression_values(self):
        i = run("let n = 5\nlet v = with {x: n * 2} { x + 1 }")
        assert val(i, "v") == 11

    def test_with_outer_scope_visible(self):
        i = run("let outer = 100\nlet v = with {x: 1} { x + outer }")
        assert val(i, "v") == 101


# ===========================================================================
# BigInt literals (42n)
# ===========================================================================


class TestBigInt:
    def test_bigint_addition(self):
        assert eval_expr("42n + 1") == 43

    def test_bigint_multiplication(self):
        assert eval_expr("10n * 3") == 30

    def test_bigint_comparison(self):
        assert eval_expr("42n == 42") is True

    def test_bigint_in_variable(self):
        i = run("let v = 100n")
        assert val(i, "v") == 100

    def test_bigint_arithmetic(self):
        assert eval_expr("100n - 1n") == 99

    def test_bigint_zero(self):
        assert eval_expr("0n") == 0


# ===========================================================================
# for {x, y} of list (object destructuring in for-of)
# ===========================================================================


class TestForOfObjectDestruct:
    def test_basic_destruct(self):
        src = "var v = 0\nfor {x, y} of [{x:1,y:2},{x:3,y:4}] { v = v + x + y }"
        i = run(src)
        assert val(i, "v") == 10  # (1+2) + (3+4)

    def test_single_field_destruct(self):
        src = "var v = 0\nfor {n} of [{n:10},{n:20},{n:30}] { v = v + n }"
        i = run(src)
        assert val(i, "v") == 60

    def test_destruct_builds_list(self):
        src = "var v = []\nfor {name} of [{name:\"a\"},{name:\"b\"}] { v.push(name) }"
        i = run(src)
        assert val(i, "v") == ["a", "b"]

    def test_destruct_with_extra_keys(self):
        src = "var v = 0\nfor {x} of [{x:5, y:100}] { v = x }"
        i = run(src)
        assert val(i, "v") == 5


# ===========================================================================
# Class fn get / fn set — getters and setters
# ===========================================================================


class TestGettersSetters:
    def test_getter(self):
        src = """
class Box {
  var _val = 0
  fn get value() { return self._val }
}
let b = Box.new()
let v = b.value
"""
        i = run(src)
        assert val(i, "v") == 0

    def test_setter(self):
        src = """
class Box {
  var _val = 0
  fn get value() { return self._val }
  fn set value(v) { self._val = v }
}
let b = Box.new()
b.value = 42
let v = b.value
"""
        i = run(src)
        assert val(i, "v") == 42

    def test_computed_getter(self):
        src = """
class Rect {
  var width = 4
  var height = 5
  fn get area() { return self.width * self.height }
}
let r = Rect.new()
let v = r.area
"""
        i = run(src)
        assert val(i, "v") == 20

    def test_setter_validates(self):
        src = """
class PositiveNum {
  var _n = 0
  fn get n() { return self._n }
  fn set n(val) {
    if val > 0 {
      self._n = val
    }
  }
}
let p = PositiveNum.new()
p.n = -5
let v = p.n
"""
        i = run(src)
        assert val(i, "v") == 0  # setter rejected negative

    def test_setter_replaces_value(self):
        src = """
class P {
  var _x = 10
  fn get x() { return self._x }
  fn set x(v) { self._x = v * 2 }
}
let p = P.new()
p.x = 7
let v = p.x
"""
        i = run(src)
        assert val(i, "v") == 14


# ===========================================================================
# forEach list method
# ===========================================================================


class TestListForEach:
    def test_foreach_sum(self):
        src = "var total = 0\nlet nums = [1,2,3,4,5]\nnums.forEach(x => { total = total + x })"
        i = run(src)
        assert val(i, "total") == 15

    def test_foreach_with_index(self):
        src = "var idxsum = 0\nlet arr = [10,20,30]\narr.forEach((x, i) => { idxsum = idxsum + i })"
        i = run(src)
        assert val(i, "idxsum") == 3  # 0+1+2

    def test_foreach_mutation(self):
        src = "var v = []\nlet arr = [1,2,3]\narr.forEach(x => { v.push(x * 2) })"
        i = run(src)
        assert val(i, "v") == [2, 4, 6]

    def test_foreach_empty_list(self):
        src = "var v = 0\nlet arr = []\narr.forEach(x => { v = 99 })"
        i = run(src)
        assert val(i, "v") == 0  # never called


# ===========================================================================
# Additional array and string features confirmed working
# ===========================================================================


class TestArrayExtras:
    def test_flatmap(self):
        i = run("let v = [1,2,3].flatMap(x => [x, x * 2])")
        assert val(i, "v") == [1, 2, 2, 4, 3, 6]

    def test_array_of(self):
        assert eval_expr("Array.of(1, 2, 3)") == [1, 2, 3]

    def test_array_is_array(self):
        assert eval_expr("Array.isArray([1,2,3])") is True
        assert eval_expr("Array.isArray(42)") is False

    def test_array_entries(self):
        # entries() returns an iterator of [index, value] pairs
        i = run("let v = [x for x in [\"a\",\"b\"].entries()]")
        assert val(i, "v") == [[0, "a"], [1, "b"]]

    def test_array_keys(self):
        i = run("let v = [x for x in [\"a\",\"b\",\"c\"].keys()]")
        assert val(i, "v") == [0, 1, 2]


class TestStringExtras:
    def test_string_at_positive(self):
        assert eval_expr('"hello".at(0)') == "h"

    def test_string_at_negative(self):
        assert eval_expr('"hello".at(-1)') == "o"

    def test_string_padstart(self):
        assert eval_expr('"5".padStart(3, "0")') == "005"

    def test_string_padend(self):
        assert eval_expr('"hi".padEnd(5, ".")') == "hi..."

    def test_string_repeat(self):
        assert eval_expr('"ab".repeat(3)') == "ababab"

    def test_string_includes(self):
        assert eval_expr('"hello world".includes("world")') is True
        assert eval_expr('"hello world".includes("xyz")') is False


# ===========================================================================
# Math extras
# ===========================================================================


class TestMathExtras:
    def test_math_sign_positive(self):
        assert eval_expr("Math.sign(5)") == 1

    def test_math_sign_negative(self):
        assert eval_expr("Math.sign(-3)") == -1

    def test_math_sign_zero(self):
        assert eval_expr("Math.sign(0)") == 0

    def test_math_trunc_positive(self):
        assert eval_expr("Math.trunc(3.9)") == 3

    def test_math_trunc_negative(self):
        assert eval_expr("Math.trunc(-3.9)") == -3

    def test_math_cbrt(self):
        assert eval_expr("Math.cbrt(27)") == pytest.approx(3.0)

    def test_math_log2(self):
        assert eval_expr("Math.log2(8)") == pytest.approx(3.0)

    def test_math_log10(self):
        assert eval_expr("Math.log10(1000)") == pytest.approx(3.0)

    def test_math_hypot(self):
        assert eval_expr("Math.hypot(3, 4)") == pytest.approx(5.0)


# ===========================================================================
# Object namespace extras
# ===========================================================================


class TestObjectNamespace:
    def test_object_keys(self):
        assert sorted(eval_expr('Object.keys({a:1, b:2, c:3})')) == ["a", "b", "c"]

    def test_object_values(self):
        assert sorted(eval_expr('Object.values({a:1, b:2})')) == [1, 2]

    def test_object_entries(self):
        entries = eval_expr('Object.entries({a:1, b:2})')
        assert sorted(entries) == [["a", 1], ["b", 2]]

    def test_object_from_entries(self):
        assert eval_expr('Object.fromEntries([["a", 1], ["b", 2]])') == {"a": 1, "b": 2}

    def test_object_has_own_property(self):
        assert eval_expr('Object.hasOwn({a:1}, "a")') is True
        assert eval_expr('Object.hasOwn({a:1}, "b")') is False

    def test_object_freeze(self):
        # Frozen objects should still be readable
        i = run('let o = Object.freeze({x: 1})\nlet v = o.x')
        assert val(i, "v") == 1
