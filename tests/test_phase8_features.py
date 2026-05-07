"""
Phase 8 feature tests:
  - `as` type cast postfix — `42 as Text`, `"3" as Int`, etc.
  - `result ok/fail` literal expressions
  - `Set()` builtin — deduplication
  - `events` namespace — on/off/emit/once
  - standalone-language migration coverage — python.* removed
  - Computed property keys — `{[key]: value}`
  - `for [a, b] in list` — destructuring in for-of loop
  - `import "path" as alias` — AS token fix
  - Regex literal with `.match()` / `.search()` / `.matchAll()`
"""

from __future__ import annotations

import math
import pytest

from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# `as` type cast
# ---------------------------------------------------------------------------


class TestTypeCast:
    def test_int_to_text(self):
        i = run("let v = 42 as Text")
        assert val(i, "v") == "42"

    def test_float_to_text(self):
        i = run("let v = 3.14 as Text")
        assert val(i, "v") == "3.14"

    def test_string_to_int(self):
        i = run('let v = "42" as Int')
        assert val(i, "v") == 42

    def test_string_float_to_int(self):
        i = run('let v = "3.9" as Int')
        assert val(i, "v") == 3

    def test_string_to_float(self):
        i = run('let v = "3.14" as Float')
        assert abs(val(i, "v") - 3.14) < 1e-9

    def test_int_to_bool_true(self):
        i = run("let v = 1 as Bool")
        assert val(i, "v") is True

    def test_int_to_bool_false(self):
        i = run("let v = 0 as Bool")
        assert val(i, "v") is False

    def test_string_to_list(self):
        i = run('let v = "abc" as List')
        assert val(i, "v") == ["a", "b", "c"]

    def test_list_to_list(self):
        i = run("let v = [1, 2, 3] as List")
        assert val(i, "v") == [1, 2, 3]

    def test_chained_cast(self):
        i = run("let v = (3 as Float) as Text")
        # _builtin_str strips .0 from whole floats — 3.0 → "3"
        assert val(i, "v") == "3"

    def test_cast_in_expression(self):
        i = run('let v = ("10" as Int) + 5')
        assert val(i, "v") == 15

    def test_cast_in_function(self):
        src = 'fn toNum(s) { return s as Int }\nlet v = toNum("99")'
        i = run(src)
        assert val(i, "v") == 99

    def test_cast_chained_int_text(self):
        i = run("let v = 3.7 as Int as Text")
        assert val(i, "v") == "3"

    def test_cast_does_not_break_with_alias(self):
        # 'with expr as alias' should NOT be treated as type cast
        i = run('var v = null\nwith {x: 42} as obj { v = obj.x }')
        assert val(i, "v") == 42

    def test_cast_does_not_break_import(self):
        i = run('import "math" as m\nlet v = m.floor(3.7)')
        assert val(i, "v") == 3


# ---------------------------------------------------------------------------
# `result ok/fail` literals
# ---------------------------------------------------------------------------


class TestResultLiteral:
    def test_result_ok_value(self):
        i = run("let r = result ok 42\nlet v = r.value")
        assert val(i, "v") == 42

    def test_result_ok_is_ok(self):
        i = run("let r = result ok 42\nlet v = r.ok")
        assert val(i, "v") is True

    def test_result_fail_error(self):
        i = run('let r = result fail "something went wrong"\nlet v = r.error')
        assert val(i, "v") == "something went wrong"

    def test_result_fail_is_ok(self):
        i = run('let r = result fail "err"\nlet v = r.ok')
        assert val(i, "v") is False

    def test_result_ok_zero(self):
        i = run("let r = result ok 0\nlet v = r.value")
        assert val(i, "v") == 0

    def test_result_ok_string(self):
        i = run('let r = result ok "done"\nlet v = r.value')
        assert val(i, "v") == "done"

    def test_result_ok_list(self):
        i = run("let r = result ok [1, 2, 3]\nlet v = r.value")
        assert val(i, "v") == [1, 2, 3]

    def test_result_in_function_return(self):
        src = """fn divide(a, b) {
  if b == 0 { return result fail "division by zero" }
  return result ok a / b
}
let r = divide(10, 2)
let v = r.value"""
        i = run(src)
        assert val(i, "v") == 5.0

    def test_result_fail_in_function(self):
        src = """fn divide(a, b) {
  if b == 0 { return result fail "division by zero" }
  return result ok a / b
}
let r = divide(10, 0)
let v = r.error"""
        i = run(src)
        assert val(i, "v") == "division by zero"

    def test_result_ok_with_expression(self):
        i = run("let n = 5\nlet r = result ok n * 2\nlet v = r.value")
        assert val(i, "v") == 10


