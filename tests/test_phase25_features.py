"""Phase 25 feature tests.

Covers:
- Arrow function body assignment via _parse_lambda_body():
    x => a = x, (x, y) => obj.prop = x + y, x => a += x, () => a = 1
- TokenType.MONEY_TYPE in _IDENTIFIER_LIKE:
    'Money' usable as variable name, parameter name, and class name
- class extends _ErrorNamespace:
    Custom error classes extending Error, TypeError, RangeError, etc.
    instanceof walking the built-in error superclass
- instanceof superclass chain walk:
    val instanceof ParentClass when val is SpryInstance of a subclass
- structuredClone SpryMap / SprySet:
    Deep clone produces independent copies of Map and Set values
- switch case X { } brace syntax:
    Both brace and colon styles, default branch with braces
"""

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
# Arrow function body assignment
# ===========================================================================

class TestArrowBodyAssignment:
    """Arrow function bodies may contain assignment expressions."""

    def test_single_param_simple_assignment(self):
        i = run("var a = 0\nlet f = v => a = v\nf(42)")
        assert val(i, "a") == 42

    def test_single_param_assignment_side_effect(self):
        """Arrow body with assignment sets the outer variable."""
        i = run("var a = 0\nlet f = v => a = v\nf(7)\nlet r = a")
        assert val(i, "r") == 7

    def test_zero_param_simple_assignment(self):
        i = run("var a = 0\nlet f = () => a = 99\nf()")
        assert val(i, "a") == 99

    def test_multi_param_simple_assignment(self):
        i = run("var a = 0\nlet f = (x, y) => a = x + y\nf(3, 4)")
        assert val(i, "a") == 7

    def test_multi_param_assignment_with_expression(self):
        i = run("var result = 0\nlet f = (x, y) => result = x * y\nf(6, 7)")
        assert val(i, "result") == 42

    def test_single_param_compound_assignment_plus(self):
        i = run("var a = 10\nlet f = v => a += v\nf(5)")
        assert val(i, "a") == 15

    def test_single_param_compound_assignment_minus(self):
        i = run("var a = 10\nlet f = v => a -= v\nf(3)")
        assert val(i, "a") == 7

    def test_single_param_compound_assignment_star(self):
        i = run("var a = 5\nlet f = v => a *= v\nf(4)")
        assert val(i, "a") == 20

    def test_member_assignment_in_arrow(self):
        i = run("var obj = {x: 0}\nlet f = v => obj.x = v\nf(55)")
        assert val(i, "obj") == {"x": 55}

    def test_arrow_body_assignment_in_foreach(self):
        i = run("var total = 0\nlet nums = [1,2,3]\nnums.forEach(n => total = total + n)")
        assert val(i, "total") == 6

    def test_arrow_body_assignment_chained_calls(self):
        i = run("var last = 0\nlet f = v => last = v\nf(1)\nf(2)\nf(3)")
        assert val(i, "last") == 3

    def test_arrow_body_not_polluting_pipeline(self):
        """Arrow with assignment in body must not consume |> operators."""
        i = run("let r = [1,2,3,4,5] |> filter(x => x > 2) |> map(x => x * 10)")
        assert val(i, "r") == [30, 40, 50]

    def test_arrow_body_normal_expr_still_works(self):
        i = run("let f = x => x * 2\nlet r = f(5)")
        assert val(i, "r") == 10

    def test_arrow_block_body_still_works(self):
        i = run("var a = 0\nlet f = v => { a = v; return a * 2 }\nlet r = f(3)")
        assert val(i, "r") == 6
        assert val(i, "a") == 3

    def test_multi_param_block_body_assignment(self):
        i = run("var s = 0\nlet f = (x, y) => { s = x + y }\nf(10, 20)")
        assert val(i, "s") == 30

    def test_arrow_body_assignment_in_sort(self):
        i = run("let r = [3,1,2].sort((a, b) => a - b)")
        assert val(i, "r") == [1, 2, 3]

    def test_arrow_body_assignment_in_reduce(self):
        i = run("let r = [1,2,3,4].reduce((acc, x) => acc + x, 0)")
        assert val(i, "r") == 10


# ===========================================================================
# MONEY_TYPE as identifier
# ===========================================================================

