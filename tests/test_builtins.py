"""
Tests for new built-in namespaces and language features:

- math namespace (math.abs, math.floor, math.PI, etc.)
- json namespace (json.parse, json.stringify)
- date namespace (date.today, date.now, date.format, date.diff)
- random() and randint() builtins
- print() builtin
- type() returning SpryCode type names
- for i in 0..5 range syntax
- for i, v in enumerate(list) destructured loop
- {name, age} object shorthand
- spread in function calls (sum(...args))
"""

import pytest

from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.runtime.stdlib import SpryLogger


def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    out: list[str] = []
    interp = Interpreter(logger=SpryLogger(output=out))
    interp.run(program)
    return interp


# ---------------------------------------------------------------------------
# math namespace
# ---------------------------------------------------------------------------


class TestMathNamespace:
    def test_math_abs(self):
        i = run("let v = math.abs(-7)")
        assert i.globals.get("v") == 7

    def test_math_abs_positive(self):
        i = run("let v = math.abs(5)")
        assert i.globals.get("v") == 5

    def test_math_floor(self):
        i = run("let v = math.floor(3.9)")
        assert i.globals.get("v") == 3

    def test_math_ceil(self):
        i = run("let v = math.ceil(3.1)")
        assert i.globals.get("v") == 4

    def test_math_round(self):
        i = run("let v = math.round(3.5)")
        assert i.globals.get("v") == 4

    def test_math_round_down(self):
        i = run("let v = math.round(3.4)")
        assert i.globals.get("v") == 3

    def test_math_sqrt(self):
        i = run("let v = math.sqrt(9.0)")
        assert i.globals.get("v") == 3.0

    def test_math_pow(self):
        i = run("let v = math.pow(2, 10)")
        assert i.globals.get("v") == 1024

    def test_math_pi(self):
        import math
        i = run("let v = math.PI")
        assert abs(i.globals.get("v") - math.pi) < 1e-10

    def test_math_e(self):
        import math
        i = run("let v = math.E")
        assert abs(i.globals.get("v") - math.e) < 1e-10

    def test_math_min(self):
        i = run("let v = math.min(3, 7)")
        assert i.globals.get("v") == 3

    def test_math_max(self):
        i = run("let v = math.max(3, 7)")
        assert i.globals.get("v") == 7

    def test_math_log(self):
        import math
        i = run("let v = math.log(1)")
        assert i.globals.get("v") == 0.0

    def test_math_sign_positive(self):
        i = run("let v = math.sign(10)")
        assert i.globals.get("v") == 1

    def test_math_sign_negative(self):
        i = run("let v = math.sign(-10)")
        assert i.globals.get("v") == -1

    def test_math_sign_zero(self):
        i = run("let v = math.sign(0)")
        assert i.globals.get("v") == 0

    def test_math_clamp_within(self):
        i = run("let v = math.clamp(5, 0, 10)")
        assert i.globals.get("v") == 5

    def test_math_clamp_below(self):
        i = run("let v = math.clamp(-5, 0, 10)")
        assert i.globals.get("v") == 0

    def test_math_clamp_above(self):
        i = run("let v = math.clamp(15, 0, 10)")
        assert i.globals.get("v") == 10

    def test_math_trunc(self):
        i = run("let v = math.trunc(3.9)")
        assert i.globals.get("v") == 3

    def test_math_trunc_negative(self):
        i = run("let v = math.trunc(-3.9)")
        assert i.globals.get("v") == -3


# ---------------------------------------------------------------------------
# json namespace
# ---------------------------------------------------------------------------


class TestJsonNamespace:
    def test_json_stringify_dict(self):
        import json
        i = run('let v = json.stringify({a: 1})')
        raw = i.globals.get("v")
        assert json.loads(raw) == {"a": 1}

    def test_json_stringify_number(self):
        i = run("let v = json.stringify(42)")
        assert i.globals.get("v") == "42"

    def test_json_stringify_string(self):
        i = run('let v = json.stringify("hello")')
        assert i.globals.get("v") == '"hello"'

    def test_json_stringify_list(self):
        import json
        i = run("let v = json.stringify([1, 2, 3])")
        assert json.loads(i.globals.get("v")) == [1, 2, 3]

    def test_json_roundtrip(self):
        i = run("""
var obj = {name: "Alice", score: 99}
let text = json.stringify(obj)
let back = json.parse(text)
let v = back["name"]
""")
        assert i.globals.get("v") == "Alice"

    def test_json_roundtrip_nested(self):
        i = run("""
var data = {user: {id: 1}}
let text = json.stringify(data)
let parsed = json.parse(text)
let v = parsed["user"]["id"]
""")
        assert i.globals.get("v") == 1

    def test_json_parse_invalid_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("let v = json.parse(\"not json\")")


