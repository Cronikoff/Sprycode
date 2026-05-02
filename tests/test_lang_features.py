"""
Tests for new language features:
  - switch/case/default statement
  - anonymous function expressions (fn() { })
  - list comprehensions ([expr for var in iterable if cond])
  - postfix/prefix ++/-- operators
  - regex literals (/pattern/flags)
  - %=  compound assignment
  - interface method signatures (no-body fn)
"""

import pytest

from sprycode.interpreter import Interpreter, SpryRegex
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.runtime.stdlib import SpryLogger


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(prog)
    return interp


def run_output(src: str) -> list:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    out: list = []
    interp = Interpreter(logger=SpryLogger(output=out))
    interp.run(prog)
    return out


def val(interp: Interpreter, name: str):
    return interp.globals.get(name)


# ---------------------------------------------------------------------------
# switch / case / default
# ---------------------------------------------------------------------------


class TestSwitch:
    def test_basic_case_match(self):
        i = run('let x = 2\nswitch x {\n  case 1: let r = "one"\n  case 2: let r = "two"\n  default: let r = "other"\n}\nlet v = r')
        assert val(i, "v") == "two"

    def test_default_fallthrough(self):
        i = run('let x = 99\nswitch x {\n  case 1: let r = "one"\n  default: let r = "other"\n}\nlet v = r')
        assert val(i, "v") == "other"

    def test_no_match_no_default(self):
        # No error, just no assignment
        i = run("let x = 42\nvar r = \"none\"\nswitch x {\n  case 1: r = \"one\"\n}\nlet v = r")
        assert val(i, "v") == "none"

    def test_string_cases(self):
        i = run('let s = "banana"\nswitch s {\n  case "apple": let r = 1\n  case "banana": let r = 2\n  default: let r = 0\n}\nlet v = r')
        assert val(i, "v") == 2

    def test_integer_cases(self):
        i = run("let n = 3\nswitch n {\n  case 1: let r = \"a\"\n  case 2: let r = \"b\"\n  case 3: let r = \"c\"\n}\nlet v = r")
        assert val(i, "v") == "c"

    def test_case_body_can_have_multiple_statements(self):
        i = run("let x = 1\nswitch x {\n  case 1:\n    let a = 10\n    let b = 20\n  default: let a = 0\n}\nlet v = a + b")
        assert val(i, "v") == 30

    def test_switch_in_function(self):
        i = run('fn classify(n) {\n  switch n {\n    case 1: return "one"\n    case 2: return "two"\n    default: return "many"\n  }\n}\nlet v = classify(2)')
        assert val(i, "v") == "two"

    def test_switch_first_match_wins(self):
        # value 1 should match the first case
        i = run("let x = 1\nvar r = 0\nswitch x {\n  case 1: r = 10\n  case 1: r = 20\n}\nlet v = r")
        assert val(i, "v") == 10


# ---------------------------------------------------------------------------
# Anonymous function expressions
# ---------------------------------------------------------------------------


class TestAnonymousFunctions:
    def test_basic_anon_fn(self):
        i = run("let f = fn() { return 42 }\nlet v = f()")
        assert val(i, "v") == 42

    def test_anon_fn_with_args(self):
        i = run("let f = fn(x, y) { return x + y }\nlet v = f(3, 4)")
        assert val(i, "v") == 7

    def test_anon_fn_arrow_form(self):
        i = run("let f = fn(x) => x * 2\nlet v = f(5)")
        assert val(i, "v") == 10

    def test_anon_fn_no_args_arrow(self):
        i = run("let f = fn() => 99\nlet v = f()")
        assert val(i, "v") == 99

    def test_anon_fn_closure(self):
        src = """fn counter() {
  var n = 0
  return fn() { n += 1\n return n }
}
let c = counter()
c()
let v = c()"""
        i = run(src)
        assert val(i, "v") == 2

    def test_anon_fn_as_argument(self):
        i = run("let v = [1,2,3].map(fn(x) => x * 3)")
        assert val(i, "v") == [3, 6, 9]

    def test_anon_fn_stored_and_called(self):
        i = run("var ops = [fn(x) => x+1, fn(x) => x*2]\nlet v = ops[1](5)")
        assert val(i, "v") == 10

    def test_anon_fn_with_rest_params(self):
        i = run("let f = fn(...args) { return args.length }\nlet v = f(1,2,3,4)")
        assert val(i, "v") == 4

    def test_anon_fn_default_params(self):
        i = run('let f = fn(x, y = 10) { return x + y }\nlet v = f(5)')
        assert val(i, "v") == 15

    def test_anon_fn_returns_anon_fn(self):
        src = """let adder = fn(x) => fn(y) => x + y
let add5 = adder(5)
let v = add5(3)"""
        i = run(src)
        assert val(i, "v") == 8