class TestMoneyTypeAsIdentifier:
    """'Money' keyword can be used as a variable/parameter name."""

    def test_money_as_let_variable(self):
        i = run("let Money = 42\nlet r = Money")
        assert val(i, "r") == 42

    def test_money_as_var_variable(self):
        i = run("var Money = 100\nMoney = 200\nlet r = Money")
        assert val(i, "r") == 200

    def test_money_as_function_param(self):
        i = run("fn calc(Money) { return Money * 2 }\nlet r = calc(5)")
        assert val(i, "r") == 10

    def test_money_as_lambda_param(self):
        i = run("let f = Money => Money + 1\nlet r = f(9)")
        assert val(i, "r") == 10

    def test_money_in_object_shorthand(self):
        i = run("let Money = 50\nlet obj = {Money}\nlet r = obj[\"Money\"]")
        assert val(i, "r") == 50

    def test_money_as_class_name(self):
        i = run("""
class Money {
  fn init(amount) { self.amount = amount }
  fn getValue() { return self.amount }
}
let m = Money.new(100)
let r = m.getValue()
""")
        assert val(i, "r") == 100

    def test_money_in_for_loop(self):
        i = run("var total = 0\nfor Money in [10, 20, 30] { total = total + Money }")
        assert val(i, "total") == 60

    def test_money_in_destructure(self):
        i = run("let [Money, price] = [10, 20]\nlet r = Money + price")
        assert val(i, "r") == 30

    def test_money_as_multi_param(self):
        i = run("let f = (Money, tax) => Money + tax\nlet r = f(100, 15)")
        assert val(i, "r") == 115


# ===========================================================================
# class extends _ErrorNamespace (built-in errors)
# ===========================================================================

class TestClassExtendsError:
    """Classes can extend built-in error types (Error, TypeError, etc.)."""

    def test_extends_error_message(self):
        i = run("""
class AppError extends Error {
  fn init(msg) { self.message = msg; self.name = "AppError" }
}
let e = AppError.new("something went wrong")
let r = e.message
""")
        assert val(i, "r") == "something went wrong"

    def test_extends_error_name(self):
        i = run("""
class AppError extends Error {
  fn init(msg) { self.message = msg; self.name = "AppError" }
}
let e = AppError.new("oops")
let r = e.name
""")
        assert val(i, "r") == "AppError"

    def test_extends_error_instanceof_self(self):
        i = run("""
class AppError extends Error {
  fn init(msg) { self.message = msg }
}
let e = AppError.new("msg")
let r = e instanceof AppError
""")
        assert val(i, "r") is True

    def test_extends_error_instanceof_error(self):
        i = run("""
class AppError extends Error {
  fn init(msg) { self.message = msg }
}
let e = AppError.new("msg")
let r = e instanceof Error
""")
        assert val(i, "r") is True

    def test_extends_type_error_instanceof(self):
        i = run("""
class ValidationError extends TypeError {
  fn init(msg) { self.message = msg; self.name = "ValidationError" }
}
let e = ValidationError.new("bad type")
let r1 = e instanceof ValidationError
let r2 = e instanceof TypeError
""")
        assert val(i, "r1") is True
        assert val(i, "r2") is True

    def test_extends_range_error_instanceof(self):
        i = run("""
class BoundsError extends RangeError {
  fn init(msg) { self.message = msg }
}
let e = BoundsError.new("out of bounds")
let r = e instanceof RangeError
""")
        assert val(i, "r") is True

    def test_custom_error_not_instanceof_other_error(self):
        i = run("""
class AppError extends Error {
  fn init(msg) { self.message = msg }
}
let e = AppError.new("msg")
let r = e instanceof TypeError
""")
        assert val(i, "r") is False

    def test_custom_error_thrown_and_caught(self):
        i = run("""
class AppError extends Error {
  fn init(msg) { self.message = msg; self.name = "AppError" }
}
var caught = false
var msg = ""
try {
  let e = AppError.new("bad")
  throw e
} catch err {
  caught = true
  msg = err.message
}
""")
        assert val(i, "caught") is True
        assert val(i, "msg") == "bad"

    def test_custom_error_with_extra_fields(self):
        i = run("""
class HttpError extends Error {
  fn init(msg, code) {
    self.message = msg
    self.name = "HttpError"
    self.statusCode = code
  }
}
let e = HttpError.new("Not Found", 404)
let r1 = e.message
let r2 = e.statusCode
let r3 = e instanceof Error
""")
        assert val(i, "r1") == "Not Found"
        assert val(i, "r2") == 404
        assert val(i, "r3") is True

    def test_custom_error_method(self):
        i = run("""
class AppError extends Error {
  fn init(msg) { self.message = msg; self.name = "AppError" }
  fn toString() { return self.name + ": " + self.message }
}
let e = AppError.new("fail")
let r = e.toString()
""")
        assert val(i, "r") == "AppError: fail"


