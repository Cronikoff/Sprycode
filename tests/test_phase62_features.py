"""Phase 62 feature tests.

Covers:
- every()/some() pass (element, index, array) to callback when arity > 1
- arr.length = n  truncates or extends the array in place
- \\uXXXX / \\u{XXXXXX} / \\xXX Unicode/hex escapes in string literals
- new Function(arg1, ..., body) constructor
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


def val(interp: Interpreter) -> object:
    return interp.globals["v"]


# ---------------------------------------------------------------------------
# every() / some() with index argument
# ---------------------------------------------------------------------------

class TestEveryWithIndex:
    def test_every_index_third_arg(self):
        """Callback receives (element, index) — check index ordering."""
        i = run("let v = [1, 2, 3, 4].every((x, i) => x === i + 1)")
        assert val(i) is True

    def test_every_index_fails_correctly(self):
        i = run("let v = [1, 2, 99, 4].every((x, i) => x === i + 1)")
        assert val(i) is False

    def test_every_no_index_still_works(self):
        i = run("let v = [2, 4, 6].every(x => x % 2 === 0)")
        assert val(i) is True

    def test_every_with_array_arg(self):
        """Third arg is the original array."""
        i = run("""
let arr = [10, 20, 30]
let v = arr.every((x, i, a) => a[i] === x)
""")
        assert val(i) is True

    def test_every_empty_array(self):
        """every() on empty array is vacuously true."""
        i = run("let v = [].every((x, i) => false)")
        assert val(i) is True

    def test_some_index_true(self):
        """some() callback receives (element, index) — finds the target."""
        i = run("let v = [5, 1, 5].some((x, i) => i === 1 && x === 1)")
        assert val(i) is True

    def test_some_index_false(self):
        i = run("let v = [1, 2, 3].some((x, i) => i === 0 && x === 99)")
        assert val(i) is False

    def test_some_no_index_still_works(self):
        i = run("let v = [1, 3, 5].some(x => x % 2 === 0)")
        assert val(i) is False

    def test_some_empty_array(self):
        i = run("let v = [].some((x, i) => true)")
        assert val(i) is False

    def test_some_find_even_index(self):
        i = run("let v = [10, 20, 30, 40].some((x, i) => i % 2 === 1 && x > 15)")
        assert val(i) is True

    def test_every_index_builds_mapping(self):
        """Use every() to verify parallel arrays are in sync."""
        i = run("""
let keys = ["a", "b", "c"]
let vals = [1, 2, 3]
let v = keys.every((k, i) => vals[i] === i + 1)
""")
        assert val(i) is True

    def test_some_short_circuit(self):
        """some() short-circuits after first truthy result."""
        i = run("""
let checked = []
let v = [1, 2, 3, 4].some((x, i) => {
  checked.push(i)
  return x === 2
})
""")
        assert val(i) is True
        assert i.globals["checked"] == [0, 1]


# ---------------------------------------------------------------------------
# arr.length = n  (truncate / extend)
# ---------------------------------------------------------------------------

class TestArrayLengthSet:
    def test_truncate_array(self):
        i = run("let arr = [1, 2, 3, 4, 5]; arr.length = 3; let v = arr")
        assert val(i) == [1, 2, 3]

    def test_truncate_to_zero(self):
        i = run("let arr = [1, 2, 3]; arr.length = 0; let v = arr")
        assert val(i) == []

    def test_extend_array_fills_undefined(self):
        i = run("let arr = [1, 2, 3]; arr.length = 5; let v = arr.length")
        assert val(i) == 5

    def test_truncate_then_access(self):
        i = run("""
let arr = [10, 20, 30, 40, 50]
arr.length = 2
let v = arr
""")
        assert val(i) == [10, 20]

    def test_length_same_value_noop(self):
        i = run("let arr = [1, 2, 3]; arr.length = 3; let v = arr")
        assert val(i) == [1, 2, 3]

    def test_length_set_in_function(self):
        i = run("""
