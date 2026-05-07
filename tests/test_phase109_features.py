"""Phase 109: SpryCode as a standalone language.

Tests covering:
  - python.* namespace removed (SpryCode is now a standalone language)
  - log debug/trace/verbose/notice levels
  - match expression with comma-separated arms (JS-style)
  - typed catch binding: catch(e: TypeError)
  - interface with bare method signatures (no fn keyword)
  - `as const` / `as Type` post-fix annotation (no-op)
  - `type Alias = ...` type alias declarations (no-op)
  - pipeline `|> map namedFn` / `|> filter namedFn` / `|> each namedFn`
"""

import pytest
from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# python.* namespace removed — SpryCode is a standalone language
# ---------------------------------------------------------------------------


class TestPythonInteropRemoved:
    def test_python_global_does_not_exist(self):
        """python.* must no longer be accessible in SpryCode scripts."""
        with pytest.raises(Exception):
            run('let v = python.eval("1+1")')

    def test_python_call_not_available(self):
        with pytest.raises(Exception):
            run('let v = python.call("abs", -5)')

    def test_python_import_not_available(self):
        with pytest.raises(Exception):
            run('let v = python.import_module("math")')

    def test_native_power_replaces_python_eval(self):
        i = run('let v = 2 ** 10')
        assert val(i, 'v') == 1024

    def test_native_string_concat_replaces_python_eval(self):
        i = run('let v = "hello" + " " + "world"')
        assert val(i, 'v') == 'hello world'

    def test_native_length_replaces_python_len(self):
        i = run('let v = [1, 2, 3, 4].length')
        assert val(i, 'v') == 4

    def test_math_floor_replaces_python_import_math(self):
        i = run('let v = Math.floor(3.99)')
        assert val(i, 'v') == 3

    def test_math_abs_replaces_python_call_abs(self):
        i = run('let v = Math.abs(-7)')
        assert val(i, 'v') == 7

    def test_string_conversion_replaces_python_call_str(self):
        i = run('let v = String(42)')
        assert val(i, 'v') == '42'

    def test_array_sort_replaces_python_sorted(self):
        i = run('let v = [3, 1, 2].sort()')
        assert val(i, 'v') == [1, 2, 3]

    def test_native_sorted_replaces_python_sorted(self):
        i = run('let v = sorted([5, 3, 1, 4, 2])')
        assert val(i, 'v') == [1, 2, 3, 4, 5]

    def test_native_abs_builtin(self):
        i = run('let v = abs(-42)')
        assert val(i, 'v') == 42

    def test_native_sum_builtin(self):
        i = run('let v = sum([1, 2, 3, 4, 5])')
        assert val(i, 'v') == 15

    def test_native_sqrt_builtin(self):
        i = run('let v = sqrt(16)')
        assert val(i, 'v') == 4.0

    def test_native_max_builtin(self):
        i = run('let v = max(1, 10, 3, 7)')
        assert val(i, 'v') == 10

    def test_native_min_builtin(self):
        i = run('let v = min(5, 2, 8, 1)')
        assert val(i, 'v') == 1

    def test_native_round_builtin(self):
        i = run('let v = round(3.7)')
        assert val(i, 'v') == 4

    def test_json_parse_native(self):
        i = run('let v = JSON.parse(\'{"x":42}\').x')
        assert val(i, 'v') == 42

    def test_json_stringify_native(self):
        i = run('let v = JSON.stringify({a: 1})')
        assert isinstance(val(i, 'v'), str)


# ---------------------------------------------------------------------------
# log debug / trace / verbose / notice levels
# ---------------------------------------------------------------------------


class TestLogLevels:
    def test_log_info(self):
        i = run('log info "hello"\nlet v = true')
        assert val(i, 'v') is True

    def test_log_warn(self):
        i = run('log warn "careful"\nlet v = true')
        assert val(i, 'v') is True

    def test_log_error(self):
        i = run('log error "fail"\nlet v = true')
        assert val(i, 'v') is True

    def test_log_debug(self):
        i = run('log debug "debugging"\nlet v = true')
        assert val(i, 'v') is True

    def test_log_trace(self):
        i = run('log trace "tracing"\nlet v = true')
        assert val(i, 'v') is True

    def test_log_verbose(self):
        i = run('log verbose "verbose message"\nlet v = true')
        assert val(i, 'v') is True

    def test_log_notice(self):
        i = run('log notice "notice"\nlet v = true')
        assert val(i, 'v') is True

    def test_log_debug_with_fstring(self):
        i = run('let x = 42\nlog debug f"value is {x}"\nlet v = true')
        assert val(i, 'v') is True


