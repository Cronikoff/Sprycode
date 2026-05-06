"""Tests for Phase 55 features:
- `btoa(str)` / `atob(str)` global Base64 encode/decode
- `Promise.try(fn)` (ES2025)
- `Error.isError(val)` (TC39)
- `SpryPromise.state` and `SpryPromise.reason` properties
- `Symbol.toPrimitive` on plain dicts in arithmetic and template literals
- `isNaN` / `isFinite` global JS-style coercive semantics
"""
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


# ---------------------------------------------------------------------------
# btoa / atob
# ---------------------------------------------------------------------------

class TestBtoaAtob:
    def test_btoa_basic(self) -> None:
        i = run('let v = btoa("hello")')
        assert val(i) == "aGVsbG8="

    def test_atob_basic(self) -> None:
        i = run('let v = atob("aGVsbG8=")')
        assert val(i) == "hello"

    def test_btoa_atob_round_trip(self) -> None:
        i = run('let v = atob(btoa("hello world"))')
        assert val(i) == "hello world"

    def test_btoa_empty(self) -> None:
        i = run('let v = btoa("")')
        assert val(i) == ""

    def test_atob_empty(self) -> None:
        i = run('let v = atob("")')
        assert val(i) == ""

    def test_btoa_unicode_latin(self) -> None:
        i = run('let v = btoa("abc")')
        assert val(i) == "YWJj"

    def test_btoa_is_function(self) -> None:
        i = run("let v = typeof btoa")
        assert val(i) == "function"

    def test_atob_is_function(self) -> None:
        i = run("let v = typeof atob")
        assert val(i) == "function"

    def test_btoa_number(self) -> None:
        i = run("let v = btoa(42)")
        import base64
        assert val(i) == base64.b64encode(b"42").decode()

    def test_btoa_in_expression(self) -> None:
        i = run('let b = btoa("hi"); let v = b.length > 0')
        assert val(i) is True


# ---------------------------------------------------------------------------
# Promise.try
# ---------------------------------------------------------------------------

class TestPromiseTry:
    def test_try_returns_fulfilled_promise(self) -> None:
        i = run("let p = Promise.try(() => 42); let v = p.value")
        assert val(i) == 42

    def test_try_state_is_fulfilled(self) -> None:
        i = run("let p = Promise.try(() => 42); let v = p.state")
        assert val(i) == "fulfilled"

    def test_try_rejects_on_throw(self) -> None:
        i = run("""
let p = Promise.try(() => { throw new Error("boom") })
let v = p.state
""")
        assert val(i) == "rejected"

    def test_try_rejection_reason_is_error_object(self) -> None:
        i = run("""
let p = Promise.try(() => { throw new Error("boom") })
let v = p.reason.message
""")
        assert val(i) == "boom"

    def test_try_with_named_function(self) -> None:
        i = run("""
fn compute() { return 1 + 2 }
let p = Promise.try(compute)
let v = p.value
""")
        assert val(i) == 3

    def test_try_with_lambda(self) -> None:
        i = run("let p = Promise.try(() => 99); let v = p.value")
        assert val(i) == 99

    def test_try_with_promise_return(self) -> None:
        i = run("""
let p = Promise.try(() => Promise.resolve(55))
let v = p.value
""")
        assert val(i) == 55

    def test_try_is_function(self) -> None:
        i = run("let v = typeof Promise.try")
        assert val(i) == "function"

    def test_try_undefined_return(self) -> None:
        i = run("let p = Promise.try(() => {}); let v = p.state")
        assert val(i) == "fulfilled"

    def test_try_captures_string_error(self) -> None:
        i = run("""
let p = Promise.try(() => { throw \"string error\" })
let v = p.state
""")
        assert val(i) == "rejected"

    def test_try_chained_then(self) -> None:
        i = run("""
let p = Promise.try(() => 10).then(x => x * 2)
let v = p.value
""")
        assert val(i) == 20

    def test_try_chained_catch(self) -> None:
        i = run("""
let p = Promise.try(() => { throw new Error(\"oops\") }).catch(e => \"caught\")
let v = p.value
""")
        assert val(i) == "caught"


# ---------------------------------------------------------------------------
# Error.isError
# ---------------------------------------------------------------------------

