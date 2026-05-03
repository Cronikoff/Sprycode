"""Phase 25 feature tests."""
from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import (
    Interpreter,
    SpryInstance,
    SpryRuntimeError,
)
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
# FIX 1: Arrow function body with assignment
# ---------------------------------------------------------------------------


def test_arrow_assign_forEach_sum() -> None:
    i = run("var s = 0; [1,2,3].forEach(x => s = s + x); let v = s")
    assert i.globals.get("v") == 6


def test_arrow_assign_forEach_accumulate() -> None:
    i = run("var acc = []; [1,2,3].forEach((x, i) => acc.push(x * i)); let v = acc")
    assert i.globals.get("v") == [0, 2, 6]


def test_arrow_assign_map_forEach() -> None:
    i = run("var s = 0; Map.new([['a',1],['b',2]]).forEach((val2, k) => s = s + val2); let r = s")
    assert i.globals.get("r") == 3


def test_arrow_assign_set_forEach() -> None:
    i = run("var s = 0; Set.new([1,2,3]).forEach(x => s = s + x); let v = s")
    assert i.globals.get("v") == 6


def test_arrow_assign_does_not_consume_pipeline() -> None:
    i = run("let v = [1,2,3,4,5,6,7,8,9,10] |> filter x => x % 2 == 0 |> take 3")
    assert i.globals.get("v") == [2, 4, 6]


def test_arrow_assign_compound() -> None:
    i = run("var s = 0; [10, 20, 30].forEach(x => s += x); let v = s")
    assert i.globals.get("v") == 60


def test_arrow_assign_member() -> None:
    i = run("let obj = { count: 0 }; obj.count = 0; [1,2,3].forEach(x => obj.count = obj.count + x); let v = obj.count")
    assert i.globals.get("v") == 6


def test_arrow_filter_unchanged() -> None:
    i = run("let v = [1,2,3,4].filter(x => x > 2)")
    assert i.globals.get("v") == [3, 4]


# ---------------------------------------------------------------------------
# FIX 2: Object method shorthand with default params (Proxy)
# ---------------------------------------------------------------------------


def test_proxy_get_handler() -> None:
    i = run("""
let handler = { get(target, key) { return target[key] * 2 } }
let p = Proxy.new({x: 21}, handler)
let v = p.x
""")
    assert i.globals.get("v") == 42


def test_object_method_shorthand_default_param() -> None:
    i = run("""
let o = { greet(name = 'world') { return 'Hello ' + name } }
let v = o.greet()
""")
    assert i.globals.get("v") == "Hello world"


def test_object_method_shorthand_default_param_override() -> None:
    i = run("""
let o = { greet(name = 'world') { return 'Hello ' + name } }
let v = o.greet('SpryCode')
""")
    assert i.globals.get("v") == "Hello SpryCode"


# ---------------------------------------------------------------------------
# FIX 3: MONEY_TYPE in _IDENTIFIER_LIKE
# ---------------------------------------------------------------------------


def test_money_as_class_name() -> None:
    i = run("""
class Money { var amount = 0 }
let m = Money.new()
m.amount = 42
let v = m.amount
""")
    assert i.globals.get("v") == 42


def test_money_class_with_method() -> None:
    i = run("""
class Money {
    var amount = 0
    fn init(a) { self.amount = a }
    fn valueOf() { return self.amount }
}
let m = Money.new(99)
let v = m.valueOf()
""")
    assert i.globals.get("v") == 99


def test_money_container_class() -> None:
    i = run("""
class MoneyContainer { var val = 0 }
let c = MoneyContainer.new()
c.val = 5
let v = c.val
""")
    assert i.globals.get("v") == 5


# ---------------------------------------------------------------------------
# FIX 4: class extends Error
# ---------------------------------------------------------------------------


def test_extends_error_basic() -> None:
    i = run("""
class MyError extends Error {}
let e = MyError.new('oops')
let v = e.message
""")
    # With no init, message field is pre-populated as empty string
    assert isinstance(i.globals.get("v"), str)


def test_extends_error_with_init_super() -> None:
    i = run("""
class AppErr extends Error {
    fn init(msg) { super.init(msg) }
}
let e = AppErr.new('fail')
let v = e.message
""")
    assert i.globals.get("v") == "fail"