# ---------------------------------------------------------------------------
# match expression with comma-separated arms
# ---------------------------------------------------------------------------


class TestMatchCommaArms:
    def test_match_first_arm(self):
        i = run('let x = 1; let v = match x { 1 => "one", 2 => "two", _ => "other" }')
        assert val(i, 'v') == 'one'

    def test_match_second_arm(self):
        i = run('let x = 2; let v = match x { 1 => "one", 2 => "two", _ => "other" }')
        assert val(i, 'v') == 'two'

    def test_match_wildcard_arm(self):
        i = run('let x = 99; let v = match x { 1 => "one", 2 => "two", _ => "other" }')
        assert val(i, 'v') == 'other'

    def test_match_string_subject(self):
        i = run('let s = "b"; let v = match s { "a" => 1, "b" => 2, _ => 0 }')
        assert val(i, 'v') == 2

    def test_match_single_arm_comma(self):
        i = run('let x = 5; let v = match x { 5 => "five", }')
        assert val(i, 'v') == 'five'

    def test_match_mixed_newline_and_comma(self):
        i = run('''
let x = 3
let v = match x {
  1 => "one",
  2 => "two",
  3 => "three"
  _ => "other"
}
''')
        assert val(i, 'v') == 'three'

    def test_match_comma_arms_no_wildcard(self):
        i = run('let x = 10; let v = match x { 1 => "one", 10 => "ten" }')
        assert val(i, 'v') == 'ten'

    def test_match_still_works_with_newlines(self):
        i = run('''
let n = 2
let v = match n {
  1 => "one"
  2 => "two"
  _ => "other"
}
''')
        assert val(i, 'v') == 'two'


# ---------------------------------------------------------------------------
# typed catch binding: catch(e: TypeError)
# ---------------------------------------------------------------------------


class TestTypedCatch:
    def test_catch_typed_simple(self):
        i = run('''
let v = "none"
try {
  throw new TypeError("type error")
} catch(e: TypeError) {
  v = e.message
}
''')
        assert val(i, 'v') == 'type error'

    def test_catch_typed_range_error(self):
        i = run('''
let v = false
try {
  throw new RangeError("out of range")
} catch(e: RangeError) {
  v = true
}
''')
        assert val(i, 'v') is True

    def test_catch_typed_custom_error(self):
        i = run('''
let v = false
try {
  throw new Error("custom")
} catch(e: Error) {
  v = e.message == "custom"
}
''')
        assert val(i, 'v') is True

    def test_catch_typed_catches_all_same_as_untyped(self):
        i = run('''
let v = 0
try {
  throw new Error("err")
} catch(e: SomeType) {
  v = 1
}
''')
        assert val(i, 'v') == 1

    def test_catch_typed_preserves_error_info(self):
        i = run('''
var msg = ""
try {
  throw new TypeError("oops")
} catch(e: TypeError) {
  msg = e.message
}
let v = msg
''')
        assert val(i, 'v') == 'oops'


# ---------------------------------------------------------------------------
# interface with bare method signatures (no fn keyword)
# ---------------------------------------------------------------------------


class TestInterfaceBareSignatures:
    def test_interface_bare_method(self):
        i = run('''
interface Greeter {
  greet(name: Text) -> Text
}
let v = true
''')
        assert val(i, 'v') is True

    def test_interface_multiple_methods(self):
        i = run('''
interface Shape {
  area() -> Number
  perimeter() -> Number
  describe(label: Text) -> Text
}
let v = true
''')
        assert val(i, 'v') is True

    def test_interface_mixed_fn_and_bare(self):
        i = run('''
interface Processor {
  fn process(data: Text) -> Text
  validate(input: Text) -> Bool
}
let v = true
''')
        assert val(i, 'v') is True

    def test_interface_no_params(self):
        i = run('''
interface Printable {
  toString() -> Text
  print()
}
let v = true
''')
        assert val(i, 'v') is True

    def test_interface_used_as_class_implements(self):
        i = run('''
interface Animal {
  speak() -> Text
}

class Dog implements Animal {
  speak() {
    return "woof"
  }
}

let v = new Dog().speak()
''')
        assert val(i, 'v') == 'woof'


# ---------------------------------------------------------------------------
# `as const` / `as Type` post-fix annotation (no-op at runtime)
# ---------------------------------------------------------------------------