# ---------------------------------------------------------------------------
# date namespace
# ---------------------------------------------------------------------------


class TestDateNamespace:
    def test_date_today_not_null(self):
        i = run("let v = date.today() != null")
        assert i.globals.get("v") is True

    def test_date_today_iso_format(self):
        from datetime import date
        i = run("let v = date.today()")
        val = i.globals.get("v")
        assert isinstance(val, str)
        # Should be a valid ISO date
        date.fromisoformat(val)

    def test_date_now_not_null(self):
        i = run("let v = date.now() != null")
        assert i.globals.get("v") is True

    def test_date_now_is_string(self):
        i = run("let v = date.now()")
        val = i.globals.get("v")
        assert isinstance(val, str)

    def test_date_utcnow(self):
        i = run("let v = date.utcnow()")
        val = i.globals.get("v")
        assert isinstance(val, str)
        assert "T" in val

    def test_date_format(self):
        i = run('let v = date.format("2024-01-15", "%Y/%m/%d")')
        assert i.globals.get("v") == "2024/01/15"

    def test_date_diff_days(self):
        i = run('let v = date.diff("2024-01-01", "2024-01-11")')
        assert i.globals.get("v") == 10

    def test_date_diff_seconds(self):
        i = run('let v = date.diff("2024-01-01T00:00:00", "2024-01-01T01:00:00", "seconds")')
        assert i.globals.get("v") == 3600.0


# ---------------------------------------------------------------------------
# random() and randint()
# ---------------------------------------------------------------------------


class TestRandomBuiltins:
    def test_random_in_range(self):
        i = run("let v = random()")
        v = i.globals.get("v")
        assert isinstance(v, float)
        assert 0.0 <= v < 1.0

    def test_randint_in_range(self):
        i = run("let v = randint(1, 10)")
        v = i.globals.get("v")
        assert isinstance(v, int)
        assert 1 <= v <= 10

    def test_randint_single_value(self):
        i = run("let v = randint(5, 5)")
        assert i.globals.get("v") == 5


# ---------------------------------------------------------------------------
# print() builtin
# ---------------------------------------------------------------------------


class TestPrintBuiltin:
    def test_print_does_not_raise(self):
        run('print("hello")')

    def test_print_number(self):
        run("print(42)")

    def test_print_multiple_args(self):
        run('print("a", "b", "c")')


# ---------------------------------------------------------------------------
# type() returning SpryCode type names
# ---------------------------------------------------------------------------


class TestTypeBuiltin:
    def test_type_number_int(self):
        i = run("let v = type(42)")
        assert i.globals.get("v") == "Number"

    def test_type_number_float(self):
        i = run("let v = type(3.14)")
        assert i.globals.get("v") == "Number"

    def test_type_text(self):
        i = run('let v = type("hello")')
        assert i.globals.get("v") == "Text"

    def test_type_bool_true(self):
        i = run("let v = type(true)")
        assert i.globals.get("v") == "Bool"

    def test_type_bool_false(self):
        i = run("let v = type(false)")
        assert i.globals.get("v") == "Bool"

    def test_type_list(self):
        i = run("let v = type([1, 2, 3])")
        assert i.globals.get("v") == "List"

    def test_type_map(self):
        i = run("let v = type({a: 1})")
        assert i.globals.get("v") == "Map"

    def test_type_null(self):
        i = run("let v = type(null)")
        assert i.globals.get("v") == "Null"

    def test_type_class_instance(self):
        i = run("""
class Dog { var name = "" }
let d = Dog()
let v = type(d)
""")
        assert i.globals.get("v") == "Dog"


# ---------------------------------------------------------------------------
# for i in 0..5 range syntax
# ---------------------------------------------------------------------------


