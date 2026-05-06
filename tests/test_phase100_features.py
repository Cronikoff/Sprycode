"""Tests for Phase 100: Pattern Matching / Advanced Switch"""
from __future__ import annotations
from typing import Any
import pytest
from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str = "v") -> Any:
    return i.globals.get(name)


# ── Switch on string values ───────────────────────────────────────────────────

class TestSwitchString:
    def test_switch_string_match(self):
        i = run("""
let s = \"hello\";
let v = \"\";
switch(s) {
  case \"hello\": v = \"matched\"; break;
  case \"world\": v = \"other\"; break;
  default: v = \"none\";
}
""")
        assert val(i) == "matched"

    def test_switch_string_default(self):
        i = run("""
let s = \"unknown\";
let v = \"\";
switch(s) {
  case \"hello\": v = \"hello\"; break;
  default: v = \"default\";
}
""")
        assert val(i) == "default"

    def test_switch_string_second_case(self):
        i = run("""
let s = \"world\";
let v = \"\";
switch(s) {
  case \"hello\": v = \"hello\"; break;
  case \"world\": v = \"world\"; break;
}
""")
        assert val(i) == "world"

    def test_switch_no_match_no_default(self):
        i = run("""
let s = \"xyz\";
let v = \"none\";
switch(s) {
  case \"a\": v = \"a\"; break;
  case \"b\": v = \"b\"; break;
}
""")
        assert val(i) == "none"


# ── Switch with multiple cases ────────────────────────────────────────────────

class TestSwitchMultipleCases:
    def test_switch_number_1(self):
        i = run("""
let x = 1;
let v = \"\";
switch(x) {
  case 1: v = \"one\"; break;
  case 2: v = \"two\"; break;
  case 3: v = \"three\"; break;
  default: v = \"other\";
}
""")
        assert val(i) == "one"

    def test_switch_number_3(self):
        i = run("""
let x = 3;
let v = \"\";
switch(x) {
  case 1: v = \"one\"; break;
  case 2: v = \"two\"; break;
  case 3: v = \"three\"; break;
  default: v = \"other\";
}
""")
        assert val(i) == "three"

    def test_switch_fallthrough(self):
        i = run("""
let x = 2;
let v = 0;
switch(x) {
  case 1: v = 10; break;
  case 2: v = 20; break;
  case 3: v = 30; break;
}
""")
        assert val(i) == 20

    def test_switch_five_cases(self):
        i = run("""
let x = 4;
let v = 0;
switch(x) {
  case 1: v = 10; break;
  case 2: v = 20; break;
  case 3: v = 30; break;
  case 4: v = 40; break;
  case 5: v = 50; break;
}
""")
        assert val(i) == 40

    def test_switch_default_middle(self):
        i = run("""
let x = 99;
let v = \"\";
switch(x) {
  case 1: v = \"one\"; break;
  default: v = \"default\"; break;
  case 2: v = \"two\"; break;
}
""")
        assert val(i) == "default"


# ── Switch with complex expressions ──────────────────────────────────────────

class TestSwitchComplexExpressions:
    def test_switch_on_expression(self):
        i = run("""
let a = 2; let b = 3;
let v = \"\";
switch(a + b) {
  case 4: v = \"four\"; break;
  case 5: v = \"five\"; break;
  case 6: v = \"six\"; break;
}
""")
        assert val(i) == "five"

    def test_switch_on_method_result(self):
        i = run("""
let s = \"hello\";
let v = \"\";
switch(s.length) {
  case 3: v = \"short\"; break;
  case 5: v = \"medium\"; break;
  case 7: v = \"long\"; break;
}
""")
        assert val(i) == "medium"

    def test_switch_on_ternary_result(self):
        i = run("""
let x = 10;
let v = \"\";
switch(x > 5 ? \"big\" : \"small\") {
  case \"big\": v = \"big\"; break;
  case \"small\": v = \"small\"; break;
}
""")
        assert val(i) == "big"

    def test_switch_on_mod(self):
        i = run("""
let x = 7;
let v = \"\";
switch(x % 3) {
  case 0: v = \"divisible\"; break;
  case 1: v = \"remainder1\"; break;
  case 2: v = \"remainder2\"; break;
}
""")
        assert val(i) == "remainder1"


# ── Nested switch ──────────────────────────────────────────────────────────────

class TestNestedSwitch:
    def test_nested_switch(self):
        i = run("""
let x = 1; let y = 2;
let v = \"\";
switch(x) {
  case 1:
    switch(y) {
      case 1: v = \"1-1\"; break;
      case 2: v = \"1-2\"; break;
    }
    break;
  case 2: v = \"2\"; break;
}
""")
        assert val(i) == "1-2"

    def test_nested_switch_outer(self):
        i = run("""
let x = 2; let y = 1;
let v = \"\";
switch(x) {
  case 1:
    switch(y) {
      case 1: v = \"1-1\"; break;
    }
    break;
  case 2:
    switch(y) {
      case 1: v = \"2-1\"; break;
      case 2: v = \"2-2\"; break;
    }
    break;
}
""")
        assert val(i) == "2-1"


