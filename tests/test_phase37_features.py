"""Phase 37 feature tests.

Covers:
- Short-circuit evaluation for ``&&`` and ``||``: right-hand side not evaluated when unnecessary;
  operators return the actual operand value (JS semantics)
- ``instanceof Array``, ``instanceof String``, ``instanceof Boolean``, ``instanceof Map``,
  ``instanceof Set``, ``instanceof Promise``, ``instanceof Symbol`` — JS primitive type aliases
- ``toFixed()`` with no arguments defaults to 0 decimal places (JS: ``(3.14).toFixed()`` → ``'3'``)
- ``Symbol.toString()`` / ``Symbol.valueOf()`` member access on SprySymbol
- Standalone block ``{ ... }`` as a statement with own lexical scope
- Class ``static { ... }`` initialization block — runs once when class is evaluated
"""

from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import Interpreter, SpryMap, SprySet, SpryPromise, SprySymbol
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


def val(source: str, name: str = "v") -> Any:
    return run(source).globals.get(name)


# ---------------------------------------------------------------------------
# Short-circuit evaluation for && and ||
# ---------------------------------------------------------------------------


class TestShortCircuitAnd:
    def test_false_and_side_effect_not_executed(self) -> None:
        """false && expr must NOT evaluate expr."""
        i = run("var v = 0; false && (v = 1); let r = v")
        assert i.globals.get("r") == 0

    def test_true_and_side_effect_executed(self) -> None:
        """true && expr MUST evaluate expr."""
        i = run("var v = 0; true && (v = 1); let r = v")
        assert i.globals.get("r") == 1

    def test_and_returns_last_truthy(self) -> None:
        """x && y returns y when x is truthy (JS semantics)."""
        assert val("let v = 42 && 99") == 99

    def test_and_returns_first_falsy(self) -> None:
        """x && y returns x when x is falsy (JS semantics)."""
        assert val("let v = false && 99") is False

    def test_and_null_short_circuits(self) -> None:
        assert val("let v = null && 99") is None

    def test_and_zero_short_circuits(self) -> None:
        assert val("let v = 0 && 99") == 0

    def test_and_chained(self) -> None:
        i = run("var c = 0; fn inc() { c = c + 1; return true }; true && true && inc(); let v = c")
        assert i.globals.get("v") == 1

    def test_and_chained_short_circuit_stops_early(self) -> None:
        i = run("var c = 0; fn inc() { c = c + 1; return true }; false && inc(); let v = c")
        assert i.globals.get("v") == 0

    def test_and_in_if_condition(self) -> None:
        src = """
var counter = 0
fn expensive() { counter = counter + 1; return true }
if (false && expensive()) { }
let v = counter
"""
        assert val(src, "v") == 0

    def test_and_with_truthy_string(self) -> None:
        assert val('let v = "hello" && "world"') == "world"

    def test_and_with_empty_string(self) -> None:
        assert val('let v = "" && "world"') == ""


class TestShortCircuitOr:
    def test_true_or_side_effect_not_executed(self) -> None:
        """true || expr must NOT evaluate expr."""
        i = run("var v = 0; true || (v = 1); let r = v")
        assert i.globals.get("r") == 0

    def test_false_or_side_effect_executed(self) -> None:
        """false || expr MUST evaluate expr."""
        i = run("var v = 0; false || (v = 1); let r = v")
        assert i.globals.get("r") == 1

    def test_or_returns_first_truthy(self) -> None:
        """x || y returns x when x is truthy (JS semantics)."""
        assert val('let v = "hello" || "default"') == "hello"

    def test_or_returns_second_when_first_falsy(self) -> None:
        """x || y returns y when x is falsy."""
        assert val('let v = null || "default"') == "default"

    def test_or_null_returns_right(self) -> None:
        assert val("let v = null || 42") == 42

    def test_or_zero_returns_right(self) -> None:
        assert val("let v = 0 || 99") == 99

    def test_or_with_truthy_number(self) -> None:
        assert val("let v = 1 || 99") == 1

    def test_or_chained(self) -> None:
        assert val('let v = false || null || "found"') == "found"

    def test_or_in_default_value_pattern(self) -> None:
        src = "fn greet(name) { return (name || \"stranger\") }; let v = greet(null)"
        assert val(src) == "stranger"

    def test_or_does_not_execute_when_truthy(self) -> None:
        i = run("var c = 0; fn side() { c = c + 1; return \"x\" }; \"truthy\" || side(); let v = c")
        assert i.globals.get("v") == 0