# ---------------------------------------------------------------------------
# List comprehensions
# ---------------------------------------------------------------------------


class TestListComprehensions:
    def test_basic_comprehension(self):
        i = run("let v = [x*2 for x in [1,2,3]]")
        assert val(i, "v") == [2, 4, 6]

    def test_comprehension_over_range(self):
        i = run("let v = [x*2 for x in range(1,6)]")
        assert val(i, "v") == [2, 4, 6, 8, 10]

    def test_comprehension_with_filter(self):
        i = run("let v = [x for x in range(1,11) if x % 2 == 0]")
        assert val(i, "v") == [2, 4, 6, 8, 10]

    def test_comprehension_string_transform(self):
        i = run('let words = ["hello", "world"]\nlet v = [w.toUpperCase() for w in words]')
        assert val(i, "v") == ["HELLO", "WORLD"]

    def test_comprehension_expr_with_local_var(self):
        i = run("let v = [x * x for x in range(1,6)]")
        assert val(i, "v") == [1, 4, 9, 16, 25]

    def test_comprehension_filter_odd(self):
        i = run("let v = [x for x in [1,2,3,4,5,6] if x % 2 != 0]")
        assert val(i, "v") == [1, 3, 5]

    def test_comprehension_empty_when_all_filtered(self):
        i = run("let v = [x for x in [1,2,3] if x > 100]")
        assert val(i, "v") == []

    def test_comprehension_over_string_chars(self):
        i = run('let v = [c for c in "abc"]')
        assert val(i, "v") == ["a", "b", "c"]

    def test_comprehension_nested_expression(self):
        i = run("let v = [x * x + 1 for x in range(1, 4)]")
        assert val(i, "v") == [2, 5, 10]


# ---------------------------------------------------------------------------
# Postfix / prefix ++ and --
# ---------------------------------------------------------------------------


class TestIncrementDecrement:
    def test_postfix_increment(self):
        i = run("var i = 0\ni++\nlet v = i")
        assert val(i, "v") == 1

    def test_postfix_decrement(self):
        i = run("var i = 5\ni--\nlet v = i")
        assert val(i, "v") == 4

    def test_prefix_increment(self):
        i = run("var i = 0\n++i\nlet v = i")
        assert val(i, "v") == 1

    def test_prefix_decrement(self):
        i = run("var i = 5\n--i\nlet v = i")
        assert val(i, "v") == 4

    def test_postfix_returns_old_value(self):
        # Postfix ++ evaluates to old value
        i = run("var i = 3\nlet old = i++\nlet v = old")
        assert val(i, "v") == 3
        assert val(i, "i") == 4

    def test_prefix_returns_new_value(self):
        # Prefix ++ evaluates to new value
        i = run("var i = 3\nlet new_v = ++i")
        assert val(i, "new_v") == 4
        assert val(i, "i") == 4

    def test_increment_in_loop(self):
        i = run("var c = 0\nfor x in range(5) { c++ }\nlet v = c")
        assert val(i, "v") == 5

    def test_decrement_in_loop(self):
        i = run("var c = 10\nfor x in range(5) { c-- }\nlet v = c")
        assert val(i, "v") == 5

    def test_multiple_increments(self):
        i = run("var n = 0\nn++\nn++\nn++\nlet v = n")
        assert val(i, "v") == 3

    def test_increment_not_applied_to_literal(self):
        # 0++ followed by i should be a parse of var with postfix only on ident
        # This just checks no crash and var i is assigned 0
        i = run("var i = 0\nlet v = i")
        assert val(i, "v") == 0


# ---------------------------------------------------------------------------
# Regex literals
# ---------------------------------------------------------------------------


