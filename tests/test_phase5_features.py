"""
Tests for Phase 5 language features:
  - try/catch/finally
  - do/while loop
  - typeof operator
  - instanceof operator
  - debit/credit in transaction blocks
  - websocket statement
  - spawn statement
  - with/using statement
"""

import pytest

from sprycode.interpreter import Interpreter, SpryWebSocket
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
# try / catch / finally
# ---------------------------------------------------------------------------


class TestTryFinally:
    def test_finally_runs_on_success(self):
        src = "var v = 0\ntry { v = 1 } catch e { v = 99 } finally { v = v + 10 }"
        i = run(src)
        assert val(i, "v") == 11

    def test_finally_runs_on_error(self):
        src = "var v = 0\ntry { throw \"oops\" } catch e { v = 2 } finally { v = v + 10 }"
        i = run(src)
        assert val(i, "v") == 12

    def test_finally_without_catch(self):
        src = "var v = 0\ntry { v = 5 } finally { v = v + 1 }"
        i = run(src)
        assert val(i, "v") == 6

    def test_finally_runs_even_on_throw(self):
        src = """var v = 0
try {
  throw "err"
} catch e {
  v = 1
} finally {
  v = v + 100
}"""
        i = run(src)
        assert val(i, "v") == 101

    def test_catch_only_still_works(self):
        src = "var v = 0\ntry { throw \"oops\" } catch e { v = 42 }"
        i = run(src)
        assert val(i, "v") == 42

    def test_try_catch_error_binding(self):
        src = 'var msg = ""\ntry { throw "test error" } catch e { msg = e }'
        i = run(src)
        assert val(i, "msg") == "test error"

    def test_finally_does_not_interfere_with_return(self):
        src = """fn f() {
  try {
    return 10
  } finally {
    let x = 99
  }
}
let v = f()"""
        i = run(src)
        assert val(i, "v") == 10

    def test_nested_try_finally(self):
        src = """var v = 0
try {
  try { v = 1 } finally { v = v + 1 }
} finally {
  v = v + 10
}"""
        i = run(src)
        assert val(i, "v") == 12


# ---------------------------------------------------------------------------
# do / while loop
# ---------------------------------------------------------------------------


class TestDoWhile:
    def test_basic_do_while(self):
        i = run("var i = 0\ndo { i = i + 1 } while i < 5\nlet v = i")
        assert val(i, "v") == 5

    def test_body_runs_at_least_once(self):
        i = run("var i = 0\ndo { i = i + 1 } while false\nlet v = i")
        assert val(i, "v") == 1

    def test_condition_checked_after_body(self):
        # Even when condition is false from the start, body runs once
        i = run("var i = 100\ndo { i = i + 1 } while i < 5\nlet v = i")
        assert val(i, "v") == 101

    def test_break_in_do_while(self):
        i = run("var i = 0\ndo { i = i + 1\n if i == 3 { break } } while i < 10\nlet v = i")
        assert val(i, "v") == 3

    def test_continue_in_do_while(self):
        src = """var sum = 0
var i = 0
do {
  i = i + 1
  if i % 2 == 0 { continue }
  sum = sum + i
} while i < 10
let v = sum"""
        i = run(src)
        # Sum of odd numbers 1,3,5,7,9 = 25
        assert val(i, "v") == 25

    def test_do_while_accumulate(self):
        i = run("var product = 1\nvar n = 1\ndo { product = product * n\n n = n + 1 } while n <= 5\nlet v = product")
        assert val(i, "v") == 120  # 5!

    def test_do_while_string_building(self):
        i = run('var s = ""\nvar i = 0\ndo { s = s + \"x\"\n i = i + 1 } while i < 4\nlet v = s')
        assert val(i, "v") == "xxxx"


# ---------------------------------------------------------------------------
# typeof operator
# ---------------------------------------------------------------------------


