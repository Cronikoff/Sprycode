"""Tests for Phase 91: Error Types Advanced
- TypeError, RangeError, ReferenceError, SyntaxError, URIError, EvalError instances
- instanceof checks, name/message properties
- Custom error classes, AggregateError
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


# ── TypeError ──────────────────────────────────────────────────────────────────

class TestTypeError:
    def test_create(self):
        i = run('let v = new TypeError("bad type")')
        assert val(i) is not None

    def test_message(self):
        i = run('let err = new TypeError("bad type"); let v = err.message')
        assert val(i) == "bad type"

    def test_name(self):
        i = run('let err = new TypeError("msg"); let v = err.name')
        assert val(i) == "TypeError"

    def test_instanceof_TypeError(self):
        i = run('let err = new TypeError("msg"); let v = err instanceof TypeError')
        assert val(i) is True

    def test_instanceof_Error(self):
        i = run('let err = new TypeError("msg"); let v = err instanceof Error')
        assert val(i) is True

    def test_caught_in_try(self):
        i = run('''
let v = null;
try { throw new TypeError("oops"); }
catch(e) { v = e.message; }
''')
        assert val(i) == "oops"

    def test_rethrow_preserves_type(self):
        i = run('''
let v = false;
try {
  try { throw new TypeError("t"); }
  catch(e) { throw e; }
} catch(e) {
  v = e instanceof TypeError;
}
''')
        assert val(i) is True


# ── RangeError ─────────────────────────────────────────────────────────────────

class TestRangeError:
    def test_create(self):
        i = run('let v = new RangeError("out of range")')
        assert val(i) is not None

    def test_message(self):
        i = run('let err = new RangeError("out of range"); let v = err.message')
        assert val(i) == "out of range"

    def test_name(self):
        i = run('let err = new RangeError("x"); let v = err.name')
        assert val(i) == "RangeError"

    def test_instanceof_RangeError(self):
        i = run('let err = new RangeError("x"); let v = err instanceof RangeError')
        assert val(i) is True

    def test_instanceof_Error(self):
        i = run('let err = new RangeError("x"); let v = err instanceof Error')
        assert val(i) is True

    def test_caught_in_try(self):
        i = run('''
let v = null;
try { throw new RangeError("range!"); }
catch(e) { v = e.name; }
''')
        assert val(i) == "RangeError"


# ── ReferenceError ─────────────────────────────────────────────────────────────

class TestReferenceError:
    def test_create(self):
        i = run('let v = new ReferenceError("not defined")')
        assert val(i) is not None

    def test_message(self):
        i = run('let err = new ReferenceError("not defined"); let v = err.message')
        assert val(i) == "not defined"

    def test_name(self):
        i = run('let err = new ReferenceError("x"); let v = err.name')
        assert val(i) == "ReferenceError"

    def test_instanceof(self):
        i = run('let err = new ReferenceError("x"); let v = err instanceof ReferenceError')
        assert val(i) is True

    def test_instanceof_Error(self):
        i = run('let err = new ReferenceError("x"); let v = err instanceof Error')
        assert val(i) is True


# ── SyntaxError ────────────────────────────────────────────────────────────────

class TestSyntaxError:
    def test_create(self):
        i = run('let v = new SyntaxError("bad syntax")')
        assert val(i) is not None

    def test_message(self):
        i = run('let err = new SyntaxError("bad syntax"); let v = err.message')
        assert val(i) == "bad syntax"

    def test_name(self):
        i = run('let err = new SyntaxError("x"); let v = err.name')
        assert val(i) == "SyntaxError"

    def test_instanceof(self):
        i = run('let err = new SyntaxError("x"); let v = err instanceof SyntaxError')
        assert val(i) is True


# ── URIError ───────────────────────────────────────────────────────────────────

class TestURIError:
    def test_create(self):
        i = run('let v = new URIError("bad uri")')
        assert val(i) is not None

    def test_message(self):
        i = run('let err = new URIError("bad uri"); let v = err.message')
        assert val(i) == "bad uri"

    def test_name(self):
        i = run('let err = new URIError("x"); let v = err.name')
        assert val(i) == "URIError"

    def test_instanceof(self):
        i = run('let err = new URIError("x"); let v = err instanceof URIError')
        assert val(i) is True


# ── EvalError ─────────────────────────────────────────────────────────────────

class TestEvalError:
    def test_create(self):
        i = run('let v = new EvalError("eval error")')
        assert val(i) is not None

    def test_message(self):
        i = run('let err = new EvalError("eval error"); let v = err.message')
        assert val(i) == "eval error"

    def test_name(self):
        i = run('let err = new EvalError("x"); let v = err.name')
        assert val(i) == "EvalError"

    def test_instanceof(self):
        i = run('let err = new EvalError("x"); let v = err instanceof EvalError')
        assert val(i) is True


# ── Error.isError ──────────────────────────────────────────────────────────────

class TestErrorIsError:
    def test_isError_Error(self):
        i = run('let err = new Error("m"); let v = Error.isError(err)')
        assert val(i) is True

    def test_isError_TypeError(self):
        i = run('let err = new TypeError("m"); let v = Error.isError(err)')
        assert val(i) is True

    def test_isError_RangeError(self):
        i = run('let err = new RangeError("m"); let v = Error.isError(err)')
        assert val(i) is True

    def test_isError_number(self):
        i = run('let v = Error.isError(42)')
        assert val(i) is False

    def test_isError_string(self):
        i = run('let v = Error.isError("hello")')
        assert val(i) is False

    def test_isError_null(self):
        i = run('let v = Error.isError(null)')
        assert val(i) is False

    def test_isError_object(self):
        i = run('let v = Error.isError({message: "x"})')
        assert val(i) is False


# ── Custom Error Classes ───────────────────────────────────────────────────────

class TestCustomError:
    def test_custom_error_message(self):
        i = run('''
class MyError extends Error {
  constructor(msg) { super(msg); this.name = "MyError"; }
}
let err = new MyError("oops");
let v = err.message;
''')
        assert val(i) == "oops"

    def test_custom_error_name(self):
        i = run('''
class MyError extends Error {
  constructor(msg) { super(msg); this.name = "MyError"; }
}
let err = new MyError("oops");
let v = err.name;
''')
        assert val(i) == "MyError"

    def test_custom_instanceof_Error(self):
        i = run('''
class MyError extends Error {
  constructor(msg) { super(msg); }
}
let err = new MyError("oops");
let v = err instanceof Error;
''')
        assert val(i) is True

    def test_custom_extra_field(self):
        i = run('''
class AppError extends Error {
  constructor(msg, code) {
    super(msg);
    this.code = code;
  }
}
let err = new AppError("not found", 404);
let v = err.code;
''')
        assert val(i) == 404

    def test_custom_caught_in_try(self):
        i = run('''
class AppError extends Error {
  constructor(msg) { super(msg); this.name = "AppError"; }
}
let v = null;
try { throw new AppError("fail"); }
catch(e) { v = e.name; }
''')
        assert val(i) == "AppError"

    def test_custom_extra_field_accessed(self):
        i = run('''
class HttpError extends Error {
  constructor(msg, status) {
    super(msg);
    this.status = status;
  }
}
let err = new HttpError("forbidden", 403);
let v = err.status;
''')
        assert val(i) == 403

    def test_custom_instanceof_custom(self):
        i = run('''
class MyError extends Error {
  constructor(msg) { super(msg); }
}
let err = new MyError("x");
let v = err instanceof MyError;
''')
        assert val(i) is True

    def test_rethrow_preserves_custom_type(self):
        i = run('''
class MyError extends Error {
  constructor(msg) { super(msg); }
}
let v = false;
try {
  try { throw new MyError("bad"); }
  catch(e) { throw e; }
} catch(e) {
  v = e instanceof MyError;
}
''')
        assert val(i) is True


# ── AggregateError ─────────────────────────────────────────────────────────────

class TestAggregateError:
    def test_create(self):
        i = run('''
let e1 = new Error("a");
let e2 = new Error("b");
let v = new AggregateError([e1, e2], "multi");
''')
        assert val(i) is not None

    def test_errors_length(self):
        i = run('''
let e1 = new Error("a");
let e2 = new Error("b");
let agg = new AggregateError([e1, e2], "multi");
let v = agg.errors.length;
''')
        assert val(i) == 2

    def test_errors_first_message(self):
        i = run('''
let e1 = new Error("first");
let e2 = new Error("second");
let agg = new AggregateError([e1, e2], "multi");
let v = agg.errors[0].message;
''')
        assert val(i) == "first"

    def test_message(self):
        i = run('''
let agg = new AggregateError([new Error("x")], "aggregate message");
let v = agg.message;
''')
        assert val(i) == "aggregate message"

    def test_three_errors(self):
        i = run('''
let errors = [new Error("a"), new Error("b"), new Error("c")];
let agg = new AggregateError(errors, "three");
let v = agg.errors.length;
''')
        assert val(i) == 3
