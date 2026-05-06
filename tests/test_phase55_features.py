"""Phase 55 feature tests — btoa/atob globals, coercive isNaN/isFinite,
Promise.try, Promise.state/reason, Promise.withResolvers."""
import pytest
from sprycode.lexer import Lexer
from sprycode.parser import Parser
from sprycode.interpreter import Interpreter


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(src: str, name: str = "v"):
    return run(src).globals.get(name)


# ---------------------------------------------------------------------------
# btoa / atob
# ---------------------------------------------------------------------------

class TestBtoaAtob:
    def test_btoa(self):
        assert val('let v = btoa("hello")') == "aGVsbG8="

    def test_atob(self):
        assert val('let v = atob("aGVsbG8=")') == "hello"

    def test_roundtrip(self):
        assert val('let v = atob(btoa("SpryCode"))') == "SpryCode"


# ---------------------------------------------------------------------------
# Coercive isNaN / isFinite
# ---------------------------------------------------------------------------

class TestCoerciveChecks:
    def test_isnan_number(self):
        assert val('let v = isNaN(NaN)') is True

    def test_isnan_string_numeric(self):
        # coercive: isNaN("123") → false (123 is not NaN)
        assert val('let v = isNaN("123")') is False

    def test_isnan_string_non_numeric(self):
        assert val('let v = isNaN("hello")') is True

    def test_isfinite_number(self):
        assert val('let v = isFinite(42)') is True

    def test_isfinite_infinity(self):
        assert val('let v = isFinite(Infinity)') is False

    def test_isfinite_string(self):
        assert val('let v = isFinite("3.14")') is True


# ---------------------------------------------------------------------------
# Promise.try
# ---------------------------------------------------------------------------

class TestPromiseTry:
    def test_promise_try_success(self):
        src = """
let p = Promise["try"](() => 42)
let v = p.value
"""
        assert val(src) == 42

    def test_promise_try_error(self):
        src = """
let p = Promise["try"](() => { throw "oops" })
let v = p.status
"""
        assert val(src) == "rejected"


# ---------------------------------------------------------------------------
# Promise.state / .reason
# ---------------------------------------------------------------------------

class TestPromiseStateReason:
    def test_fulfilled_state(self):
        src = """
let p = Promise.resolve(42)
let v = p.state
"""
        assert val(src) == "fulfilled"

    def test_rejected_state(self):
        src = """
let p = Promise.reject("err")
let v = p.state
"""
        assert val(src) == "rejected"

    def test_rejected_reason(self):
        src = """
let p = Promise.reject("my error")
let v = p.reason
"""
        assert val(src) == "my error"