# ===========================================================================
# instanceof superclass chain walk
# ===========================================================================

class TestInstanceofChain:
    """instanceof walks the full superclass chain."""

    def test_direct_class(self):
        i = run("""
class Animal { fn init() {} }
let a = Animal.new()
let r = a instanceof Animal
""")
        assert val(i, "r") is True

    def test_parent_class(self):
        i = run("""
class Animal { fn init() {} }
class Dog extends Animal { fn init() {} }
let d = Dog.new()
let r = d instanceof Animal
""")
        assert val(i, "r") is True

    def test_grandparent_class(self):
        i = run("""
class Animal { fn init() {} }
class Dog extends Animal { fn init() {} }
class Poodle extends Dog { fn init() {} }
let p = Poodle.new()
let r = p instanceof Animal
""")
        assert val(i, "r") is True

    def test_not_unrelated_class(self):
        i = run("""
class Animal { fn init() {} }
class Car { fn init() {} }
let a = Animal.new()
let r = a instanceof Car
""")
        assert val(i, "r") is False

    def test_grandchild_instanceof_grandparent(self):
        i = run("""
class Base { fn init() {} }
class Mid extends Base { fn init() {} }
class Leaf extends Mid { fn init() {} }
let obj = Leaf.new()
let r1 = obj instanceof Leaf
let r2 = obj instanceof Mid
let r3 = obj instanceof Base
""")
        assert val(i, "r1") is True
        assert val(i, "r2") is True
        assert val(i, "r3") is True

    def test_parent_not_instanceof_child(self):
        i = run("""
class Animal { fn init() {} }
class Dog extends Animal { fn init() {} }
let a = Animal.new()
let r = a instanceof Dog
""")
        assert val(i, "r") is False


# ===========================================================================
# structuredClone with SpryMap / SprySet
# ===========================================================================