# ---------------------------------------------------------------------------
# instanceof JS primitive type aliases
# ---------------------------------------------------------------------------


class TestInstanceofJSAliases:
    def test_list_instanceof_array(self) -> None:
        assert val("let v = [] instanceof Array") is True

    def test_non_empty_list_instanceof_array(self) -> None:
        assert val("let v = [1, 2, 3] instanceof Array") is True

    def test_dict_not_instanceof_array(self) -> None:
        assert val("let v = {} instanceof Array") is False

    def test_string_instanceof_string(self) -> None:
        assert val('let v = "hello" instanceof String') is True

    def test_empty_string_instanceof_string(self) -> None:
        assert val('let v = "" instanceof String') is True

    def test_number_not_instanceof_string(self) -> None:
        assert val("let v = 42 instanceof String") is False

    def test_true_instanceof_boolean(self) -> None:
        assert val("let v = true instanceof Boolean") is True

    def test_false_instanceof_boolean(self) -> None:
        assert val("let v = false instanceof Boolean") is True

    def test_number_not_instanceof_boolean(self) -> None:
        assert val("let v = 1 instanceof Boolean") is False

    def test_int_instanceof_number(self) -> None:
        assert val("let v = 42 instanceof Number") is True

    def test_float_instanceof_number(self) -> None:
        assert val("let v = 3.14 instanceof Number") is True

    def test_bool_not_instanceof_number(self) -> None:
        """In JS, true is not instanceof Number even though bool is subtype of int in Python."""
        assert val("let v = true instanceof Number") is False

    def test_map_instanceof_map(self) -> None:
        assert val("let m = new Map(); let v = m instanceof Map") is True

    def test_set_instanceof_set(self) -> None:
        assert val("let s = new Set(); let v = s instanceof Set") is True

    def test_promise_instanceof_promise(self) -> None:
        assert val("let p = Promise.resolve(1); let v = p instanceof Promise") is True

    def test_symbol_instanceof_symbol(self) -> None:
        assert val("let s = Symbol('x'); let v = s instanceof Symbol") is True

    def test_class_instance_instanceof_own_class(self) -> None:
        src = "class Dog {}; let d = Dog.new(); let v = d instanceof Dog"
        assert val(src) is True

    def test_class_instance_not_instanceof_other_class(self) -> None:
        src = "class A {}; class B {}; let a = A.new(); let v = a instanceof B"
        assert val(src) is False

    def test_object_instanceof_object(self) -> None:
        assert val("let v = {} instanceof Object") is True


# ---------------------------------------------------------------------------
# toFixed() with no arguments defaults to 0 decimal places
# ---------------------------------------------------------------------------


class TestToFixedNoArgs:
    def test_float_no_args(self) -> None:
        assert val("let v = (3.14).toFixed()") == "3"

    def test_rounding_up(self) -> None:
        assert val("let v = (3.7).toFixed()") == "4"

    def test_integer_no_args(self) -> None:
        assert val("let v = (5).toFixed()") == "5"

    def test_negative_no_args(self) -> None:
        assert val("let v = (-3.7).toFixed()") == "-4"

    def test_zero_no_args(self) -> None:
        assert val("let v = (0.0).toFixed()") == "0"

    def test_with_zero_arg(self) -> None:
        assert val("let v = (3.14).toFixed(0)") == "3"

    def test_with_two_arg(self) -> None:
        assert val("let v = (3.14159).toFixed(2)") == "3.14"

    def test_with_five_arg(self) -> None:
        assert val("let v = (3.14159).toFixed(5)") == "3.14159"


# ---------------------------------------------------------------------------
# Symbol.toString() / Symbol.valueOf() / Symbol.description
# ---------------------------------------------------------------------------