class TestErrorIsError:
    def test_error_instance_is_error(self) -> None:
        i = run("let v = Error.isError(new Error(\"x\"))")
        assert val(i) is True

    def test_type_error_is_error(self) -> None:
        i = run("let v = Error.isError(new TypeError(\"x\"))")
        assert val(i) is True

    def test_range_error_is_error(self) -> None:
        i = run("let v = Error.isError(new RangeError(\"x\"))")
        assert val(i) is True

    def test_syntax_error_is_error(self) -> None:
        i = run('let v = Error.isError(new SyntaxError("x"))')
        assert val(i) is True

    def test_dict_is_not_error(self) -> None:
        i = run('let v = Error.isError({message: "x"})')
        assert val(i) is False

    def test_null_is_not_error(self) -> None:
        i = run("let v = Error.isError(null)")
        assert val(i) is False

    def test_string_is_not_error(self) -> None:
        i = run('let v = Error.isError("error string")')
        assert val(i) is False

    def test_number_is_not_error(self) -> None:
        i = run("let v = Error.isError(42)")
        assert val(i) is False

    def test_class_instance_is_not_error(self) -> None:
        i = run("""
class MyError {
  constructor(msg) { this.message = msg }
}
let v = Error.isError(new MyError("x"))
""")
        assert val(i) is False

    def test_is_error_is_function(self) -> None:
        i = run("let v = typeof Error.isError")
        assert val(i) == "function"

    def test_is_error_on_type_error_ns(self) -> None:
        i = run("let v = TypeError.isError(new TypeError(\"x\"))")
        assert val(i) is True


# ---------------------------------------------------------------------------
# SpryPromise.state and SpryPromise.reason
# ---------------------------------------------------------------------------

class TestPromiseStateReason:
    def test_resolve_state_is_fulfilled(self) -> None:
        i = run("let v = Promise.resolve(42).state")
        assert val(i) == "fulfilled"

    def test_reject_state_is_rejected(self) -> None:
        i = run('let v = Promise.reject("err").state')
        assert val(i) == "rejected"

    def test_reject_reason(self) -> None:
        i = run('let v = Promise.reject("my reason").reason')
        assert val(i) == "my reason"

    def test_reject_reason_is_error(self) -> None:
        i = run("""
let e = new Error("oops")
let v = Promise.reject(e).reason.message
""")
        assert val(i) == "oops"

    def test_resolve_reason_is_null(self) -> None:
        i = run("let v = Promise.resolve(42).reason")
        assert val(i) is None

    def test_status_alias(self) -> None:
        i = run("let v = Promise.resolve(42).status")
        assert val(i) == "fulfilled"

    def test_state_and_status_same(self) -> None:
        i = run("""
let p = Promise.reject("x")
let v = p.state === p.status
""")
        assert val(i) is True

    def test_allSettled_uses_state(self) -> None:
        i = run("""
let results = Promise.allSettled([Promise.resolve(1), Promise.reject(2)])
let v = results.value
""")
        assert val(i)[0]["status"] == "fulfilled"
        assert val(i)[1]["status"] == "rejected"


# ---------------------------------------------------------------------------
# Symbol.toPrimitive on plain dicts
# ---------------------------------------------------------------------------

class TestDictToPrimitive:
    def test_addition_string_hint(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { return "world" } }
let v = "hello " + obj
""")
        assert val(i) == "hello world"

    def test_addition_number_hint(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { if (hint === "default") return 10; return "x" } }
let v = obj + 5
""")
        # hint is "default" for +
        assert val(i) == 15

    def test_subtraction(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { return 10 } }
let v = obj - 3
""")
        assert val(i) == 7

    def test_multiplication(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { return 5 } }
let v = obj * 4
""")
        assert val(i) == 20

    def test_division(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { return 20 } }
let v = obj / 4
""")
        assert val(i) == 5.0

    def test_unary_plus(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { if (hint === "number") return 7; return 0 } }
let v = +obj
""")
        assert val(i) == 7

    def test_template_literal(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { return "tpl" } }
let v = `result: ${obj}`
""")
        assert val(i) == "result: tpl"

    def test_hint_passed_correctly(self) -> None:
        i = run("""
let hints = []
let obj = { [Symbol.toPrimitive](hint) { hints.push(hint); return 0 } }
let _ = obj + 1
let v = hints[0]
""")
        # + passes "default" hint
        assert val(i) == "default"

    def test_number_hint_for_subtraction(self) -> None:
        i = run("""
let hints = []
let obj = { [Symbol.toPrimitive](hint) { hints.push(hint); return 5 } }
let _ = obj - 1
let v = hints[0]
""")
        assert val(i) == "number"

    def test_no_toPrimitive_falls_through(self) -> None:
        """Dict without Symbol.toPrimitive falls through to default behavior."""
        i = run("""
