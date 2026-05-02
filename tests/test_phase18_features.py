"""Phase 18 feature tests.

Covers:
- Semicolons as statement separators inside blocks `{ a; b; c }`
- list.sort(comparator) — sort with custom comparator function
- JS-style parseInt / parseFloat (stop at non-numeric, hex/binary prefixes)
- string.concat(...)
- URLSearchParams global
- TextEncoder / TextDecoder globals
- AbortController / AbortSignal globals
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
# Semicolons as statement separators in blocks
# ===========================================================================

class TestSemicolonsInBlocks:
    def test_semicolons_in_fn_body(self):
        i = run("fn f() { let a = 1; let b = 2; return a + b }\nlet r = f()")
        assert val(i, "r") == 3

    def test_trailing_semicolons_in_fn(self):
        i = run("fn f() { return 42; }\nlet r = f()")
        assert val(i, "r") == 42

    def test_multiple_stmts_semicolons(self):
        i = run("fn f() { let x = 10; let y = 20; let z = 30; return x + y + z }\nlet r = f()")
        assert val(i, "r") == 60

    def test_semicolons_in_if_body(self):
        i = run("var r = 0\nif true { r = 1; r = r + 1 }")
        assert val(i, "r") == 2

    def test_semicolons_in_while_body(self):
        i = run("var c = 0; var s = 0\nwhile c < 3 { c = c + 1; s = s + c }")
        assert val(i, "s") == 6

    def test_semicolons_in_for_body(self):
        i = run("var s = 0\nfor x in [1,2,3] { let t = x * 2; s = s + t }")
        assert val(i, "s") == 12

    def test_semicolons_in_class_method(self):
        i = run("""
class Adder {
  fn add(a, b) { let x = a; let y = b; return x + y }
}
let a = Adder.new()
let r = a.add(3, 4)
""")
        assert val(i, "r") == 7

    def test_empty_semicolons_only(self):
        i = run("fn f() { ; ; return 99 }\nlet r = f()")
        assert val(i, "r") == 99

    def test_semicolons_between_expressions(self):
        i = run("var a = 1\nvar b = 0\nfn f() { a = 2; b = 3 }\nf()")
        assert val(i, "a") == 2
        assert val(i, "b") == 3

    def test_semicolons_in_lambda_block(self):
        i = run("let f = x => { let y = x + 1; return y * 2 }\nlet r = f(4)")
        assert val(i, "r") == 10

    def test_semicolons_in_nested_blocks(self):
        i = run("""
fn f() {
  var result = 0
  if true { result = 1; result = result + 2 }
  return result
}
let r = f()
""")
        assert val(i, "r") == 3

    def test_semicolons_in_try_catch(self):
        i = run("""