# ── Switch inside a function ──────────────────────────────────────────────────

class TestSwitchInFunction:
    def test_switch_in_function(self):
        i = run("""
function describe(x) {
  switch(x) {
    case 1: return \"one\";
    case 2: return \"two\";
    default: return \"other\";
  }
}
let v = describe(2);
""")
        assert val(i) == "two"

    def test_switch_function_default(self):
        i = run("""
function gradeLabel(g) {
  switch(g) {
    case \"A\": return \"Excellent\";
    case \"B\": return \"Good\";
    case \"C\": return \"Average\";
    default: return \"Unknown\";
  }
}
let v = gradeLabel(\"B\");
""")
        assert val(i) == "Good"

    def test_switch_returns_value(self):
        i = run("""
function f(x) {
  switch(x) {
    case 1: return 10;
    case 2: return 20;
    case 3: return 30;
  }
  return 0;
}
let v = f(3);
""")
        assert val(i) == 30


# ── Switch with object destructuring in case body ─────────────────────────────

class TestSwitchWithDestructuring:
    def test_switch_body_destructure(self):
        i = run("""
let obj = {type: \"circle\", r: 5};
let v = 0;
switch(obj.type) {
  case \"circle\": {
    let {r} = obj;
    v = r * 2;
    break;
  }
  case \"square\": v = 1; break;
}
""")
        assert val(i) == 10

    def test_switch_body_computes(self):
        i = run("""
let item = {kind: \"add\", a: 3, b: 4};
let v = 0;
switch(item.kind) {
  case \"add\": v = item.a + item.b; break;
  case \"mul\": v = item.a * item.b; break;
}
""")
        assert val(i) == 7


# ── Ternary chains ────────────────────────────────────────────────────────────

class TestTernaryChains:
    def test_ternary_chain_2(self):
        i = run("let x = 2; let v = x === 1 ? \"one\" : \"other\";")
        assert val(i) == "other"

    def test_ternary_chain_3(self):
        i = run("let x = 3; let v = x === 1 ? \"one\" : x === 2 ? \"two\" : \"three\";")
        assert val(i) == "three"

    def test_ternary_chain_4(self):
        i = run("""
let x = 2;
let v = x === 1 ? \"a\" : x === 2 ? \"b\" : x === 3 ? \"c\" : \"d\";
""")
        assert val(i) == "b"

    def test_ternary_chain_5(self):
        i = run("""
let score = 85;
let v = score >= 90 ? \"A\" : score >= 80 ? \"B\" : score >= 70 ? \"C\" : score >= 60 ? \"D\" : \"F\";
""")
        assert val(i) == "B"

    def test_ternary_nested(self):
        i = run("let x = true; let y = false; let v = x ? (y ? 1 : 2) : 3;")
        assert val(i) == 2

    def test_ternary_in_expression(self):
        i = run("let n = 5; let v = (n > 3 ? n * 2 : n / 2) + 1;")
        assert val(i) == 11


# ── Short-circuit evaluation ──────────────────────────────────────────────────

class TestShortCircuit:
    def test_and_false_short_circuits(self):
        i = run("""
let v = 0;
false && (v = 1);
""")
        assert val(i) == 0

    def test_and_true_evaluates_right(self):
        i = run("""
let v = 0;
true && (v = 1);
""")
        assert val(i) == 1

    def test_or_true_short_circuits(self):
        i = run("""
let v = 0;
true || (v = 99);
""")
        assert val(i) == 0

    def test_or_false_evaluates_right(self):
        i = run("""
let v = 0;
false || (v = 5);
""")
        assert val(i) == 5

    def test_and_chain(self):
        i = run("""
let v = [];
let a = true; let b = true; let c = false;
a && v.push(1);
b && v.push(2);
c && v.push(3);
""")
        assert val(i) == [1, 2]

    def test_or_chain(self):
        i = run("""
let v = 0;
let x = null;
let y = 0;
let z = 5;
let r = x || y || z;
v = r;
""")
        assert val(i) == 5


# ── Nullish assignment ??= ────────────────────────────────────────────────────

class TestNullishAssignment:
    def test_nullish_null(self):
        i = run("let a = null; a ??= 42; let v = a;")
        assert val(i) == 42

    def test_nullish_undefined(self):
        i = run("let a = undefined; a ??= \"default\"; let v = a;")
        assert val(i) == "default"

    def test_nullish_not_null_unchanged(self):
        i = run("let a = 0; a ??= 99; let v = a;")
        assert val(i) == 0

    def test_nullish_false_unchanged(self):
        i = run("let a = false; a ??= true; let v = a;")
        assert val(i) is False

    def test_nullish_empty_string_unchanged(self):
        i = run("let a = \"\"; a ??= \"fallback\"; let v = a;")
        assert val(i) == ""

    def test_nullish_pattern_object(self):
        i = run("""
let config = null;
config ??= {debug: false, level: 1};
let v = config.level;
""")
        assert val(i) == 1


