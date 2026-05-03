"""Phase 16 feature tests.

Covers:
  - Nested ternary (right-associative)
  - **= exponentiation compound assignment
  - string.replace(regex, str|fn) and string.split(regex)
  - string.replaceAll(str|fn, fn)
  - Error / TypeError / RangeError / SyntaxError / ReferenceError globals
  - for [i, x] of — destructured loop variable
  - for var i = 0; i < n; i++ — C-style for loop
  - class static field / static fn using `static` keyword
  - Symbol.new()
  - array.lastIndexOf
  - Object.defineProperty / defineProperties / getOwnPropertyDescriptor
  - list.product() / list.avg() / list.mean()
  - Multi-level super (3+ levels)
  - JSON.stringify(val, replacer, indent) — 3-arg form
  - [a, b] = [b, a] — array destructuring assignment
  - fn first([head, ...rest]) — array destructuring in function params
  - Semicolon as statement separator
"""

import pytest
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.interpreter import Interpreter


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


def val(src: str, name: str = "v"):
    return run(src).globals.get(name)


def err(src: str) -> str:
    """Return the error message from running src, or raise if no error."""
    try:
        run(src)
        raise AssertionError("Expected an error but none was raised")
    except Exception as e:
        return str(e)


# ---------------------------------------------------------------------------
# Nested ternary
# ---------------------------------------------------------------------------

class TestNestedTernary:
    def test_nested_ternary_first_branch(self):
        assert val('let x = 1\nlet v = x == 1 ? "one" : x == 2 ? "two" : "other"') == "one"

    def test_nested_ternary_second_branch(self):
        assert val('let x = 2\nlet v = x == 1 ? "one" : x == 2 ? "two" : "other"') == "two"

    def test_nested_ternary_else_branch(self):
        assert val('let x = 3\nlet v = x == 1 ? "one" : x == 2 ? "two" : "other"') == "other"

    def test_nested_ternary_three_levels(self):
        assert val('let x = 3\nlet v = x == 1 ? "a" : x == 2 ? "b" : x == 3 ? "c" : "d"') == "c"

    def test_nested_ternary_false_all(self):
        assert val('let x = 99\nlet v = x == 1 ? "a" : x == 2 ? "b" : x == 3 ? "c" : "d"') == "d"

    def test_ternary_with_expr(self):
        assert val('let v = true ? 1 + 2 : 10') == 3

    def test_ternary_inside_ternary_complex(self):
        # (a ? b : c) where b itself contains a ternary
        assert val('let a = true\nlet b = false\nlet v = a ? (b ? "ab" : "anotb") : "nota"') == "anotb"


# ---------------------------------------------------------------------------
# **= exponentiation compound assignment
# ---------------------------------------------------------------------------

class TestExponentiationAssign:
    def test_power_assign_basic(self):
        assert val('var x = 2\nx **= 10\nlet v = x') == 1024

    def test_power_assign_square(self):
        assert val('var x = 5\nx **= 2\nlet v = x') == 25

    def test_power_assign_cube(self):
        assert val('var x = 3\nx **= 3\nlet v = x') == 27

    def test_power_assign_zero_exp(self):
        assert val('var x = 99\nx **= 0\nlet v = x') == 1

    def test_power_assign_one_exp(self):
        assert val('var x = 7\nx **= 1\nlet v = x') == 7

    def test_power_assign_float(self):
        result = val('var x = 9.0\nx **= 0.5\nlet v = x')
        assert abs(result - 3.0) < 1e-10


# ---------------------------------------------------------------------------
# string.replace / string.replaceAll with regex / function
# ---------------------------------------------------------------------------