class TestRangeLoop:
    def test_range_sum(self):
        i = run("""
var s = 0
for i in 0..5 { s = s + i }
let v = s
""")
        assert i.globals.get("v") == 10  # 0+1+2+3+4

    def test_range_1_to_6(self):
        i = run("""
var s = 0
for i in 1..6 { s = s + i }
let v = s
""")
        assert i.globals.get("v") == 15  # 1+2+3+4+5

    def test_range_list_fill(self):
        i = run("""
var result = []
for i in 0..4 {
    result.push(i * i)
}
let v = result
""")
        assert i.globals.get("v") == [0, 1, 4, 9]

    def test_range_single(self):
        i = run("""
var s = 0
for i in 5..6 { s = s + i }
let v = s
""")
        assert i.globals.get("v") == 5

    def test_range_empty(self):
        i = run("""
var s = 0
for i in 5..5 { s = s + 1 }
let v = s
""")
        assert i.globals.get("v") == 0  # empty range

    def test_range_variable(self):
        i = run("""
let n = 4
var s = 0
for i in 0..n { s += 1 }
let v = s
""")
        assert i.globals.get("v") == 4

    def test_range_break(self):
        i = run("""
var s = 0
for i in 0..10 {
    if i == 3 { break }
    s = s + i
}
let v = s
""")
        assert i.globals.get("v") == 3  # 0+1+2


# ---------------------------------------------------------------------------
# for i, v in enumerate(list)
# ---------------------------------------------------------------------------


class TestDestructuredFor:
    def test_enumerate_indices(self):
        i = run("""
var result = []
for idx, val in enumerate([10, 20, 30]) {
    result.push(idx)
}
let v = result
""")
        assert i.globals.get("v") == [0, 1, 2]

    def test_enumerate_values(self):
        i = run("""
var s = 0
for idx, val in enumerate([10, 20, 30]) {
    s = s + val
}
let v = s
""")
        assert i.globals.get("v") == 60

    def test_enumerate_index_plus_value(self):
        i = run("""
var s = 0
for i, v in enumerate([1, 2, 3]) {
    s = s + i * v
}
let v = s
""")
        assert i.globals.get("v") == 8  # 0*1 + 1*2 + 2*3 = 0+2+6

    def test_for_on_nested_list(self):
        # Iterate over [[0, 10], [1, 20], [2, 30]] directly
        i = run("""
var result = []
let pairs = [[0, 10], [1, 20], [2, 30]]
for i, v in pairs {
    result.push(v)
}
let r = result
""")
        assert i.globals.get("r") == [10, 20, 30]

    def test_enumerate_with_break(self):
        i = run("""
var s = 0
for i, v in enumerate([10, 20, 30, 40]) {
    if i == 2 { break }
    s = s + v
}
let r = s
""")
        assert i.globals.get("r") == 30  # 10+20


# ---------------------------------------------------------------------------
# Object shorthand { name, age }
# ---------------------------------------------------------------------------


class TestObjectShorthand:
    def test_single_shorthand(self):
        i = run("""
let name = "Alice"
let v = {name}
""")
        assert i.globals.get("v") == {"name": "Alice"}

    def test_multiple_shorthand(self):
        i = run("""
let name = "Bob"
let age = 25
let v = {name, age}
""")
        assert i.globals.get("v") == {"name": "Bob", "age": 25}

    def test_mixed_shorthand_and_literal(self):
        i = run("""
let x = 10
let v = {x, y: 20}
""")
        assert i.globals.get("v") == {"x": 10, "y": 20}

    def test_shorthand_in_function(self):
        i = run("""
fn make_point(x, y) {
    return {x, y}
}
let v = make_point(3, 4)
""")
        assert i.globals.get("v") == {"x": 3, "y": 4}

    def test_shorthand_with_number(self):
        i = run("""
let score = 99
let v = {score}
""")
        assert i.globals.get("v") == {"score": 99}


# ---------------------------------------------------------------------------
# Spread in function calls
# ---------------------------------------------------------------------------


class TestSpreadCalls:
    def test_spread_basic(self):
        i = run("""
fn sum(a, b, c) { return a + b + c }
let args = [1, 2, 3]
let v = sum(...args)
""")
        assert i.globals.get("v") == 6

    def test_spread_two_args(self):
        i = run("""
fn add(x, y) { return x + y }
let nums = [10, 20]
let v = add(...nums)
""")
        assert i.globals.get("v") == 30

    def test_spread_with_leading_arg(self):
        i = run("""
fn f(a, b, c) { return a + b + c }
let rest = [2, 3]
let v = f(1, ...rest)
""")
        assert i.globals.get("v") == 6

    def test_spread_builtin(self):
        i = run("""
let nums = [3, 1, 4, 1, 5]
let v = max(...nums)
""")
        assert i.globals.get("v") == 5

    def test_spread_into_list_concat(self):
        i = run("""
fn make_list(a, b, c) { return [a, b, c] }
let items = [10, 20, 30]
let v = make_list(...items)
""")
        assert i.globals.get("v") == [10, 20, 30]