def test_extends_error_name_field() -> None:
    i = run("""
class AppErr extends Error {}
let e = AppErr.new('x')
let v = e.name
""")
    assert i.globals.get("v") == "AppErr"


def test_extends_error_stack_field() -> None:
    i = run("""
class AppErr extends Error {
    fn init(msg) { super.init(msg) }
}
let e = AppErr.new('boom')
let v = e.stack
""")
    assert "AppErr" in str(i.globals.get("v"))
    assert "boom" in str(i.globals.get("v"))


def test_instanceof_error_class() -> None:
    i = run("""
class AppErr extends Error {}
let e = AppErr.new('x')
let v = e instanceof Error
""")
    assert i.globals.get("v") is True


def test_instanceof_error_class_with_init() -> None:
    i = run("""
class AppErr extends Error {
    fn init(msg) { super.init(msg) }
}
let e = AppErr.new('fail')
let v = e instanceof Error
""")
    assert i.globals.get("v") is True


def test_extends_error_cause_field() -> None:
    i = run("""
class AppErr extends Error {}
let e = AppErr.new('x')
let v = e.cause
""")
    assert i.globals.get("v") is None


# ---------------------------------------------------------------------------
# FIX 5: structuredClone Map/Set
# ---------------------------------------------------------------------------


def test_structured_clone_map_isolation() -> None:
    i = run("""
let m = Map.new([['a',1]])
let m2 = structuredClone(m)
m2.set('b', 2)
let v = m.size
""")
    assert i.globals.get("v") == 1


def test_structured_clone_map_has_data() -> None:
    i = run("""
let m = Map.new([['a',1],['b',2]])
let m2 = structuredClone(m)
let v = m2.get('a')
""")
    assert i.globals.get("v") == 1


def test_structured_clone_set_isolation() -> None:
    i = run("""
let s = Set.new([1,2,3])
let s2 = structuredClone(s)
s2.add(4)
let v = s.size
""")
    assert i.globals.get("v") == 3


def test_structured_clone_set_has_data() -> None:
    i = run("""
let s = Set.new([10,20,30])
let s2 = structuredClone(s)
let v = s2.has(20)
""")
    assert i.globals.get("v") is True


def test_structured_clone_list_isolation() -> None:
    i = run("""
let a = [1,[2,3]]
let b = structuredClone(a)
b[1].push(99)
let v = len(a[1])
""")
    assert i.globals.get("v") == 2


def test_structured_clone_nested_map() -> None:
    i = run("""
let m = Map.new([['k', [1,2,3]]])
let m2 = structuredClone(m)
m2.get('k').push(4)
let v = len(m.get('k'))
""")
    assert i.globals.get("v") == 3


# ---------------------------------------------------------------------------
# FIX 6: Switch case { } block bodies
# ---------------------------------------------------------------------------


def test_switch_case_brace_body() -> None:
    i = run("""
var v = 0
switch 2 {
    case 1: { v = 10 }
    case 2: { v = 20 }
    case 3: { v = 30 }
}
""")
    assert i.globals.get("v") == 20


def test_switch_default_brace_body() -> None:
    i = run("""
var v = 0
switch 5 {
    case 1: { v = 10 }
    default: { v = 99 }
}
""")
    assert i.globals.get("v") == 99


def test_switch_string_case_brace_body() -> None:
    i = run("""
var v = 0
switch 'b' {
    case 'a': { v = 1 }
    case 'b': { v = 2 }
    case 'c': { v = 3 }
}
""")
    assert i.globals.get("v") == 2


def test_switch_case_brace_multiple_stmts() -> None:
    i = run("""
var x = 0
var y = 0
switch 1 {
    case 1: {
        x = 10
        y = 20
    }
    case 2: { x = 99 }
}
let v = x + y
""")
    assert i.globals.get("v") == 30


def test_switch_no_match_brace_body() -> None:
    i = run("""
var v = 0
switch 9 {
    case 1: { v = 10 }
    case 2: { v = 20 }
}
""")
    assert i.globals.get("v") == 0