# ---------------------------------------------------------------------------
# `Set` builtin
# ---------------------------------------------------------------------------


class TestSetBuiltin:
    def test_dedup_basic(self):
        i = run("let v = Set([1, 2, 2, 3, 1])")
        assert sorted(val(i, "v")) == [1, 2, 3]

    def test_dedup_all_same(self):
        i = run("let v = len(Set([5, 5, 5]))")
        assert val(i, "v") == 1

    def test_dedup_already_unique(self):
        i = run("let v = Set([1, 2, 3])")
        assert val(i, "v") == [1, 2, 3]

    def test_dedup_strings(self):
        i = run('let v = Set(["a", "b", "a", "c"])')
        assert sorted(val(i, "v")) == ["a", "b", "c"]

    def test_dedup_preserves_first_occurrence(self):
        i = run("let v = Set([3, 1, 2, 2, 1])")
        assert val(i, "v") == [3, 1, 2]

    def test_dedup_empty(self):
        i = run("let v = Set([])")
        assert val(i, "v") == []

    def test_dedup_len(self):
        i = run("let v = len(Set([1, 2, 2, 3, 3, 4]))")
        assert val(i, "v") == 4


# ---------------------------------------------------------------------------
# Computed property keys
# ---------------------------------------------------------------------------


class TestComputedPropertyKeys:
    def test_simple_variable_key(self):
        i = run('let k = "name"\nlet obj = {[k]: "Alice"}\nlet v = obj.name')
        assert val(i, "v") == "Alice"

    def test_expression_key(self):
        i = run('let prefix = "key"\nlet n = 1\nlet obj = {[prefix + "_" + (n as Text)]: 99}\nlet v = obj.key_1')
        assert val(i, "v") == 99

    def test_mixed_regular_and_computed(self):
        i = run('let k = "b"\nlet obj = {a: 1, [k]: 2}\nlet v = obj.a + obj.b')
        assert val(i, "v") == 3

    def test_computed_overrides_static(self):
        i = run('let k = "x"\nlet obj = {x: 1, [k]: 2}\nlet v = obj.x')
        assert val(i, "v") == 2

    def test_computed_number_key(self):
        # Number key → string key
        i = run('let idx = 0\nlet obj = {[idx as Text]: "zero"}\nlet v = obj["0"]')
        assert val(i, "v") == "zero"

    def test_computed_in_assign(self):
        i = run('let key = "score"\nvar d = {}\nd[key] = 100\nlet v = d["score"]')
        assert val(i, "v") == 100


# ---------------------------------------------------------------------------
# `for [a, b] in list` destructuring
# ---------------------------------------------------------------------------


class TestForDestructure:
    def test_sum_second_element(self):
        src = """var s = 0
for [i, n] in [[0, 10], [1, 20], [2, 30]] { s = s + n }
let v = s"""
        i = run(src)
        assert val(i, "v") == 60

    def test_collect_first_element(self):
        src = """var keys = []
for [k, v2] in [["a", 1], ["b", 2]] { keys = keys + [k] }
let v = keys"""
        i = run(src)
        assert val(i, "v") == ["a", "b"]

    def test_three_element_destructure(self):
        src = """var s = 0
for [a, b, c] in [[1, 2, 3], [4, 5, 6]] { s = s + a + b + c }
let v = s"""
        i = run(src)
        assert val(i, "v") == 21

    def test_destructure_with_entries(self):
        src = """var total = 0
let pairs = Object.entries({x: 10, y: 20, z: 30})
for [k, n] in pairs { total = total + n }
let v = total"""
        i = run(src)
        assert val(i, "v") == 60

    def test_single_var_still_works(self):
        src = """var s = 0
for x in [1, 2, 3] { s = s + x }
let v = s"""
        i = run(src)
        assert val(i, "v") == 6

    def test_multi_comma_still_works(self):
        src = """var s = 0
for i, n in [[0, 10], [1, 20]] { s = s + n }
let v = s"""
        i = run(src)
        assert val(i, "v") == 30


# ---------------------------------------------------------------------------
# `import "path" as alias`
# ---------------------------------------------------------------------------