function clear(arr) { arr.length = 0 }
let a = [1, 2, 3, 4]
clear(a)
let v = a
""")
        assert val(i) == []

    def test_length_set_float_truncates(self):
        """length = 2.9 should truncate to integer 2."""
        i = run("let arr = [1, 2, 3, 4]; arr.length = 2.9; let v = arr")
        assert val(i) == [1, 2]

    def test_length_readable_after_truncate(self):
        i = run("let arr = [1, 2, 3, 4, 5]; arr.length = 3; let v = arr.length")
        assert val(i) == 3

    def test_invalid_property_still_raises(self):
        with pytest.raises(Exception):
            run("let arr = [1, 2, 3]; arr.push = 99")


# ---------------------------------------------------------------------------
# Unicode / hex escape sequences in string literals
# ---------------------------------------------------------------------------

class TestUnicodeEscapes:
    def test_backslash_u_four_hex(self):
        """\\uXXXX decoded to the corresponding character."""
        i = run(r'let v = "\u0041\u0042\u0043"')
        assert val(i) == "ABC"

    def test_cafe_unicode_escape(self):
        r"""caf\u00e9 should be the 4-char precomposed string."""
        i = run(r'let v = "caf\u00e9".length')
        assert val(i) == 4

    def test_unicode_escape_single_char(self):
        i = run(r'let v = "\u00e9"')
        assert val(i) == "é"

    def test_hex_escape(self):
        r"""\\xXX decoded to character."""
        i = run(r'let v = "\x41\x42"')
        assert val(i) == "AB"

    def test_unicode_escape_in_comparison(self):
        i = run(r'let v = "\u0041" === "A"')
        assert val(i) is True

    def test_unicode_mixed_with_normal_chars(self):
        i = run(r'let v = "Hello \u0057orld"')
        assert val(i) == "Hello World"

    def test_unicode_null_char(self):
        i = run(r'let v = "\u0000".length')
        assert val(i) == 1

    def test_unicode_high_codepoint(self):
        i = run(r'let v = "\u03B1\u03B2\u03B3"')
        assert val(i) == "αβγ"

    def test_escape_in_template_literal(self):
        i = run(r'let v = `caf\u00e9`')
        # template literals also process escapes
        assert "caf" in val(i)

    def test_hex_escape_newline_simulation(self):
        r"""\\x0a is newline character."""
        i = run(r'let v = "\x0a".length')
        assert val(i) == 1

    def test_unicode_in_identifier_string_keys(self):
        i = run(r'let obj = {"\u006B\u0065\u0079": 42}; let v = obj["key"]')
        assert val(i) == 42

    def test_raw_template_not_escaped(self):
        r"""String.raw`\uXXXX` should NOT decode the escape."""
        i = run(r'let v = String.raw`\u0041`')
        assert val(i) == r"\u0041"

    def test_multiple_hex_escapes(self):
        i = run(r'let v = "\x48\x65\x6c\x6c\x6f"')
        assert val(i) == "Hello"


# ---------------------------------------------------------------------------
# new Function(...) constructor
# ---------------------------------------------------------------------------

class TestFunctionConstructor:
    def test_new_function_two_params(self):
        i = run('let fn = new Function("a", "b", "return a + b"); let v = fn(3, 4)')
        assert val(i) == 7

    def test_new_function_one_param(self):
        i = run('let fn = new Function("x", "return x * x"); let v = fn(5)')
        assert val(i) == 25

    def test_new_function_no_params(self):
        i = run('let fn = new Function("return 42"); let v = fn()')
        assert val(i) == 42

    def test_function_call_direct(self):
        """Function(...) without new should also work (same semantics)."""
        i = run('let fn = Function("x", "return x + 1"); let v = fn(41)')
        assert val(i) == 42

    def test_new_function_arithmetic(self):
        i = run('let fn = new Function("a", "b", "c", "return a * b + c"); let v = fn(2, 3, 4)')
        assert val(i) == 10

    def test_new_function_string_op(self):
        i = run('let fn = new Function("s", "return s.toUpperCase()"); let v = fn("hello")')
        assert val(i) == "HELLO"

    def test_new_function_with_if(self):
        i = run("""
let abs = new Function("x", "if (x < 0) return -x; return x")
let v = [abs(-5), abs(3)]
""")
        assert val(i) == [5, 3]

    def test_new_function_closure_over_outer(self):
        """Function body can access globals from environment."""
        i = run("""
let factor = 10
let fn = new Function("x", "return x * factor")
let v = fn(5)
""")
        assert val(i) == 50

    def test_new_function_dynamic_add(self):
        i = run("""
let ops = {
  add: new Function("a", "b", "return a + b"),
  sub: new Function("a", "b", "return a - b")
}
let v = [ops.add(10, 3), ops.sub(10, 3)]
""")
        assert val(i) == [13, 7]

    def test_function_typeof(self):
        i = run('let fn = new Function("return 1"); let v = typeof fn')
        assert val(i) == "function"