class TestStringReplace:
    def test_replace_string_string(self):
        assert val('let v = "hello world".replace("world", "spry")') == "hello spry"

    def test_replace_regex_string(self):
        assert val('let v = "hello world".replace(/world/, "spry")') == "hello spry"

    def test_replace_string_fn(self):
        assert val('let v = "hello world".replace("world", s => s.toUpperCase())') == "hello WORLD"

    def test_replace_regex_fn(self):
        assert val('let v = "hello world".replace(/world/, s => s.toUpperCase())') == "hello WORLD"

    def test_replace_only_first_occurrence(self):
        assert val('let v = "aaa".replace("a", "b")') == "baa"

    def test_replace_regex_global_replaces_all(self):
        # regex with global flag replaces all
        assert val('let v = "aaa".replace(/a/g, "b")') == "bbb"

    def test_replaceAll_string_string(self):
        assert val('let v = "aabbcc".replaceAll("b", "x")') == "aaxxcc"

    def test_replaceAll_string_fn(self):
        assert val('let v = "aaa".replaceAll("a", s => "b")') == "bbb"

    def test_replaceAll_no_match(self):
        assert val('let v = "hello".replaceAll("x", "y")') == "hello"

    def test_replace_no_match(self):
        assert val('let v = "hello".replace("xyz", "abc")') == "hello"


# ---------------------------------------------------------------------------
# string.split with regex
# ---------------------------------------------------------------------------

class TestStringSplitRegex:
    def test_split_regex_whitespace(self):
        assert val('let v = "one two three".split(/ +/)') == ["one", "two", "three"]

    def test_split_regex_multiple_spaces(self):
        assert val('let v = "a  b   c".split(/ +/)') == ["a", "b", "c"]

    def test_split_regex_comma(self):
        assert val('let v = "a,b,c".split(/,/)') == ["a", "b", "c"]

    def test_split_string_still_works(self):
        assert val('let v = "a,b,c".split(",")') == ["a", "b", "c"]

    def test_split_regex_limit(self):
        # limit arg
        assert val('let v = "a b c d".split(/ /, 2)') == ["a", "b"]


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class TestErrorTypes:
    def test_error_new_message(self):
        assert val('let e = Error.new("test")\nlet v = e.message') == "test"

    def test_error_new_name(self):
        assert val('let e = Error.new("test")\nlet v = e.name') == "Error"

    def test_type_error_new(self):
        assert val('let e = TypeError.new("bad type")\nlet v = e.name') == "TypeError"

    def test_range_error_new(self):
        assert val('let e = RangeError.new("out of range")\nlet v = e.name') == "RangeError"

    def test_syntax_error_new(self):
        assert val('let e = SyntaxError.new("bad syntax")\nlet v = e.name') == "SyntaxError"

    def test_reference_error_new(self):
        assert val('let e = ReferenceError.new("undefined")\nlet v = e.name') == "ReferenceError"

    def test_error_callable(self):
        # Error(msg) also works
        assert val('let e = Error("callable")\nlet v = e.message') == "callable"

    def test_error_throw_catch(self):
        src = '''
var v = null
try {
  throw TypeError.new("bad")
} catch e {
  v = e.message
}
'''
        assert val(src) == "bad"

    def test_error_instanceof_check(self):
        # Can check that it has the right name
        assert val('let e = RangeError.new("x")\nlet v = e.name == "RangeError"') is True

    def test_error_stack(self):
        result = val('let e = Error.new("msg")\nlet v = e.stack')
        assert "Error: msg" in result


# ---------------------------------------------------------------------------
# for [i, x] of — destructured loop var
# ---------------------------------------------------------------------------

class TestDestructuredForOf:
    def test_for_entries_sum(self):
        assert val('var v = 0\nfor [i, x] of [10, 20, 30].entries() { v += x }') == 60

    def test_for_entries_indices(self):
        assert val('var v = 0\nfor [i, x] of [10, 20, 30].entries() { v += i }') == 3

    def test_for_pair_list(self):
        assert val('var v = 0\nfor [a, b] of [[1, 10], [2, 20]] { v += b }') == 30

    def test_for_destructure_in(self):
        assert val('var v = 0\nfor [a, b] in [[1, 10], [2, 20]] { v += a }') == 3

    def test_for_triple_destructure(self):
        assert val('var v = 0\nfor [a, b, c] of [[1, 2, 3], [4, 5, 6]] { v += c }') == 9


