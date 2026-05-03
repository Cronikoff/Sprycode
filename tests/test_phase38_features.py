"""Phase 38 feature tests.

Covers:
- Single-line ``if`` / ``else`` body without braces (JS/C style)
  e.g. ``if (x < 0) throw new Error('neg')``  /  ``if (x) return x; else return 0``
- ``new WeakMap()`` and ``new WeakSet()`` constructor syntax (``__call__`` on namespaces)
- ``null.property`` access raises ``TypeError`` (SpryErrorObject) catchable via try/catch
  with correct ``name``, ``message``, and ``instanceof`` semantics
- SpryCode-specific keywords (``timeout``, ``sleep``, ``retry``, ``daily``, etc.) usable
  as static class field names and as object property keys
- ``Object.freeze`` — property writes on a frozen dict are silently ignored
- ``while`` with single-statement body (brace-free)
- Labeled ``for`` loop with single-statement ``if`` body containing ``break label``
"""

from __future__ import annotations

from typing import Any

import pytest

from sprycode.interpreter import Interpreter
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
# Single-line if / else body (no braces)
# ---------------------------------------------------------------------------

class TestSingleLineIf:
    def test_throw_in_single_if(self):
        src = "fn f(x) { if (x < 0) throw new Error('neg'); return x }; let v = f(5)"
        assert val(src) == 5

    def test_throw_in_single_if_caught(self):
        src = "fn f(x) { if (x < 0) throw new Error('neg'); return x }; var v = false; try { f(-1) } catch(e) { v = true }"
        assert val(src) is True

    def test_return_in_single_if(self):
        src = "fn f(x) { if (x > 0) return x; return 0 }; let v = f(5)"
        assert val(src) == 5

    def test_return_in_single_if_fallthrough(self):
        src = "fn f(x) { if (x > 0) return x; return 0 }; let v = f(-1)"
        assert val(src) == 0

    def test_assignment_in_single_if(self):
        src = "var c = 0; if (true) c = 1; let v = c"
        assert val(src) == 1

    def test_assignment_in_single_if_false(self):
        src = "var c = 0; if (false) c = 1; let v = c"
        assert val(src) == 0

    def test_return_in_single_else(self):
        src = "fn f(x) { if (x > 0) return x; else return 0 }; let v = f(-1)"
        assert val(src) == 0

    def test_return_in_single_else_true_branch(self):
        src = "fn f(x) { if (x > 0) return x; else return 0 }; let v = f(7)"
        assert val(src) == 7

    def test_else_if_chain_single_line(self):
        src = "fn g(x) { if (x > 0) return 1; else if (x < 0) return -1; else return 0 }; let v = g(-5)"
        assert val(src) == -1

    def test_else_if_chain_zero(self):
        src = "fn g(x) { if (x > 0) return 1; else if (x < 0) return -1; else return 0 }; let v = g(0)"
        assert val(src) == 0

    def test_single_if_no_parens(self):
        # SpryCode also supports if without parentheses
        src = "var c = 0; if true c = 1; let v = c"
        assert val(src) == 1

    def test_nested_single_if(self):
        src = "fn f(x, y) { if (x > 0) if (y > 0) return 2; return 0 }; let v = f(1, 1)"
        assert val(src) == 2

    def test_single_if_with_semicolons(self):
        src = "var a = 0; var b = 0; if (true) a = 1; if (false) b = 1; let v = a + b"
        assert val(src) == 1


# ---------------------------------------------------------------------------
# Single-line while body
# ---------------------------------------------------------------------------

class TestSingleLineWhile:
    def test_while_single_increment(self):
        src = "var i = 0; while (i < 5) i = i + 1; let v = i"
        assert val(src) == 5

    def test_while_single_break(self):
        src = "var i = 0; while (true) { i = i + 1; if (i >= 3) break }; let v = i"
        assert val(src) == 3


# ---------------------------------------------------------------------------
# Labeled for loop with single-line if body
# ---------------------------------------------------------------------------

class TestLabeledForSingleIf:
    def test_labeled_break_single_if(self):
        src = """
var v = 0
outer: for (let i = 0; i < 3; i++) {
  for (let j = 0; j < 3; j++) {
    if (j == 1) break outer
    v = v + 1
  }
}
"""
        assert val(src) == 1

    def test_labeled_continue_single_if(self):
        src = """
var v = 0
outer: for (let i = 0; i < 3; i++) {
  for (let j = 0; j < 2; j++) {
    if (j == 1) continue outer
    v = v + 1
  }
}
"""
        assert val(src) == 3


# ---------------------------------------------------------------------------
# new WeakMap() / new WeakSet() constructor syntax
# ---------------------------------------------------------------------------

class TestWeakMapConstructor:
    def test_new_weakmap_set_get(self):
        src = "let wm = new WeakMap(); let k = {}; wm.set(k, 42); let v = wm.get(k)"
        assert val(src) == 42

    def test_new_weakmap_has(self):
        src = "let wm = new WeakMap(); let k = {}; wm.set(k, 1); let v = wm.has(k)"
        assert val(src) is True

    def test_new_weakmap_has_missing(self):
        src = "let wm = new WeakMap(); let k = {}; let v = wm.has(k)"
        assert val(src) is False

    def test_new_weakmap_delete(self):
        src = "let wm = new WeakMap(); let k = {}; wm.set(k, 1); wm.delete(k); let v = wm.has(k)"
        assert val(src) is False

    def test_new_weakmap_get_missing(self):
        src = "let wm = new WeakMap(); let k = {}; let v = wm.get(k)"
        assert val(src) is None

    def test_weakmap_new_method(self):
        # WeakMap.new() — alternate creation syntax
        src = "let wm = WeakMap.new(); let k = {}; wm.set(k, 99); let v = wm.get(k)"
        assert val(src) == 99