class TestImportAlias:
    def test_import_math_as(self):
        i = run('import "math" as m\nlet v = m.floor(3.9)')
        assert val(i, "v") == 3

    def test_import_math_ceil(self):
        i = run('import "math" as m\nlet v = m.ceil(3.1)')
        assert val(i, "v") == 4

    def test_import_math_sqrt(self):
        i = run('import "math" as m\nlet v = m.sqrt(16.0)')
        assert abs(val(i, "v") - 4.0) < 1e-9

    def test_import_json_as(self):
        i = run('import "json" as j\nlet v = j.dumps([1, 2, 3])')
        assert val(i, "v") == "[1, 2, 3]"

    def test_import_without_as(self):
        # Plain import still works
        i = run('import "math"\nlet v = math.floor(2.8)')
        assert val(i, "v") == 2


# ---------------------------------------------------------------------------
# Regex literal with string methods
# ---------------------------------------------------------------------------


class TestRegexLiteralMethods:
    def test_match_basic(self):
        i = run('let v = "hello world".match(/[a-z]+/)')
        from sprycode.interpreter import SpryRegexMatch
        m = val(i, "v")
        assert isinstance(m, SpryRegexMatch)
        assert m[0] == "hello"

    def test_match_no_match(self):
        i = run('let v = "123".match(/[a-z]+/)')
        assert val(i, "v") is None

    def test_match_digits(self):
        i = run('let v = "abc 123 def 456".match(/\\d+/)')
        from sprycode.interpreter import SpryRegexMatch
        m = val(i, "v")
        assert isinstance(m, SpryRegexMatch)
        assert m[0] == "123"

    def test_search_found(self):
        i = run('let v = "hello world".search(/world/)')
        assert val(i, "v") == 6

    def test_search_not_found(self):
        i = run('let v = "hello".search(/xyz/)')
        assert val(i, "v") == -1

    def test_matchAll_all_matches(self):
        i = run('let v = "one two three".matchAll(/[a-z]+/)')
        result = val(i, "v")
        assert [m[0] for m in result] == ["one", "two", "three"]

    def test_regex_test_method(self):
        i = run('let re = /^\\d+$/\nlet v = re.test("12345")')
        assert val(i, "v") is True

    def test_regex_test_fail(self):
        i = run('let re = /^\\d+$/\nlet v = re.test("abc")')
        assert val(i, "v") is False


# ---------------------------------------------------------------------------
# `events` namespace
# ---------------------------------------------------------------------------


class TestEventsNamespace:
    def test_on_and_emit(self):
        i = run('events.on("click", x => x + 1)\nlet v = events.emit("click", 5)')
        assert val(i, "v") == 6

    def test_emit_no_handler(self):
        i = run('let v = events.emit("nonexistent", 5)')
        assert val(i, "v") is None

    def test_multiple_handlers(self):
        src = """var results = []
events.on("data", x => { results = results + [x * 2] })
events.on("data", x => { results = results + [x * 3] })
events.emit("data", 10)
let v = results"""
        i = run(src)
        assert val(i, "v") == [20, 30]

    def test_off_removes_handler(self):
        src = """fn handler(x) { return x + 1 }
events.on("e", handler)
events.off("e", handler)
let v = events.emit("e", 5)"""
        i = run(src)
        assert val(i, "v") is None

    def test_off_all_handlers(self):
        src = """events.on("e", x => x + 1)
events.on("e", x => x + 2)
events.off("e")
let v = events.emit("e", 5)"""
        i = run(src)
        assert val(i, "v") is None

    def test_emit_returns_last_result(self):
        src = """events.on("e", x => x + 1)
events.on("e", x => x * 10)
let v = events.emit("e", 5)"""
        i = run(src)
        assert val(i, "v") == 50  # last handler: 5 * 10

    def test_once_fires_once(self):
        src = """var count = 0
events.once("ping", x => { count = count + x })
events.emit("ping", 1)
events.emit("ping", 1)
events.emit("ping", 1)
let v = count"""
        i = run(src)
        assert val(i, "v") == 1

    def test_listeners_count(self):
        src = """events.on("a", x => x)
events.on("a", x => x * 2)
let v = len(events.listeners("a"))"""
        i = run(src)
        assert val(i, "v") == 2

    def test_listeners_empty(self):
        i = run('let v = len(events.listeners("nope"))')
        assert val(i, "v") == 0


# ---------------------------------------------------------------------------
# SpryCode native equivalents — standalone language (no python.* interop)
# ---------------------------------------------------------------------------