class TestTypeof:
    def test_typeof_int(self):
        i = run("let v = typeof 42")
        assert val(i, "v") == "number"

    def test_typeof_float(self):
        i = run("let v = typeof 3.14")
        assert val(i, "v") == "number"

    def test_typeof_text(self):
        i = run('let v = typeof "hello"')
        assert val(i, "v") == "string"

    def test_typeof_bool_true(self):
        i = run("let v = typeof true")
        assert val(i, "v") == "boolean"

    def test_typeof_bool_false(self):
        i = run("let v = typeof false")
        assert val(i, "v") == "boolean"

    def test_typeof_null(self):
        i = run("let v = typeof null")
        assert val(i, "v") == "object"

    def test_typeof_list(self):
        i = run("let v = typeof [1,2,3]")
        assert val(i, "v") == "object"

    def test_typeof_object(self):
        i = run("let v = typeof {a:1}")
        assert val(i, "v") == "object"

    def test_typeof_function(self):
        i = run("fn f() { return 1 }\nlet v = typeof f")
        assert val(i, "v") == "function"

    def test_typeof_anon_fn(self):
        i = run("let f = fn(x) => x\nlet v = typeof f")
        assert val(i, "v") == "function"

    def test_typeof_in_condition(self):
        i = run('let x = 42\nvar v = "no"\nif typeof x == "number" { v = "yes" }')
        assert val(i, "v") == "yes"

    def test_typeof_variable(self):
        i = run('let s = "world"\nlet v = typeof s')
        assert val(i, "v") == "string"


# ---------------------------------------------------------------------------
# instanceof operator
# ---------------------------------------------------------------------------


class TestInstanceof:
    def test_instanceof_int(self):
        i = run("let v = 42 instanceof Int")
        assert val(i, "v") is True

    def test_instanceof_float(self):
        i = run("let v = 3.14 instanceof Float")
        assert val(i, "v") is True

    def test_instanceof_text(self):
        i = run('let v = "hi" instanceof Text')
        assert val(i, "v") is True

    def test_instanceof_bool(self):
        i = run("let v = true instanceof Bool")
        assert val(i, "v") is True

    def test_instanceof_list(self):
        i = run("let v = [1,2,3] instanceof List")
        assert val(i, "v") is True

    def test_instanceof_object(self):
        i = run("let v = {a:1} instanceof Object")
        assert val(i, "v") is True

    def test_instanceof_number_int(self):
        i = run("let v = 42 instanceof Number")
        assert val(i, "v") is True

    def test_instanceof_number_float(self):
        i = run("let v = 3.14 instanceof Number")
        assert val(i, "v") is True

    def test_instanceof_false(self):
        i = run("let v = 42 instanceof Text")
        assert val(i, "v") is False

    def test_instanceof_in_if(self):
        i = run('var v = "no"\nif 99 instanceof Int { v = "yes" }')
        assert val(i, "v") == "yes"

    def test_instanceof_function(self):
        i = run("fn f() { return 1 }\nlet v = f instanceof Function")
        assert val(i, "v") is True


# ---------------------------------------------------------------------------
# debit / credit in transaction blocks
# ---------------------------------------------------------------------------


class TestDebitCredit:
    def test_debit_executes(self):
        src = 'transaction db { debit account "A" amount 100 }'
        # Should not raise
        run(src)

    def test_credit_executes(self):
        src = 'transaction db { credit account "B" amount 100 }'
        run(src)

    def test_debit_credit_combined(self):
        src = """transaction db {
  debit account "A" amount 50
  credit account "B" amount 50
  compensate { log info "rolling back" }
}"""
        run(src)

    def test_debit_returns_record(self):
        src = 'var r = null\ntransaction db { r = debit account "A" amount 75 }'
        i = run(src)
        r = val(i, "r")
        assert isinstance(r, dict)
        assert r.get("type") == "debit"
        assert r.get("amount") == 75

    def test_credit_returns_record(self):
        src = 'var r = null\ntransaction db { r = credit account "B" amount 25 }'
        i = run(src)
        r = val(i, "r")
        assert isinstance(r, dict)
        assert r.get("type") == "credit"
        assert r.get("amount") == 25

    def test_debit_without_account_keyword(self):
        # debit "A" amount 100 (no 'account' keyword)
        src = 'transaction db { debit "A" amount 100 }'
        run(src)

    def test_multiple_debits(self):
        src = """var total = 0
transaction db {
  let d1 = debit account "A" amount 10
  let d2 = debit account "B" amount 20
  total = d1.amount + d2.amount
}"""
        i = run(src)
        assert val(i, "total") == 30


# ---------------------------------------------------------------------------
# websocket statement
# ---------------------------------------------------------------------------