class TestSymbolMethods:
    def test_to_string_with_desc(self) -> None:
        assert val("let s = Symbol('hello'); let v = s.toString()") == "Symbol(hello)"

    def test_to_string_empty_desc(self) -> None:
        assert val("let s = Symbol(''); let v = s.toString()") == "Symbol()"

    def test_to_string_no_parens(self) -> None:
        assert val("let s = Symbol(); let v = s.toString()") == "Symbol()"

    def test_value_of_returns_self(self) -> None:
        i = run("let s = Symbol('x'); let sv = s.valueOf()")
        s = i.globals.get("s")
        sv = i.globals.get("sv")
        assert sv is s

    def test_description_property(self) -> None:
        assert val("let s = Symbol('desc'); let v = s.description") == "desc"

    def test_description_empty(self) -> None:
        assert val("let s = Symbol(''); let v = s.description") == ""

    def test_symbols_are_unique(self) -> None:
        i = run("let a = Symbol('x'); let b = Symbol('x'); let v = a == b")
        assert i.globals.get("v") is False

    def test_same_symbol_equals_itself(self) -> None:
        i = run("let a = Symbol('x'); let v = a == a")
        assert i.globals.get("v") is True


# ---------------------------------------------------------------------------
# Standalone block { ... } as statement with own lexical scope
# ---------------------------------------------------------------------------


class TestStandaloneBlock:
    def test_simple_assignment_in_block(self) -> None:
        assert val("var v = 0; { v = 42 }") == 42

    def test_outer_var_modified_in_block(self) -> None:
        """Modifying an outer var from inside a block works."""
        i = run("var x = 0; { x = 5 }; let v = x")
        assert i.globals.get("v") == 5

    def test_let_in_block_scope_not_leaked(self) -> None:
        """let declarations stay inside the block scope."""
        src = """
var v = 0
{
  let inner = 99
  v = inner
}
var leaked = null
try {
  leaked = inner
} catch {
  leaked = null
}
"""
        i = run(src)
        assert i.globals.get("v") == 99
        assert i.globals.get("leaked") is None

    def test_block_with_let_decl(self) -> None:
        src = "var v = 0; { let x = 5; v = x }"
        assert val(src) == 5

    def test_nested_blocks(self) -> None:
        src = """
var v = 0
{
  let a = 10
  {
    let b = 20
    v = a + b
  }
}
"""
        assert val(src) == 30

    def test_block_with_if(self) -> None:
        src = """
var v = 0
{
  if (true) {
    v = 1
  }
}
"""
        assert val(src) == 1

    def test_block_with_for(self) -> None:
        src = """
var v = 0
{
  for (let i = 0; i < 3; i++) {
    v = v + i
  }
}
"""
        assert val(src) == 3

    def test_empty_block(self) -> None:
        """Empty block {} should be valid."""
        assert val("var v = 5; {}") == 5

    def test_block_shadow_outer_let(self) -> None:
        """Inner let shadows outer let."""
        src = """
let outer = 1
var v = 0
{
  let outer = 99
  v = outer
}
"""
        assert val(src) == 99


# ---------------------------------------------------------------------------
# Class static { ... } initialization block
# ---------------------------------------------------------------------------


class TestStaticInitBlock:
    def test_basic_static_init(self) -> None:
        src = """
class Config {
  static db = "default"
  static {
    Config.db = "postgresql"
  }
}
let v = Config.db
"""
        assert val(src) == "postgresql"

    def test_static_init_runs_once(self) -> None:
        src = """
class Counter {
  static count = 0
  static {
    Counter.count = Counter.count + 10
  }
}
let v = Counter.count
"""
        assert val(src) == 10

    def test_static_init_can_compute(self) -> None:
        src = """
class Config {
  static value = 0
  static {
    Config.value = 2 + 3
  }
}
let v = Config.value
"""
        assert val(src) == 5

    def test_static_init_runs_after_static_fields(self) -> None:
        src = """
class Cfg {
  static base = 100
  static total = 0
  static {
    Cfg.total = Cfg.base * 2
  }
}
let v = Cfg.total
"""
        assert val(src) == 200

    def test_static_init_with_multiple_statements(self) -> None:
        src = """
class Env {
  static host = ""
  static port = 0
  static {
    Env.host = "localhost"
    Env.port = 8080
  }
}
let v = Env.host + ":" + Env.port
"""
        assert val(src) == "localhost:8080"

    def test_empty_static_block(self) -> None:
        src = """
class MyClass {
  static x = 42
  static { }
}
let v = MyClass.x
"""
        assert val(src) == 42

    def test_static_init_can_use_conditions(self) -> None:
        src = """
class Settings {
  static debug = false
  static {
    let flag = true
    if (flag) {
      Settings.debug = true
    }
  }
}
let v = Settings.debug
"""
        assert val(src) is True