class TestSpryCodeNativeBuiltins:
    """These tests verify that SpryCode provides native equivalents for all
    previously python.* operations, confirming it is a standalone language."""

    def test_arithmetic_power(self):
        # Native arithmetic in SpryCode
        i = run('let v = 2 ** 10')
        assert val(i, "v") == 1024

    def test_string_concat(self):
        # Native string concatenation in SpryCode
        i = run('let v = "hello" + " " + "world"')
        assert val(i, "v") == "hello world"

    def test_array_length(self):
        # Native array length access in SpryCode
        i = run('let v = [1, 2, 3, 4].length')
        assert val(i, "v") == 4

    def test_math_round(self):
        # Native Math usage in SpryCode
        i = run('let v = Math.round(3.14159 * 100) / 100')
        assert val(i, "v") == 3.14

    def test_array_length_via_native(self):
        # Native array length access in SpryCode
        i = run('let v = [1, 2, 3].length')
        assert val(i, "v") == 3

    def test_math_abs(self):
        # Native Math usage in SpryCode
        i = run('let v = Math.abs(-7)')
        assert val(i, "v") == 7

    def test_string_conversion(self):
        # Native String conversion in SpryCode
        i = run('let v = String(42)')
        assert val(i, "v") == "42"

    def test_math_floor(self):
        # Native Math usage in SpryCode
        i = run('let v = Math.floor(3.99)')
        assert val(i, "v") == 3

    def test_array_sort(self):
        # Native array sorting in SpryCode
        i = run('let v = [3, 1, 2].sort()')
        assert val(i, "v") == [1, 2, 3]

    def test_no_python_global(self):
        # Confirm python.* is no longer in the global scope
        with pytest.raises(Exception):
            run('let v = python.eval("1 + 1")')

    def test_native_sorted(self):
        i = run('let v = sorted([3, 1, 2])')
        assert val(i, "v") == [1, 2, 3]

    def test_native_abs(self):
        i = run('let v = abs(-42)')
        assert val(i, "v") == 42

    def test_native_sum(self):
        i = run('let v = sum([1, 2, 3, 4, 5])')
        assert val(i, "v") == 15

    def test_native_sqrt(self):
        i = run('let v = sqrt(16)')
        assert val(i, "v") == 4.0

    def test_native_max(self):
        i = run('let v = max(1, 5, 3)')
        assert val(i, "v") == 5

    def test_native_min(self):
        i = run('let v = min(1, 5, 3)')
        assert val(i, "v") == 1

    def test_native_round(self):
        i = run('let v = round(3.14159)')
        assert val(i, "v") == 3

    def test_math_pow(self):
        i = run('let v = Math.pow(2, 8)')
        assert val(i, "v") == 256

    def test_math_ceil(self):
        i = run('let v = Math.ceil(3.01)')
        assert val(i, "v") == 4

    def test_math_sqrt(self):
        i = run('let v = Math.sqrt(25)')
        assert val(i, "v") == 5.0

    def test_json_parse(self):
        i = run('let v = JSON.parse(\'{"x":42}\').x')
        assert val(i, "v") == 42

    def test_json_stringify(self):
        i = run('let v = JSON.stringify({a:1,b:2})')
        assert isinstance(val(i, "v"), str)



# ---------------------------------------------------------------------------
# Block-body lambdas: `x => { ... }` and `(a, b) => { ... }`
# ---------------------------------------------------------------------------


class TestBlockLambda:
    def test_single_param_block_return(self):
        i = run("let v = [1, 2, 3].map(x => { return x * x })")
        assert val(i, "v") == [1, 4, 9]

    def test_single_param_block_side_effect(self):
        src = """var total = 0
let nums = [1, 2, 3, 4]
nums.map(x => { total = total + x })
let v = total"""
        i = run(src)
        assert val(i, "v") == 10

    def test_multi_param_block_reduce(self):
        i = run("let v = [1, 2, 3, 4, 5].reduce((a, b) => { return a + b })")
        assert val(i, "v") == 15

    def test_block_lambda_with_if(self):
        src = """let v = [1, -2, 3, -4, 5].map(x => {
  if x < 0 { return 0 - x }
  return x
})"""
        i = run(src)
        assert val(i, "v") == [1, 2, 3, 4, 5]

    def test_block_lambda_filter(self):
        i = run("let v = [1, 2, 3, 4, 5, 6].filter(x => { return x % 2 == 0 })")
        assert val(i, "v") == [2, 4, 6]

    def test_block_lambda_events(self):
        src = """var results = []
events.on("data", x => { results = results + [x * 2] })
events.emit("data", 10)
events.emit("data", 20)
let v = results"""
        i = run(src)
        assert val(i, "v") == [20, 40]

    def test_block_lambda_captures_closure(self):
        src = """let factor = 3
let v = [1, 2, 3].map(x => { return x * factor })"""
        i = run(src)
        assert val(i, "v") == [3, 6, 9]