# ── Logical OR assignment ||= ─────────────────────────────────────────────────

class TestLogicalOrAssignment:
    def test_or_assign_falsy(self):
        i = run("let a = 0; a ||= 5; let v = a;")
        assert val(i) == 5

    def test_or_assign_truthy_unchanged(self):
        i = run("let a = 1; a ||= 99; let v = a;")
        assert val(i) == 1

    def test_or_assign_null(self):
        i = run("let a = null; a ||= \"default\"; let v = a;")
        assert val(i) == "default"

    def test_or_assign_false(self):
        i = run("let a = false; a ||= true; let v = a;")
        assert val(i) is True

    def test_or_assign_empty_string(self):
        i = run("let a = \"\"; a ||= \"hello\"; let v = a;")
        assert val(i) == "hello"


# ── Logical AND assignment &&= ────────────────────────────────────────────────

class TestLogicalAndAssignment:
    def test_and_assign_truthy(self):
        i = run("let a = 1; a &&= 10; let v = a;")
        assert val(i) == 10

    def test_and_assign_falsy_unchanged(self):
        i = run("let a = 0; a &&= 99; let v = a;")
        assert val(i) == 0

    def test_and_assign_true(self):
        i = run("let a = true; a &&= 42; let v = a;")
        assert val(i) == 42

    def test_and_assign_false_unchanged(self):
        i = run("let a = false; a &&= 99; let v = a;")
        assert val(i) is False

    def test_and_assign_string_truthy(self):
        i = run("let a = \"hi\"; a &&= \"world\"; let v = a;")
        assert val(i) == "world"


# ── x ??= defaultVal pattern ─────────────────────────────────────────────────

class TestNullishDefaultPattern:
    def test_nullish_default_from_null(self):
        i = run("""
let options = null;
options ??= {timeout: 1000, retries: 3};
let v = options.timeout;
""")
        assert val(i) == 1000

    def test_nullish_default_preserved(self):
        i = run("""
let val = 0;
val ??= 99;
let v = val;
""")
        assert val(i) == 0

    def test_nullish_chained(self):
        i = run("""
let a = null;
a ??= null;
a ??= \"final\";
let v = a;
""")
        assert val(i) == "final"


# ── Comma operator ────────────────────────────────────────────────────────────

class TestCommaOperator:
    def test_comma_returns_last(self):
        i = run("let v = (1, 2, 3);")
        assert val(i) == 3

    def test_comma_two_values(self):
        i = run("let v = (10, 20);")
        assert val(i) == 20

    def test_comma_side_effects(self):
        i = run("""
let v = 0;
let r = (v = 5, v + 10);
""")
        assert i.globals.get("r") == 15

    def test_comma_in_for(self):
        i = run("""
let v = 0;
let s = 0;
for (v = 0; v < 3; v = v + 1) { s = s + v; }
""")
        assert i.globals.get("s") == 3


# ── Void operator ─────────────────────────────────────────────────────────────

class TestVoidOperator:
    def test_void_returns_undefined(self):
        i = run("let v = void 0;")
        assert val(i) is None

    def test_void_any_value(self):
        i = run("let v = void 42;")
        assert val(i) is None

    def test_void_string(self):
        i = run("let v = void \"hello\";")
        assert val(i) is None

    def test_void_expression(self):
        i = run("let v = void (1 + 2 + 3);")
        assert val(i) is None

    def test_void_side_effect(self):
        i = run("""
let x = 0;
let v = void (x = 99);
""")
        assert i.globals.get("x") == 99
        assert val(i) is None


# ── typeof on undeclared var ──────────────────────────────────────────────────

class TestTypeofUndeclared:
    def test_typeof_undeclared(self):
        i = run("let v = typeof neverDeclaredVar;")
        assert val(i) == "undefined"

    def test_typeof_declared_undefined(self):
        i = run("let x = undefined; let v = typeof x;")
        assert val(i) == "undefined"

    def test_typeof_number(self):
        i = run("let x = 42; let v = typeof x;")
        assert val(i) == "number"

    def test_typeof_string(self):
        i = run("let x = \"hi\"; let v = typeof x;")
        assert val(i) == "string"

    def test_typeof_boolean(self):
        i = run("let x = true; let v = typeof x;")
        assert val(i) == "boolean"

    def test_typeof_object(self):
        i = run("let x = {}; let v = typeof x;")
        assert val(i) == "object"

    def test_typeof_function(self):
        i = run("function f() {} let v = typeof f;")
        assert val(i) == "function"