# ---------------------------------------------------------------------------
# C-style for loop
# ---------------------------------------------------------------------------

class TestCStyleFor:
    def test_basic_sum(self):
        assert val('var v = 0\nfor var i = 0; i < 5; i++ { v += i }') == 10

    def test_count(self):
        assert val('var v = 0\nfor var i = 0; i < 10; i++ { v++ }') == 10

    def test_last_value(self):
        assert val('var v = 0\nfor var i = 0; i < 5; i++ { v = i }') == 4

    def test_product(self):
        assert val('var v = 1\nfor var i = 1; i <= 5; i++ { v *= i }') == 120

    def test_step_2(self):
        assert val('var v = 0\nfor var i = 0; i < 10; i += 2 { v++ }') == 5

    def test_reverse(self):
        assert val('var v = 0\nfor var i = 5; i > 0; i-- { v += i }') == 15

    def test_break_in_cstyle(self):
        assert val('var v = 0\nfor var i = 0; i < 100; i++ { if i == 5 { break }\nv++ }') == 5


# ---------------------------------------------------------------------------
# class static keyword
# ---------------------------------------------------------------------------

class TestClassStaticKeyword:
    def test_static_field(self):
        assert val('class Config { static version = "1.0" }\nlet v = Config.version') == "1.0"

    def test_static_field_number(self):
        assert val('class Math2 { static PI = 3.14159 }\nlet v = Math2.PI') == pytest.approx(3.14159)

    def test_static_method(self):
        assert val('class M { static fn square(x) { return x * x } }\nlet v = M.square(5)') == 25

    def test_static_method_with_field(self):
        src = '''
class Counter {
  static count = 0
  static fn increment() { return 1 }
}
let v = Counter.count
'''
        assert val(src) == 0

    def test_let_field_still_works(self):
        assert val('class Cfg { let version = "2.0" }\nlet v = Cfg.version') == "2.0"


# ---------------------------------------------------------------------------
# Symbol.new()
# ---------------------------------------------------------------------------

class TestSymbolNew:
    def test_symbol_new_description(self):
        assert val('let s = Symbol.new("test")\nlet v = s.description') == "test"

    def test_symbol_callable(self):
        assert val('let s = Symbol("test2")\nlet v = s.description') == "test2"

    def test_symbol_unique(self):
        assert val('let a = Symbol.new("x")\nlet b = Symbol.new("x")\nlet v = a != b') is True

    def test_symbol_self_equal(self):
        assert val('let a = Symbol.new("x")\nlet v = a == a') is True

    def test_symbol_empty_description(self):
        assert val('let s = Symbol.new()\nlet v = s.description') == ""


# ---------------------------------------------------------------------------
# array.lastIndexOf
# ---------------------------------------------------------------------------

class TestArrayLastIndexOf:
    def test_last_index_of_basic(self):
        assert val('let v = [1, 2, 1, 3].lastIndexOf(1)') == 2

    def test_last_index_of_first(self):
        assert val('let v = [1, 2, 3].lastIndexOf(1)') == 0

    def test_last_index_of_not_found(self):
        assert val('let v = [1, 2, 3].lastIndexOf(99)') == -1

    def test_last_index_of_last(self):
        assert val('let v = [1, 2, 3, 2].lastIndexOf(2)') == 3

    def test_last_index_of_string(self):
        assert val('let v = ["a", "b", "a"].lastIndexOf("a")') == 2


# ---------------------------------------------------------------------------
# Object.defineProperty / defineProperties / getOwnPropertyDescriptor
# ---------------------------------------------------------------------------