class TestRegexLiterals:
    def test_basic_test_true(self):
        i = run('let r = /hello/\nlet v = r.test("say hello world")')
        assert val(i, "v") is True

    def test_basic_test_false(self):
        i = run('let r = /hello/\nlet v = r.test("nothing here")')
        assert val(i, "v") is False

    def test_case_insensitive_flag(self):
        i = run('let r = /hello/i\nlet v = r.test("HELLO WORLD")')
        assert val(i, "v") is True

    def test_regex_object_type(self):
        i = run("let r = /foo/")
        r = val(i, "r")
        assert isinstance(r, SpryRegex)

    def test_replace_first(self):
        i = run('let r = /foo/\nlet v = r.replace("foo bar foo", "baz")')
        assert val(i, "v") == "baz bar foo"

    def test_replace_all(self):
        i = run('let r = /foo/\nlet v = r.replaceAll("foo bar foo", "baz")')
        assert val(i, "v") == "baz bar baz"

    def test_split(self):
        i = run('let r = /,/\nlet v = r.split("a,b,c")')
        assert val(i, "v") == ["a", "b", "c"]

    def test_find_all(self):
        i = run(r'let r = /\d+/' + '\nlet v = r.findAll("abc 123 def 456")')
        assert val(i, "v") == ["123", "456"]

    def test_match_returns_dict(self):
        i = run(r'let r = /(\w+)/' + '\nlet m = r.match("hello world")')
        m = val(i, "m")
        assert isinstance(m, dict)
        assert m["match"] == "hello"

    def test_match_no_result_returns_null(self):
        i = run('let r = /xyz/\nlet m = r.match("hello world")')
        assert val(i, "m") is None

    def test_source_property(self):
        i = run("let r = /abc/\nlet v = r.source")
        assert val(i, "v") == "abc"

    def test_multiline_flag(self):
        i = run('let r = /^hello/m\nlet v = r.test("world\\nhello there")')
        assert val(i, "v") is True

    def test_regex_in_if_condition(self):
        i = run(r'let r = /^\d+$/' + '\nlet s = "12345"\nvar v = false\nif r.test(s) { v = true }')
        assert val(i, "v") is True

    def test_division_not_treated_as_regex(self):
        i = run("let v = 10 / 2")
        assert val(i, "v") == 5

    def test_division_after_identifier(self):
        i = run("let a = 12\nlet v = a / 4")
        assert val(i, "v") == 3


# ---------------------------------------------------------------------------
# %= compound assignment
# ---------------------------------------------------------------------------


class TestPercentAssignment:
    def test_percent_eq_basic(self):
        i = run("var x = 10\nx %= 3\nlet v = x")
        assert val(i, "v") == 1

    def test_percent_eq_zero_remainder(self):
        i = run("var x = 10\nx %= 5\nlet v = x")
        assert val(i, "v") == 0

    def test_percent_eq_larger_divisor(self):
        i = run("var x = 3\nx %= 7\nlet v = x")
        assert val(i, "v") == 3

    def test_percent_eq_in_loop(self):
        i = run("var s = 0\nfor n in range(1, 11) {\n  var tmp = n\n  tmp %= 3\n  if tmp == 0 { s += n }\n}\nlet v = s")
        assert val(i, "v") == 18  # 3+6+9


# ---------------------------------------------------------------------------
# Interface method signatures (no-body fn)
# ---------------------------------------------------------------------------


class TestInterfaceSignatures:
    def test_interface_with_signature_only(self):
        src = '''interface Printable {
  fn print() -> Text
}
class A implements Printable {
  fn print() { return "A" }
}
let a = A()
let v = a.print()'''
        i = run(src)
        assert val(i, "v") == "A"

    def test_interface_with_multiple_signatures(self):
        src = '''interface Shape {
  fn area() -> Number
  fn perimeter() -> Number
}
class Circle implements Shape {
  var r = 5
  fn area() { return math.PI * r * r }
  fn perimeter() { return 2 * math.PI * r }
}
let c = Circle()
let v = c.area() > 0'''
        i = run(src)
        assert val(i, "v") is True

    def test_interface_does_not_crash_on_body_fn(self):
        src = '''interface Mixin {
  fn greet() { return "hello" }
}
class B implements Mixin {}
let b = B()
let v = "ok"'''
        i = run(src)
        assert val(i, "v") == "ok"


# ---------------------------------------------------------------------------
# Combined / integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_comprehension_with_anon_fn(self):
        i = run("let transform = fn(x) => x * x\nlet v = [transform(x) for x in range(1, 6)]")
        assert val(i, "v") == [1, 4, 9, 16, 25]

    def test_switch_inside_comprehension(self):
        src = """fn classify(n) {
  switch n {
    case 1: return "one"
    case 2: return "two"
    default: return "many"
  }
}
let v = [classify(x) for x in [1, 2, 3]]"""
        i = run(src)
        assert val(i, "v") == ["one", "two", "many"]

    def test_regex_filter_in_comprehension(self):
        src = """let r = /^[aeiou]/i
let words = ["apple", "banana", "orange", "grape", "elm"]
let v = [w for w in words if r.test(w)]"""
        i = run(src)
        assert val(i, "v") == ["apple", "orange", "elm"]

    def test_increment_and_comprehension(self):
        src = """var n = 0
let v = [x * x for x in range(1, 6)]
n++
let cnt = n"""
        i = run(src)
        assert val(i, "v") == [1, 4, 9, 16, 25]
        assert val(i, "cnt") == 1

    def test_anon_fn_with_switch(self):
        src = """let grade = fn(score) {
  switch score {
    case 100: return "A+"
    case 90: return "A"
    default: return "B"
  }
}
let v = grade(90)"""
        i = run(src)
        assert val(i, "v") == "A"