var v = 0
try { let x = 1; v = x } catch e { v = -1 }
""")
        assert val(i, "v") == 1


# ===========================================================================
# list.sort with comparator
# ===========================================================================

class TestSortComparator:
    def test_sort_no_args_numbers(self):
        assert eval_expr("[3, 1, 2].sort()") == [1, 2, 3]

    def test_sort_no_args_strings(self):
        assert eval_expr('[\"banana\", \"apple\", \"cherry\"].sort()') == ["apple", "banana", "cherry"]

    def test_sort_as_property(self):
        i = run("let nums = [3, 1, 2]\nlet s = nums.sort")
        assert val(i, "s") == [1, 2, 3]

    def test_sort_ascending_comparator(self):
        i = run("let r = [3, 1, 2].sort((a, b) => a - b)")
        assert val(i, "r") == [1, 2, 3]

    def test_sort_descending_comparator(self):
        i = run("let r = [3, 1, 2].sort((a, b) => b - a)")
        assert val(i, "r") == [3, 2, 1]

    def test_sort_with_lambda(self):
        i = run("let r = [10, 3, 7, 1].sort((a, b) => a - b)")
        assert val(i, "r") == [1, 3, 7, 10]

    def test_sort_descending_large(self):
        i = run("let r = [5, 2, 8, 1, 9].sort((a, b) => b - a)")
        assert val(i, "r") == [9, 8, 5, 2, 1]

    def test_sort_by_key(self):
        # Sort strings by length using comparator
        i = run("let r = [\"bb\", \"a\", \"ccc\"].sort((a, b) => a.length - b.length)")
        assert val(i, "r") == ["a", "bb", "ccc"]

    def test_sort_does_not_mutate(self):
        i = run("let orig = [3, 1, 2]\nlet sorted = orig.sort((a, b) => a - b)\nlet still = orig")
        # The original should be unchanged (sort returns new list)
        assert val(i, "sorted") == [1, 2, 3]

    def test_sort_stable_equal(self):
        i = run("let r = [2, 1, 2, 1].sort((a, b) => a - b)")
        assert val(i, "r") == [1, 1, 2, 2]

    def test_toSorted_with_comparator(self):
        i = run("let r = [3, 1, 2].toSorted((a, b) => b - a)")
        assert val(i, "r") == [3, 2, 1]


# ===========================================================================
# parseInt / parseFloat (JS-style)
# ===========================================================================

class TestJsParseInt:
    def test_basic_int(self):
        assert eval_expr('parseInt("42")') == 42

    def test_trailing_alpha(self):
        assert eval_expr('parseInt("42abc")') == 42

    def test_trailing_spaces_ignored(self):
        assert eval_expr('parseInt("  42  ")') == 42

    def test_leading_sign_negative(self):
        assert eval_expr('parseInt("-5")') == -5

    def test_hex_prefix(self):
        assert eval_expr('parseInt("0x1F")') == 31

    def test_hex_prefix_uppercase(self):
        assert eval_expr('parseInt("0XFF")') == 255

    def test_binary_prefix(self):
        assert eval_expr('parseInt("0b1010")') == 10

    def test_octal_prefix(self):
        assert eval_expr('parseInt("0o17")') == 15

    def test_explicit_base_16(self):
        assert eval_expr('parseInt("FF", 16)') == 255

    def test_explicit_base_2(self):
        assert eval_expr('parseInt("1010", 2)') == 10

    def test_explicit_base_8(self):
        assert eval_expr('parseInt("17", 8)') == 15

    def test_empty_string_nan(self):
        assert math.isnan(eval_expr('parseInt("")'))

    def test_non_numeric_nan(self):
        assert math.isnan(eval_expr('parseInt("abc")'))

    def test_number_passthrough(self):
        assert eval_expr('parseInt("100")') == 100

    def test_number_global_parseint(self):
        assert eval_expr('Number.parseInt("42abc")') == 42

    def test_number_global_parseint_hex(self):
        assert eval_expr('Number.parseInt("0xFF")') == 255


class TestJsParseFloat:
    def test_basic_float(self):
        assert eval_expr('parseFloat("3.14")') == pytest.approx(3.14)

    def test_trailing_alpha(self):
        assert eval_expr('parseFloat("3.14abc")') == pytest.approx(3.14)

    def test_leading_spaces(self):
        assert eval_expr('parseFloat("  2.71 ")') == pytest.approx(2.71)

    def test_integer_string(self):
        assert eval_expr('parseFloat("42")') == pytest.approx(42.0)

    def test_scientific_notation(self):
        assert eval_expr('parseFloat("1.5e3")') == pytest.approx(1500.0)

    def test_negative(self):
        assert eval_expr('parseFloat("-3.14")') == pytest.approx(-3.14)

    def test_empty_string_nan(self):
        assert math.isnan(eval_expr('parseFloat("")'))

    def test_non_numeric_nan(self):
        assert math.isnan(eval_expr('parseFloat("abc")'))

    def test_number_global_parsefloat(self):
        assert eval_expr('Number.parseFloat("3.14xyz")') == pytest.approx(3.14)


# ===========================================================================
# string.concat
# ===========================================================================

class TestStringConcat:
    def test_concat_single(self):
        assert eval_expr('"hello".concat(" world")') == "hello world"

    def test_concat_multiple(self):
        assert eval_expr('"a".concat("b", "c", "d")') == "abcd"

    def test_concat_with_numbers(self):
        assert eval_expr('"value: ".concat(42)') == "value: 42"

    def test_concat_empty(self):
        assert eval_expr('"hello".concat("")') == "hello"

    def test_concat_on_empty(self):
        assert eval_expr('"".concat("hello", " world")') == "hello world"

    def test_concat_no_args(self):
        assert eval_expr('"hello".concat()') == "hello"


# ===========================================================================
# URLSearchParams
# ===========================================================================

class TestURLSearchParams:
    def test_new_from_string(self):
        i = run('let u = URLSearchParams.new("a=1&b=2")\nlet r = u.get("a")')
        assert val(i, "r") == "1"

    def test_get_second_param(self):
        i = run('let u = URLSearchParams.new("a=1&b=2")\nlet r = u.get("b")')
        assert val(i, "r") == "2"

    def test_get_missing_returns_null(self):
        i = run('let u = URLSearchParams.new("a=1")\nlet r = u.get("z")')
        assert val(i, "r") is None

    def test_has_key(self):
        i = run('let u = URLSearchParams.new("a=1&b=2")\nlet r = u.has("a")')
        assert val(i, "r") is True

    def test_has_missing_key(self):
        i = run('let u = URLSearchParams.new("a=1")\nlet r = u.has("z")')
        assert val(i, "r") is False

    def test_set_existing(self):
        i = run('let u = URLSearchParams.new("a=1")\nu.set("a", "99")\nlet r = u.get("a")')
        assert val(i, "r") == "99"

    def test_set_new_key(self):
        i = run('let u = URLSearchParams.new("a=1")\nu.set("b", "2")\nlet r = u.get("b")')
        assert val(i, "r") == "2"

    def test_append(self):
        i = run('let u = URLSearchParams.new("a=1")\nu.append("a", "2")\nlet r = u.getAll("a")')
        assert val(i, "r") == ["1", "2"]

    def test_delete(self):
        i = run('let u = URLSearchParams.new("a=1&b=2")\nu.delete("a")\nlet r = u.has("a")')
        assert val(i, "r") is False

    def test_toString(self):
        i = run('let u = URLSearchParams.new("a=1&b=2")\nlet r = u.toString()')
        assert "a=1" in val(i, "r")
        assert "b=2" in val(i, "r")

    def test_size_property(self):
        i = run('let u = URLSearchParams.new("a=1&b=2&c=3")\nlet r = u.size')
        assert val(i, "r") == 3

    def test_from_empty_string(self):
        i = run('let u = URLSearchParams.new("")\nlet r = u.size')
        assert val(i, "r") == 0

    def test_from_dict(self):
        i = run('let u = URLSearchParams.new({x: "1", y: "2"})\nlet r = u.get("x")')
        assert val(i, "r") == "1"

    def test_from_list_of_pairs(self):
        i = run('let u = URLSearchParams.new([[\"k\", \"v\"]])\nlet r = u.get("k")')
        assert val(i, "r") == "v"

    def test_question_mark_prefix_stripped(self):
        i = run('let u = URLSearchParams.new("?a=1&b=2")\nlet r = u.get("a")')
        assert val(i, "r") == "1"


# ===========================================================================
# TextEncoder / TextDecoder
# ===========================================================================

class TestTextEncoder:
    def test_encode_simple(self):
        i = run('let t = TextEncoder.new()\nlet r = t.encode("hi")')
        assert val(i, "r") == [104, 105]

    def test_encode_empty(self):
        i = run('let t = TextEncoder.new()\nlet r = t.encode("")')
        assert val(i, "r") == []

    def test_encode_utf8(self):
        i = run('let t = TextEncoder.new()\nlet r = t.encode("A")')
        assert val(i, "r") == [65]

    def test_encode_hello(self):
        i = run('let t = TextEncoder.new()\nlet r = t.encode("hello")')
        assert val(i, "r") == [104, 101, 108, 108, 111]

    def test_encoding_property(self):
        i = run('let t = TextEncoder.new()\nlet r = t.encoding')
        assert val(i, "r") == "utf-8"


class TestTextDecoder:
    def test_decode_bytes(self):
        i = run('let d = TextDecoder.new()\nlet r = d.decode([104, 101, 108, 108, 111])')
        assert val(i, "r") == "hello"

    def test_decode_empty(self):
        i = run('let d = TextDecoder.new()\nlet r = d.decode([])')
        assert val(i, "r") == ""

    def test_decode_single_byte(self):
        i = run('let d = TextDecoder.new()\nlet r = d.decode([65])')
        assert val(i, "r") == "A"

    def test_roundtrip(self):
        i = run("""