class TestAsConstAnnotation:
    def test_as_const_object(self):
        i = run('let obj = {a: 1, b: 2} as const\nlet v = obj.a')
        assert val(i, 'v') == 1

    def test_as_const_array(self):
        i = run('let arr = [1, 2, 3] as const\nlet v = arr.length')
        assert val(i, 'v') == 3

    def test_as_const_string(self):
        i = run('let s = "hello" as const\nlet v = s.length')
        assert val(i, 'v') == 5

    def test_as_number_type(self):
        i = run('let x = 42 as Number\nlet v = x + 1')
        assert val(i, 'v') == 43

    def test_as_int_type_truncates(self):
        i = run('let x = 3.7 as Int\nlet v = x')
        assert val(i, 'v') == 3

    def test_as_text_type(self):
        i = run('let x = 42 as Text\nlet v = x')
        assert val(i, 'v') == '42'

    def test_as_const_does_not_break_with_alias(self):
        # 'with expr as alias' must NOT be consumed as a type cast
        i = run('var v = null\nwith {x: 42} as obj { v = obj.x }')
        assert val(i, 'v') == 42

    def test_as_const_chained(self):
        i = run('let v = 3.7 as Int as Text')
        assert val(i, 'v') == '3'


# ---------------------------------------------------------------------------
# `type Alias = ...` type alias declarations (no-op at runtime)
# ---------------------------------------------------------------------------


class TestTypeAlias:
    def test_type_alias_declaration_no_error(self):
        i = run('type UserId = Number\nlet v = true')
        assert val(i, 'v') is True

    def test_type_alias_then_use_native_type(self):
        i = run('type Label = Text\nlet v = "hello"')
        assert val(i, 'v') == 'hello'

    def test_multiple_type_aliases(self):
        i = run('''
type Name = Text
type Age = Number
type Active = Bool
let v = true
''')
        assert val(i, 'v') is True

    def test_type_alias_before_function(self):
        i = run('''
type Score = Number
fn doubled(x: Score) -> Score {
  return x * 2
}
let v = doubled(21)
''')
        assert val(i, 'v') == 42


# ---------------------------------------------------------------------------
# pipeline |> map/filter/each with named function reference
# ---------------------------------------------------------------------------


class TestPipelineNamedFunction:
    def test_map_named_fn(self):
        i = run('''
fn double(x) { return x * 2 }
let v = [1, 2, 3] |> map double
''')
        assert val(i, 'v') == [2, 4, 6]

    def test_filter_named_fn(self):
        i = run('''
fn isEven(x) { return x % 2 == 0 }
let v = [1, 2, 3, 4, 5, 6] |> filter isEven
''')
        assert val(i, 'v') == [2, 4, 6]

    def test_each_named_fn(self):
        i = run('''
let total = 0
fn accumulate(x) { total = total + x }
[10, 20, 30] |> each accumulate
let v = total
''')
        assert val(i, 'v') == 60

    def test_map_lambda_still_works(self):
        i = run('let v = [1, 2, 3] |> map x => x * 3')
        assert val(i, 'v') == [3, 6, 9]

    def test_filter_lambda_still_works(self):
        i = run('let v = [1, 2, 3, 4, 5] |> filter x => x > 2')
        assert val(i, 'v') == [3, 4, 5]

    def test_map_named_fn_chained(self):
        i = run('''
fn addTen(x) { return x + 10 }
fn double(x) { return x * 2 }
let v = [1, 2, 3] |> map addTen |> map double
''')
        assert val(i, 'v') == [22, 24, 26]

    def test_filter_then_map_named(self):
        i = run('''
fn isOdd(x) { return x % 2 != 0 }
fn square(x) { return x * x }
let v = [1, 2, 3, 4, 5] |> filter isOdd |> map square
''')
        assert val(i, 'v') == [1, 9, 25]

    def test_pipe_with_regular_function_passthrough(self):
        # nums |> len — passes whole list to len
        i = run('let nums = [1, 2, 3]\nlet v = nums |> len')
        assert val(i, 'v') == 3

    def test_pipe_map_named_lambda_fn(self):
        # Function defined as lambda assignment
        i = run('''
let triple = x => x * 3
let v = [1, 2, 3] |> map triple
''')
        assert val(i, 'v') == [3, 6, 9]

    def test_filter_named_fn_empty_result(self):
        i = run('''
fn never(x) { return false }
let v = [1, 2, 3] |> filter never
''')
        assert val(i, 'v') == []

    def test_map_named_fn_single_value(self):
        i = run('''
fn inc(x) { return x + 1 }
let v = 41 |> map inc
''')
        assert val(i, 'v') == 42