class TestStructuredCloneMapSet:
    """structuredClone deep-clones SpryMap and SprySet values."""

    # SpryMap
    def test_clone_map_preserves_values(self):
        i = run("""
let m = Map.new()
m.set("a", 1)
m.set("b", 2)
let cloned = structuredClone(m)
let r = cloned.get("a")
""")
        assert val(i, "r") == 1

    def test_clone_map_is_independent(self):
        i = run("""
let m = Map.new()
m.set("a", 1)
let cloned = structuredClone(m)
cloned.set("a", 99)
let r = m.get("a")
""")
        assert val(i, "r") == 1

    def test_clone_map_new_keys_not_in_original(self):
        i = run("""
let m = Map.new()
m.set("a", 1)
let cloned = structuredClone(m)
cloned.set("b", 2)
let r = m.has("b")
""")
        assert val(i, "r") is False

    def test_clone_map_original_changes_not_in_clone(self):
        i = run("""
let m = Map.new()
m.set("x", 10)
let cloned = structuredClone(m)
m.set("x", 99)
let r = cloned.get("x")
""")
        assert val(i, "r") == 10

    def test_clone_empty_map(self):
        i = run("""
let m = Map.new()
let cloned = structuredClone(m)
let r = cloned.size
""")
        assert val(i, "r") == 0

    def test_clone_map_size_same(self):
        i = run("""
let m = Map.new()
m.set("a", 1)
m.set("b", 2)
m.set("c", 3)
let cloned = structuredClone(m)
let r = cloned.size
""")
        assert val(i, "r") == 3

    # SprySet
    def test_clone_set_preserves_values(self):
        i = run("""
let s = Set.new([1, 2, 3])
let cloned = structuredClone(s)
let r = cloned.has(2)
""")
        assert val(i, "r") is True

    def test_clone_set_is_independent_add(self):
        i = run("""
let s = Set.new([1, 2, 3])
let cloned = structuredClone(s)
cloned.add(4)
let r = s.size
""")
        assert val(i, "r") == 3

    def test_clone_set_is_independent_delete(self):
        i = run("""
let s = Set.new([1, 2, 3])
let cloned = structuredClone(s)
cloned.delete(1)
let r = s.has(1)
""")
        assert val(i, "r") is True

    def test_clone_set_size_preserved(self):
        i = run("""
let s = Set.new([10, 20, 30])
let cloned = structuredClone(s)
let r = cloned.size
""")
        assert val(i, "r") == 3

    def test_clone_empty_set(self):
        i = run("""
let s = Set.new([])
let cloned = structuredClone(s)
let r = cloned.size
""")
        assert val(i, "r") == 0

    def test_clone_set_original_unaffected_by_clone_delete(self):
        i = run("""
let s = Set.new([1, 2, 3])
let cloned = structuredClone(s)
cloned.delete(2)
let r = s.size
""")
        assert val(i, "r") == 3

    # structuredClone with plain dict/list (pre-existing, regression check)
    def test_clone_dict_independence(self):
        i = run("""
let orig = {a: 1, b: 2}
let cloned = structuredClone(orig)
cloned["a"] = 99
let r = orig["a"]
""")
        assert val(i, "r") == 1

    def test_clone_list_independence(self):
        i = run("""
let orig = [1, 2, 3]
let cloned = structuredClone(orig)
cloned[0] = 99
let r = orig[0]
""")
        assert val(i, "r") == 1

    def test_clone_nested_dict(self):
        i = run("""
let orig = {a: {b: 1}}
let cloned = structuredClone(orig)
cloned["a"]["b"] = 99
let r = orig["a"]["b"]
""")
        assert val(i, "r") == 1


# ===========================================================================
# switch case X { } brace syntax
# ===========================================================================

class TestSwitchCaseBraceSyntax:
    """switch cases support both `case X:` and `case X { }` block syntax."""

    def test_brace_case_basic(self):
        i = run("""
var r = 0
switch 1 {
  case 1 { r = 10 }
  case 2 { r = 20 }
}
""")
        assert val(i, "r") == 10

    def test_brace_case_second(self):
        i = run("""
var r = 0
switch 2 {
  case 1 { r = 10 }
  case 2 { r = 20 }
}
""")
        assert val(i, "r") == 20

    def test_brace_case_with_default(self):
        i = run("""
var r = 0
switch 99 {
  case 1 { r = 1 }
  case 2 { r = 2 }
  default { r = 99 }
}
""")
        assert val(i, "r") == 99

    def test_brace_default_only(self):
        i = run("""
var r = 0
switch "x" {
  default { r = 42 }
}
""")
        assert val(i, "r") == 42

    def test_brace_case_multi_statement(self):
        i = run("""
var r = 0
var s = 0
switch 1 {
  case 1 { r = 10; s = 20 }
}
""")
        assert val(i, "r") == 10
        assert val(i, "s") == 20

    def test_brace_case_string(self):
        i = run("""
var r = ""
switch "hello" {
  case "hello" { r = "world" }
  case "bye" { r = "gone" }
}
""")
        assert val(i, "r") == "world"

    def test_brace_case_no_match_no_default(self):
        i = run("""
var r = 0
switch 5 {
  case 1 { r = 1 }
  case 2 { r = 2 }
}
""")
        assert val(i, "r") == 0

    def test_brace_case_with_nested_logic(self):
        i = run("""
var r = 0
switch 2 {
  case 1 { r = 1 }
  case 2 {
    let x = 10
    r = x * 2
  }
}
""")
        assert val(i, "r") == 20

    def test_colon_case_style_still_works(self):
        # colon-style cases (original syntax) must still work
        i = run("""
var r = 0
switch 3 {
  case 1:
    r = 1
  case 3:
    r = 3
  default:
    r = 0
}
""")
        assert val(i, "r") == 3

    def test_switch_on_expression(self):
        i = run("""
var x = 5
var r = 0
switch x * 2 {
  case 8 { r = 8 }
  case 10 { r = 10 }
  case 12 { r = 12 }
}
""")
        assert val(i, "r") == 10