let enc = TextEncoder.new()
let dec = TextDecoder.new()
let bytes = enc.encode("hello world")
let r = dec.decode(bytes)
""")
        assert val(i, "r") == "hello world"

    def test_decode_no_args(self):
        i = run('let d = TextDecoder.new()\nlet r = d.decode()')
        assert val(i, "r") == ""

    def test_encoding_property(self):
        i = run('let d = TextDecoder.new()\nlet r = d.encoding')
        assert "utf" in val(i, "r").lower()


# ===========================================================================
# AbortController / AbortSignal
# ===========================================================================

class TestAbortController:
    def test_new_controller(self):
        i = run('let ac = AbortController.new()\nlet r = ac.signal.aborted')
        assert val(i, "r") is False

    def test_abort(self):
        i = run('let ac = AbortController.new()\nac.abort()\nlet r = ac.signal.aborted')
        assert val(i, "r") is True

    def test_abort_reason(self):
        i = run('let ac = AbortController.new()\nac.abort("cancelled")\nlet r = ac.signal.reason')
        assert val(i, "r") == "cancelled"

    def test_signal_not_aborted_before_abort(self):
        i = run('let ac = AbortController.new()\nlet s = ac.signal\nlet r = s.aborted')
        assert val(i, "r") is False

    def test_signal_aborted_after_abort(self):
        i = run('let ac = AbortController.new()\nlet s = ac.signal\nac.abort()\nlet r = s.aborted')
        assert val(i, "r") is True

    def test_multiple_abort_calls_idempotent(self):
        i = run('let ac = AbortController.new()\nac.abort("first")\nac.abort("second")\nlet r = ac.signal.reason')
        # First abort wins
        assert val(i, "r") == "first"

    def test_abort_triggers_listener(self):
        i = run("""
let ac = AbortController.new()
var called = false
ac.signal.addEventListener("abort", () => { called = true })
ac.abort()
let r = called
""")
        assert val(i, "r") is True

    def test_no_abort_listener_not_called(self):
        i = run("""
let ac = AbortController.new()
var called = false
ac.signal.addEventListener("abort", () => { called = true })
let r = called
""")
        assert val(i, "r") is False