class TestWebSocket:
    def test_websocket_creates_object(self):
        i = run('websocket ws "ws://example.com" {}')
        ws = val(i, "ws")
        assert isinstance(ws, SpryWebSocket)

    def test_websocket_url_property(self):
        i = run('websocket ws "ws://localhost:8080/socket" {}\nlet v = ws.url')
        assert val(i, "v") == "ws://localhost:8080/socket"

    def test_websocket_connected_property(self):
        i = run('websocket ws "ws://example.com" {}\nlet v = ws.connected')
        assert val(i, "v") is True

    def test_websocket_send(self):
        out = run_output('websocket ws "ws://example.com" {}\nws.send("hello")')
        assert any("hello" in str(o) for o in out)

    def test_websocket_close(self):
        src = 'websocket ws "ws://example.com" {}\nws.close()\nlet v = ws.connected'
        i = run(src)
        assert val(i, "v") is False

    def test_websocket_body_executes(self):
        src = 'var v = 0\nwebsocket ws "ws://example.com" { v = 42 }'
        i = run(src)
        assert val(i, "v") == 42

    def test_websocket_onmessage(self):
        src = 'websocket ws "ws://example.com" {}\nws.onMessage(fn(msg) => msg)\nlet v = ws.connected'
        i = run(src)
        assert val(i, "v") is True


# ---------------------------------------------------------------------------
# spawn statement
# ---------------------------------------------------------------------------


class TestSpawn:
    def test_spawn_basic(self):
        # spawn should not block and not propagate errors
        i = run("fn f() { return 42 }\nspawn f()\nlet v = 1")
        assert val(i, "v") == 1

    def test_spawn_does_not_crash_on_error(self):
        # Spawned call that throws should not propagate
        i = run('fn f() { throw "oops" }\nspawn f()\nlet v = 1')
        assert val(i, "v") == 1

    def test_spawn_lambda(self):
        i = run("spawn fn() { let x = 1 }()\nlet v = 2")
        assert val(i, "v") == 2

    def test_spawn_with_args(self):
        i = run("fn f(x) { return x * 2 }\nspawn f(5)\nlet v = 3")
        assert val(i, "v") == 3


# ---------------------------------------------------------------------------
# with / using statement
# ---------------------------------------------------------------------------


class TestWith:
    def test_with_no_alias(self):
        src = "var v = 0\nwith {x: 1} { v = 1 }"
        i = run(src)
        assert val(i, "v") == 1

    def test_with_alias(self):
        src = "var v = null\nwith {x: 42} as obj { v = obj.x }"
        i = run(src)
        assert val(i, "v") == 42

    def test_with_sql_connect(self):
        src = """var v = 0
with sql.connect(":memory:") as db {
  v = 1
}"""
        i = run(src)
        assert val(i, "v") == 1

    def test_with_closes_resource(self):
        src = """var v = 0
with sql.connect(":memory:") as db {
  v = 1
}
let done = v"""
        i = run(src)
        assert val(i, "done") == 1

    def test_with_body_can_access_outer_vars(self):
        src = """var total = 0
let nums = [1,2,3]
with nums as list {
  for x in list { total = total + x }
}"""
        i = run(src)
        assert val(i, "total") == 6

    def test_with_multiple_statements(self):
        src = """var a = 0
var b = 0
with {val: 5} as r {
  a = r.val
  b = r.val * 2
}"""
        i = run(src)
        assert val(i, "a") == 5
        assert val(i, "b") == 10


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_do_while_with_typeof(self):
        src = """var items = [1, "two", 3, "four", 5]
var idx = 0
var count_nums = 0
do {
  if typeof items[idx] == "number" { count_nums = count_nums + 1 }
  idx = idx + 1
} while idx < 5
let v = count_nums"""
        i = run(src)
        assert val(i, "v") == 3

    def test_try_finally_with_do_while(self):
        src = """var v = 0
var i = 0
try {
  do {
    i = i + 1
    v = v + i
  } while i < 5
} finally {
  v = v + 100
}"""
        i = run(src)
        assert val(i, "v") == 115  # 1+2+3+4+5=15 + 100

    def test_typeof_in_switch(self):
        src = """fn describe(x) {
  switch typeof x {
    case "number": return "integer"
    case "string": return "string"
    case "boolean": return "boolean"
    default: return "other"
  }
}
let v = [describe(1), describe("hi"), describe(true), describe([1,2])]"""
        i = run(src)
        assert val(i, "v") == ["integer", "string", "boolean", "other"]

    def test_instanceof_in_list_comprehension(self):
        i = run("let mixed = [1, \"a\", 2, \"b\", 3]\nlet v = [x for x in mixed if x instanceof Int]")
        assert val(i, "v") == [1, 2, 3]