class TestObjectDefineProperty:
    def test_define_property_sets_value(self):
        assert val('let obj = {}\nObject.defineProperty(obj, "x", {value: 42})\nlet v = obj.x') == 42

    def test_define_property_returns_obj(self):
        assert val('let obj = {}\nlet v = Object.defineProperty(obj, "y", {value: 99})') == {"y": 99}

    def test_define_properties(self):
        assert val('let obj = {}\nObject.defineProperties(obj, {a: {value: 1}, b: {value: 2}})\nlet v = obj.a + obj.b') == 3

    def test_get_own_property_descriptor(self):
        src = 'let obj = {x: 42}\nlet desc = Object.getOwnPropertyDescriptor(obj, "x")\nlet v = desc.value'
        assert val(src) == 42

    def test_get_own_property_descriptor_missing(self):
        assert val('let v = Object.getOwnPropertyDescriptor({}, "x")') is None


# ---------------------------------------------------------------------------
# list.product / list.avg / list.mean
# ---------------------------------------------------------------------------

class TestListAggregates:
    def test_product_basic(self):
        assert val('let v = [1, 2, 3, 4].product()') == 24

    def test_product_single(self):
        assert val('let v = [7].product()') == 7

    def test_product_with_zero(self):
        assert val('let v = [1, 2, 0, 4].product()') == 0

    def test_avg_basic(self):
        assert val('let v = [1, 2, 3, 4, 5].avg()') == pytest.approx(3.0)

    def test_avg_two(self):
        assert val('let v = [10, 20].avg()') == pytest.approx(15.0)

    def test_mean_alias(self):
        assert val('let v = [1, 2, 3].mean()') == pytest.approx(2.0)

    def test_average_alias(self):
        assert val('let v = [1, 2, 3].average()') == pytest.approx(2.0)

    def test_product_all_ones(self):
        assert val('let v = [1, 1, 1, 1].product()') == 1


# ---------------------------------------------------------------------------
# Multi-level super
# ---------------------------------------------------------------------------

class TestMultiLevelSuper:
    def test_three_level_super(self):
        src = '''
class A {
  fn greet() { return "A" }
}
class B extends A {
  fn greet() { return super.greet() + "B" }
}
class C extends B {
  fn greet() { return super.greet() + "C" }
}
let c = C.new()
let v = c.greet()
'''
        assert val(src) == "ABC"

    def test_four_level_super(self):
        src = '''
class A { fn g() { return "A" } }
class B extends A { fn g() { return super.g() + "B" } }
class C extends B { fn g() { return super.g() + "C" } }
class D extends C { fn g() { return super.g() + "D" } }
let d = D.new()
let v = d.g()
'''
        assert val(src) == "ABCD"

    def test_super_field_access(self):
        src = '''
class Animal {
  fn sound() { return "..." }
}
class Dog extends Animal {
  fn sound() { return "woof" }
  fn also_parent() { return super.sound() }
}
let d = Dog.new()
let v = d.also_parent()
'''
        assert val(src) == "..."

    def test_super_in_init(self):
        src = '''
class A {
  var x = 0
  fn init(x) { self.x = x }
}
class B extends A {
  fn init(x) { super(x * 2) }
}
let b = B.new(5)
let v = b.x
'''
        assert val(src) == 10


# ---------------------------------------------------------------------------
# JSON.stringify with 3 args (replacer, indent)
# ---------------------------------------------------------------------------

class TestJsonStringify3Args:
    def test_stringify_with_null_replacer_indent(self):
        result = val('let v = JSON.stringify({a: 1}, null, 2)')
        assert '"a": 1' in result
        assert "\n" in result  # indented

    def test_stringify_with_indent_4(self):
        result = val('let v = JSON.stringify({x: 42}, null, 4)')
        assert "    " in result  # 4 spaces

    def test_stringify_no_indent(self):
        result = val('let v = JSON.stringify({a: 1})')
        assert result == '{"a":1}'

    def test_lowercase_json_stringify_3args(self):
        result = val('let v = json.stringify({a: 1}, null, 2)')
        assert '"a": 1' in result

    def test_stringify_array(self):
        result = val('let v = JSON.stringify([1, 2, 3], null, 2)')
        assert "1" in result and "2" in result and "3" in result