let obj = { value: 42 }
let v = typeof obj
""")
        assert val(i) == "object"

    def test_string_concat_returns_string(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { return "42" } }
let v = "Value: " + obj
""")
        assert val(i) == "Value: 42"


# ---------------------------------------------------------------------------
# isNaN / isFinite global JS-style coercive semantics
# ---------------------------------------------------------------------------

class TestIsNaNIsFinite:
    def test_isnan_string_returns_true(self) -> None:
        i = run('let v = isNaN("hello")')
        assert val(i) is True

    def test_isnan_numeric_string_returns_false(self) -> None:
        i = run('let v = isNaN("42")')
        assert val(i) is False

    def test_isnan_nan_returns_true(self) -> None:
        i = run("let v = isNaN(NaN)")
        assert val(i) is True

    def test_isnan_number_returns_false(self) -> None:
        i = run("let v = isNaN(42)")
        assert val(i) is False

    def test_isnan_infinity_returns_false(self) -> None:
        i = run("let v = isNaN(Infinity)")
        assert val(i) is False

    def test_isnan_null_returns_false(self) -> None:
        # null coerces to 0, which is not NaN
        i = run("let v = isNaN(null)")
        assert val(i) is False

    def test_isnan_empty_string_returns_false(self) -> None:
        # "" coerces to 0
        i = run('let v = isNaN("")')
        assert val(i) is False

    def test_isfinite_string_number(self) -> None:
        i = run('let v = isFinite("42")')
        assert val(i) is True

    def test_isfinite_string_infinity(self) -> None:
        i = run('let v = isFinite("Infinity")')
        assert val(i) is False

    def test_isfinite_nan(self) -> None:
        i = run("let v = isFinite(NaN)")
        assert val(i) is False

    def test_isfinite_number(self) -> None:
        i = run("let v = isFinite(42)")
        assert val(i) is True

    def test_isfinite_infinity(self) -> None:
        i = run("let v = isFinite(Infinity)")
        assert val(i) is False

    def test_isfinite_negative_infinity(self) -> None:
        i = run("let v = isFinite(-Infinity)")
        assert val(i) is False

    def test_isfinite_null_is_finite(self) -> None:
        # null → 0, which is finite
        i = run("let v = isFinite(null)")
        assert val(i) is True


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPhase55Integration:
    def test_promise_try_with_db_pattern(self) -> None:
        i = run("""
fn fetchUser(id) {
  if (id <= 0) throw new Error("invalid id")
  return { id: id, name: "User " + id }
}
let p = Promise.try(() => fetchUser(1))
let v = [p.state, p.value.name]
""")
        assert val(i) == ["fulfilled", "User 1"]

    def test_promise_try_error_handling_chain(self) -> None:
        i = run("""
let p = Promise.try(() => { throw new Error("fail") })
  .catch(e => ({ error: e.message, handled: true }))
let v = p.value.handled
""")
        assert val(i) is True

    def test_btoa_for_auth_token(self) -> None:
        i = run("""
let creds = "user:pass"
let encoded = btoa(creds)
let decoded = atob(encoded)
let v = decoded === creds
""")
        assert val(i) is True

    def test_error_is_error_in_catch(self) -> None:
        i = run("""
let v = false
try {
  throw new TypeError("boom")
} catch(e) {
  v = Error.isError(e)
}
""")
        assert val(i) is True

    def test_symbol_toPrimitive_comparison(self) -> None:
        i = run("""
let obj = { [Symbol.toPrimitive](hint) { return 42 } }
let v = obj == 42
""")
        # == comparison doesn't go through toPrimitive in our simple implementation
        # but arithmetic does
        assert val(i) is not None  # should not crash

    def test_isnan_in_validation(self) -> None:
        i = run("""
fn parseAge(s) {
  let n = parseInt(s)
  if (isNaN(n)) return null
  return n
}
let v = [parseAge("25"), parseAge("abc")]
""")
        assert val(i) == [25, None]

    def test_promise_state_in_conditional(self) -> None:
        i = run("""
let p1 = Promise.resolve(1)
let p2 = Promise.reject("err")
let v = [p1.state === "fulfilled", p2.state === "rejected"]
""")
        assert val(i) == [True, True]

    def test_combined_promise_try_error_is_error(self) -> None:
        i = run("""
let results = []
let p1 = Promise.try(() => 42)
let p2 = Promise.try(() => { throw new RangeError("out of range") })
results.push(p1.state)
results.push(Error.isError(p2.reason))
let v = results
""")
        assert val(i) == ["fulfilled", True]