class TestWeakSetConstructor:
    def test_new_weakset_add_has(self):
        src = "let ws = new WeakSet(); let k = {}; ws.add(k); let v = ws.has(k)"
        assert val(src) is True

    def test_new_weakset_has_missing(self):
        src = "let ws = new WeakSet(); let k = {}; let v = ws.has(k)"
        assert val(src) is False

    def test_new_weakset_delete(self):
        src = "let ws = new WeakSet(); let k = {}; ws.add(k); ws.delete(k); let v = ws.has(k)"
        assert val(src) is False

    def test_weakset_new_method(self):
        src = "let ws = WeakSet.new(); let k = {}; ws.add(k); let v = ws.has(k)"
        assert val(src) is True


# ---------------------------------------------------------------------------
# null.property → TypeError
# ---------------------------------------------------------------------------

class TestNullPropertyTypeError:
    def test_null_property_name(self):
        src = "var v = null; try { null.x } catch(e) { v = e.name }"
        assert val(src) == "TypeError"

    def test_null_property_message(self):
        src = "var v = null; try { null.x } catch(e) { v = e.message }"
        assert val(src) == "Cannot read properties of null (reading 'x')"

    def test_null_property_instanceof_typeerror(self):
        src = "var v = null; try { null.x } catch(e) { v = e instanceof TypeError }"
        assert val(src) is True

    def test_null_property_instanceof_error(self):
        src = "var v = null; try { null.x } catch(e) { v = e instanceof Error }"
        assert val(src) is True

    def test_null_property_stack(self):
        src = "var v = null; try { null.x } catch(e) { v = typeof e.stack }"
        # stack is a string (JS typeof: "string")
        assert val(src) == "string"

    def test_null_property_rethrow(self):
        src = "var v = null; try { try { null.x } catch(e) { throw e } } catch(e2) { v = e2.name }"
        assert val(src) == "TypeError"

    def test_null_method_call(self):
        src = "var v = null; try { null.foo() } catch(e) { v = e.name }"
        assert val(src) == "TypeError"

    def test_nonnull_access_ok(self):
        src = "let obj = {x: 42}; let v = obj.x"
        assert val(src) == 42

    def test_undefined_var_access_not_typeerror(self):
        # typeof undeclared → 'undefined' (not a TypeError)
        src = "let v = typeof undeclaredVar"
        assert val(src) == "undefined"


# ---------------------------------------------------------------------------
# SpryCode keywords as class static field names
# ---------------------------------------------------------------------------

class TestKeywordsAsFieldNames:
    def test_static_timeout(self):
        src = "class C { static timeout = 5000 }; let v = C.timeout"
        assert val(src) == 5000

    def test_static_sleep(self):
        src = "class C { static sleep = 100 }; let v = C.sleep"
        assert val(src) == 100

    def test_static_retry(self):
        src = "class C { static retry = 3 }; let v = C.retry"
        assert val(src) == 3

    def test_static_daily(self):
        src = "class C { static daily = true }; let v = C.daily"
        assert val(src) is True

    def test_static_case(self):
        src = "class C { static case = 'A' }; let v = C.case"
        assert val(src) == "A"

    def test_static_scope(self):
        src = "class C { static scope = 'global' }; let v = C.scope"
        assert val(src) == "global"

    def test_static_reason(self):
        src = "class C { static reason = 'test' }; let v = C.reason"
        assert val(src) == "test"

    def test_instance_field_timeout(self):
        src = """
class Timer {
  fn init() { this.timeout = 3000 }
}
let t = Timer.new()
let v = t.timeout
"""
        assert val(src) == 3000

    def test_object_literal_timeout(self):
        src = "let cfg = {timeout: 1000, retry: 5}; let v = cfg.timeout"
        assert val(src) == 1000

    def test_object_literal_retry(self):
        src = "let cfg = {timeout: 1000, retry: 5}; let v = cfg.retry"
        assert val(src) == 5


# ---------------------------------------------------------------------------
# Object.freeze
# ---------------------------------------------------------------------------

class TestObjectFreeze:
    def test_freeze_ignores_write(self):
        src = """
let obj = Object.freeze({x: 1})
obj.x = 99
let v = obj.x
"""
        assert val(src) == 1

    def test_freeze_ignores_new_prop(self):
        src = """
let obj = Object.freeze({x: 1})
obj.y = 2
let v = obj.y
"""
        assert val(src) is None

    def test_freeze_returns_object(self):
        src = "let obj = Object.freeze({x: 1}); let v = obj.x"
        assert val(src) == 1

    def test_isFrozen_true(self):
        src = "let obj = Object.freeze({x: 1}); let v = Object.isFrozen(obj)"
        assert val(src) is True

    def test_isFrozen_false(self):
        src = "let obj = {x: 1}; let v = Object.isFrozen(obj)"
        assert val(src) is False