# ---------------------------------------------------------------------------
# [a, b] = [b, a] — array destructuring assignment
# ---------------------------------------------------------------------------

class TestArrayDestructureAssign:
    def test_swap_basic(self):
        assert val('var a = 1; var b = 2; [a, b] = [b, a]; let v = a') == 2

    def test_swap_b_value(self):
        assert val('var a = 1; var b = 2; [a, b] = [b, a]; let v = b') == 1

    def test_three_way_swap(self):
        assert val('var a = 1; var b = 2; var c = 3; [a, b, c] = [c, a, b]; let v = a') == 3

    def test_assign_from_list(self):
        assert val('var x = 0; var y = 0; [x, y] = [10, 20]; let v = x + y') == 30

    def test_rest_in_destructure_assign(self):
        assert val('var a = 0; var rest = []; [a, ...rest] = [1, 2, 3, 4]; let v = rest') == [2, 3, 4]

    def test_shorter_rhs_gives_null(self):
        assert val('var a = 0; var b = 99; [a, b] = [42]; let v = b') is None


# ---------------------------------------------------------------------------
# C-style for loop
# ---------------------------------------------------------------------------

class TestForCStyle:
    def test_for_cstyle_sum(self):
        assert val('var v = 0\nfor var i = 0; i < 5; i++ { v += i }') == 10

    def test_for_cstyle_count_to_10(self):
        assert val('var v = 0\nfor var i = 0; i < 10; i++ { v++ }') == 10

    def test_for_cstyle_collect(self):
        assert val('var v = []\nfor var i = 0; i < 3; i++ { v.push(i) }') == [0, 1, 2]

    def test_for_cstyle_step_by_2(self):
        assert val('var v = 0\nfor var i = 0; i < 10; i += 2 { v++ }') == 5

    def test_for_cstyle_reverse(self):
        assert val('var v = 0\nfor var i = 5; i > 0; i-- { v += i }') == 15

    def test_for_cstyle_factorial(self):
        assert val('var v = 1\nfor var i = 1; i <= 5; i++ { v *= i }') == 120

    def test_for_cstyle_break(self):
        assert val('var v = 0\nfor var i = 0; i < 100; i++ { if i == 5 { break }\nv++ }') == 5


# ---------------------------------------------------------------------------
# fn ([head, ...rest]) — array destructuring in fn params
# ---------------------------------------------------------------------------

class TestFnArrayDestructParam:
    def test_head_extraction(self):
        assert val('fn first([head, ...rest]) { return head }\nlet v = first([10, 20, 30])') == 10

    def test_rest_extraction(self):
        assert val('fn tail([head, ...rest]) { return rest }\nlet v = tail([10, 20, 30])') == [20, 30]

    def test_two_destructured(self):
        assert val('fn pair([a, b]) { return a + b }\nlet v = pair([3, 4])') == 7

    def test_empty_rest(self):
        assert val('fn first([head, ...rest]) { return rest }\nlet v = first([42])') == []

    def test_nested_with_normal(self):
        assert val('fn fn2([a, b], c) { return a + b + c }\nlet v = fn2([1, 2], 3)') == 6


# ---------------------------------------------------------------------------
# Semicolon as statement separator
# ---------------------------------------------------------------------------

class TestSemicolonSeparator:
    def test_two_stmts(self):
        assert val('var a = 1; var b = 2; let v = a + b') == 3

    def test_three_stmts(self):
        assert val('var a = 1; var b = 2; var c = 3; let v = a + b + c') == 6

    def test_mix_semicolons_and_newlines(self):
        assert val('var a = 1; var b = 2\nlet v = a + b') == 3

    def test_semicolon_after_block(self):
        assert val('var v = 0; if true { v = 42 }; let x = v\nlet v2 = x', name="v2") == 42

    def test_trailing_semicolon(self):
        assert val('let v = 42;') == 42
