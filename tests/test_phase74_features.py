"""Tests for Phase 74: Error Handling
- throw new Error("msg") - throw and catch
- throw "string error" - throw non-Error
- try/catch/finally - all three blocks
- finally runs even on throw or return
- Error.message, Error.name, Error.stack
- Custom error class: class MyError extends Error
- err instanceof Error/MyError
- Error subclasses: TypeError, RangeError, ReferenceError, SyntaxError
- Nested try/catch
- Re-throw
- Error.isError(val)
- Catch destructuring: catch({message})
- Error in async function propagates
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
# Basic throw and catch
# ---------------------------------------------------------------------------

class TestBasicThrowCatch:
    def test_throw_error_caught(self):
        i = run("""
let v = "ok"
try {
  throw new Error("oops")
} catch(e) {
  v = e.message
}
""")
        assert val(i) == "oops"

    def test_throw_prevents_continuation(self):
        i = run("""
let v = 0
try {
  throw new Error("stop")
  v = 99
} catch(e) {
  v = 1
}
""")
        assert val(i) == 1

    def test_catch_variable_accessible(self):
        i = run("""
let v = ""
try {
  throw new Error("test message")
} catch(e) {
  v = e.message
}
""")
        assert val(i) == "test message"

    def test_no_throw_no_catch(self):
        i = run("""
let v = 0
try {
  v = 42
} catch(e) {
  v = -1
}
""")
        assert val(i) == 42

    def test_throw_string(self):
        i = run("""
let v = ""
try { throw "string error" } catch(e) { v = e }
""")
        assert val(i) == "string error"

    def test_throw_number(self):
        i = run("""
let v = 0
try { throw 404 } catch(e) { v = e }
""")
        assert val(i) == 404

    def test_throw_object(self):
        i = run("""
let v = ""
try {
  throw { code: 42, msg: "bad" }
} catch(e) {
  v = e.msg
}
""")
        assert val(i) == "bad"

    def test_throw_list(self):
        i = run("""
let v = 0
try {
  throw [1, 2, 3]
} catch(e) {
  v = e[0]
}
""")
        assert val(i) == 1

    def test_catch_after_error_scope(self):
        i = run("""
let v = "before"
try {
  throw new Error("x")
} catch(e) {
  v = "caught"
}
""")
        assert val(i) == "caught"

    def test_throw_bool(self):
        i = run("""
let v = false
try { throw true } catch(e) { v = e }
""")
        assert val(i) is True


# ---------------------------------------------------------------------------
# try/catch/finally
# ---------------------------------------------------------------------------

class TestTryCatchFinally:
    def test_finally_always_runs(self):
        i = run("""
let v = 0
try { v = 1 } finally { v = v + 10 }
""")
        assert val(i) == 11

    def test_finally_runs_on_throw(self):
        i = run("""
let log = []
try {
  throw new Error("x")
} catch(e) {
  log.push("catch")
} finally {
  log.push("finally")
}
let v = log
""")
        assert val(i) == ["catch", "finally"]

    def test_finally_runs_on_return(self):
        i = run("""
fn foo() {
  try {
    return 1
  } finally {
    // finally runs
  }
}
let v = foo()
""")
        assert val(i) == 1

    def test_finally_order(self):
        i = run("""
let log = []
try {
  log.push("try")
  throw new Error("e")
} catch(e) {
  log.push("catch")
} finally {
  log.push("finally")
}
let v = log
""")
        assert val(i) == ["try", "catch", "finally"]

    def test_try_only_finally(self):
        i = run("""
let v = 0
try {
  v = 5
} finally {
  v = v + 1
}
""")
        assert val(i) == 6

    def test_finally_after_catch(self):
        i = run("""
let v = 0
try {
  throw new Error("x")
} catch(e) {
  v = 1
} finally {
  v = v + 100
}
""")
        assert val(i) == 101

    def test_finally_value_preserved(self):
        i = run("""
fn foo() {
  try {
    return 42
  } finally {
    let x = 99
  }
}
let v = foo()
""")
        assert val(i) == 42

    def test_try_catch_finally_no_throw(self):
        i = run("""
let v = []
try {
  v.push("try")
} catch(e) {
  v.push("catch")
} finally {
  v.push("finally")
}
""")
        assert val(i) == ["try", "finally"]


# ---------------------------------------------------------------------------
# Error properties
# ---------------------------------------------------------------------------

class TestErrorProperties:
    def test_error_message(self):
        i = run('let e = new Error("test message")\nlet v = e.message')
        assert val(i) == "test message"

    def test_error_name(self):
        i = run('let e = new Error("test")\nlet v = e.name')
        assert val(i) == "Error"

    def test_error_stack_exists(self):
        i = run('let e = new Error("test")\nlet v = e.stack !== null')
        assert val(i) is True

    def test_error_empty_message(self):
        i = run('let e = new Error("")\nlet v = e.message')
        assert val(i) == ""

    def test_error_message_preserved(self):
        i = run("""
let v = ""
try {
  throw new Error("preserved message")
} catch(e) {
  v = e.message
}
""")
        assert val(i) == "preserved message"

    def test_error_name_in_catch(self):
        i = run("""
let v = ""
try {
  throw new Error("x")
} catch(e) {
  v = e.name
}
""")
        assert val(i) == "Error"


# ---------------------------------------------------------------------------
# Custom error classes
# ---------------------------------------------------------------------------

class TestCustomErrorClass:
    def test_custom_error_message(self):
        i = run("""
class MyError extends Error {
  constructor(msg) {
    super(msg)
    this.name = "MyError"
  }
}
let e = new MyError("custom msg")
let v = e.message
""")
        assert val(i) == "custom msg"

    def test_custom_error_name(self):
        i = run("""
class MyError extends Error {
  constructor(msg) {
    super(msg)
    this.name = "MyError"
  }
}
let e = new MyError("x")
let v = e.name
""")
        assert val(i) == "MyError"

    def test_custom_error_caught(self):
        i = run("""
class AppError extends Error {
  constructor(msg) { super(msg) }
}
let v = ""
try {
  throw new AppError("app error")
} catch(e) {
  v = e.message
}
""")
        assert val(i) == "app error"

    def test_custom_error_extra_field(self):
        i = run("""
class HttpError extends Error {
  constructor(msg, code) {
    super(msg)
    this.code = code
  }
}
let e = new HttpError("not found", 404)
let v = e.code
""")
        assert val(i) == 404

    def test_custom_error_extra_field_message(self):
        i = run("""
class HttpError extends Error {
  constructor(msg, code) {
    super(msg)
    this.code = code
  }
}
let e = new HttpError("not found", 404)
let v = e.message
""")
        assert val(i) == "not found"

    def test_custom_error_instanceof_error(self):
        i = run("""
class MyError extends Error {
  constructor(msg) { super(msg) }
}
let e = new MyError("x")
let v = e instanceof Error
""")
        assert val(i) is True

    def test_custom_error_instanceof_custom(self):
        i = run("""
class MyError extends Error {
  constructor(msg) { super(msg) }
}
let e = new MyError("x")
let v = e instanceof MyError
""")
        assert val(i) is True

    def test_custom_error_thrown_and_caught(self):
        i = run("""
class ValidationError extends Error {
  constructor(msg) { super(msg); this.name = "ValidationError" }
}
let v = ""
try {
  throw new ValidationError("invalid input")
} catch(e) {
  v = e.name + ": " + e.message
}
""")
        assert val(i) == "ValidationError: invalid input"


# ---------------------------------------------------------------------------
# instanceof checks
# ---------------------------------------------------------------------------

class TestInstanceof:
    def test_instanceof_error(self):
        i = run("let e = new Error('test')\nlet v = e instanceof Error")
        assert val(i) is True

    def test_type_error_instanceof(self):
        i = run("let e = new TypeError('type')\nlet v = e instanceof TypeError")
        assert val(i) is True

    def test_range_error_instanceof(self):
        i = run("let e = new RangeError('range')\nlet v = e instanceof RangeError")
        assert val(i) is True

    def test_non_error_not_instanceof(self):
        i = run("let v = 42 instanceof Error")
        assert val(i) is False

    def test_null_not_instanceof(self):
        i = run("let v = null instanceof Error")
        assert val(i) is False


# ---------------------------------------------------------------------------
# Error subclasses
# ---------------------------------------------------------------------------

class TestErrorSubclasses:
    def test_type_error_name(self):
        i = run("""
let v = ""
try { throw new TypeError("type err") } catch(e) { v = e.name }
""")
        assert val(i) == "TypeError"

    def test_type_error_message(self):
        i = run("""
let v = ""
try { throw new TypeError("bad type") } catch(e) { v = e.message }
""")
        assert val(i) == "bad type"

    def test_range_error_name(self):
        i = run("""
let v = ""
try { throw new RangeError("out of range") } catch(e) { v = e.name }
""")
        assert val(i) == "RangeError"

    def test_range_error_message(self):
        i = run("""
let v = ""
try { throw new RangeError("too large") } catch(e) { v = e.message }
""")
        assert val(i) == "too large"

    def test_reference_error_name(self):
        i = run("""
let v = ""
try { throw new ReferenceError("ref err") } catch(e) { v = e.name }
""")
        assert val(i) == "ReferenceError"

    def test_reference_error_message(self):
        i = run("""
let v = ""
try { throw new ReferenceError("undefined var") } catch(e) { v = e.message }
""")
        assert val(i) == "undefined var"

    def test_syntax_error_name(self):
        i = run("""
let v = ""
try { throw new SyntaxError("syntax err") } catch(e) { v = e.name }
""")
        assert val(i) == "SyntaxError"

    def test_syntax_error_message(self):
        i = run("""
let v = ""
try { throw new SyntaxError("unexpected token") } catch(e) { v = e.message }
""")
        assert val(i) == "unexpected token"

    def test_all_subtypes_caught_as_error(self):
        i = run("""
let results = []
let errors = [new TypeError("t"), new RangeError("r"), new ReferenceError("ref")]
for (let e of errors) {
  results.push(e instanceof Error)
}
let v = results
""")
        assert val(i) == [True, True, True]


# ---------------------------------------------------------------------------
# Nested try/catch
# ---------------------------------------------------------------------------

class TestNestedTryCatch:
    def test_inner_catch_swallows(self):
        i = run("""
let v = ""
try {
  try {
    throw new Error("inner")
  } catch(e) {
    v = "inner caught"
  }
} catch(e) {
  v = "outer caught"
}
""")
        assert val(i) == "inner caught"

    def test_inner_rethrow_outer_catches(self):
        i = run("""
let v = ""
try {
  try {
    throw new Error("orig")
  } catch(e) {
    throw e
  }
} catch(e) {
  v = e.message
}
""")
        assert val(i) == "orig"

    def test_nested_finally(self):
        i = run("""
let log = []
try {
  try {
    throw new Error("x")
  } finally {
    log.push("inner finally")
  }
} catch(e) {
  log.push("outer catch")
}
let v = log
""")
        assert val(i) == ["inner finally", "outer catch"]

    def test_nested_no_throw(self):
        i = run("""
let v = 0
try {
  try {
    v = 1
  } catch(e) {
    v = -1
  }
} catch(e) {
  v = -2
}
""")
        assert val(i) == 1

    def test_deeply_nested_catch(self):
        i = run("""
let v = ""
try {
  try {
    try {
      throw new Error("deep")
    } catch(e) {
      v = "deep: " + e.message
    }
  } catch(e) {
    v = "mid"
  }
} catch(e) {
  v = "outer"
}
""")
        assert val(i) == "deep: deep"


# ---------------------------------------------------------------------------
# Re-throw
# ---------------------------------------------------------------------------

class TestRethrow:
    def test_rethrow_preserves_message(self):
        i = run("""
let v = ""
try {
  try {
    throw new Error("original")
  } catch(e) {
    throw e
  }
} catch(e) {
  v = e.message
}
""")
        assert val(i) == "original"

    def test_rethrow_as_new_error(self):
        i = run("""
let v = ""
try {
  try {
    throw new Error("orig")
  } catch(e) {
    throw new Error("wrapped: " + e.message)
  }
} catch(e) {
  v = e.message
}
""")
        assert val(i) == "wrapped: orig"

    def test_conditional_rethrow(self):
        i = run("""
let v = ""
try {
  try {
    throw new TypeError("type error")
  } catch(e) {
    if (e instanceof TypeError) {
      v = "handled TypeError"
    } else {
      throw e
    }
  }
} catch(e) {
  v = "unhandled"
}
""")
        assert val(i) == "handled TypeError"


# ---------------------------------------------------------------------------
# Error.isError
# ---------------------------------------------------------------------------

class TestErrorIsError:
    def test_is_error_true(self):
        i = run("let v = Error.isError(new Error('x'))")
        assert val(i) is True

    def test_is_error_false_string(self):
        i = run('let v = Error.isError("hello")')
        assert val(i) is False

    def test_is_error_false_number(self):
        i = run("let v = Error.isError(42)")
        assert val(i) is False

    def test_is_error_false_null(self):
        i = run("let v = Error.isError(null)")
        assert val(i) is False

    def test_is_error_custom_error(self):
        i = run("""
class MyError extends Error {
  constructor(msg) { super(msg) }
}
let e = new MyError("x")
let v = e instanceof Error
""")
        assert val(i) is True

    def test_is_error_type_error(self):
        i = run("let v = Error.isError(new TypeError('x'))")
        assert val(i) is True


# ---------------------------------------------------------------------------
# Catch destructuring
# ---------------------------------------------------------------------------

class TestCatchDestructuring:
    def test_catch_destructure_message(self):
        i = run("""
let v = ""
try {
  throw new Error("msg here")
} catch({message}) {
  v = message
}
""")
        assert val(i) == "msg here"

    def test_catch_destructure_name(self):
        i = run("""
let v = ""
try {
  throw new Error("x")
} catch({name}) {
  v = name
}
""")
        assert val(i) == "Error"

    def test_catch_destructure_multiple(self):
        i = run("""
let v = ""
try {
  throw new Error("test")
} catch({message, name}) {
  v = name + ": " + message
}
""")
        assert val(i) == "Error: test"


# ---------------------------------------------------------------------------
# Error in async function
# ---------------------------------------------------------------------------

class TestAsyncError:
    def test_async_throws_rejects(self):
        i = run("""
async fn foo() {
  throw new Error("async err")
}
let p = foo()
let v = p.state
""")
        assert val(i) == "rejected"

    def test_async_throws_reason_message(self):
        i = run("""
async fn foo() {
  throw new Error("async error msg")
}
let p = foo()
let v = p.reason.message
""")
        assert val(i) == "async error msg"

    def test_async_catch_handles_error(self):
        i = run("""
async fn foo() {
  throw new Error("async err")
}
let p = foo()
let v = p.state
""")
        assert val(i) == "rejected"

    def test_async_catch_state_fulfilled(self):
        i = run("""
async fn foo() {
  throw new Error("err")
}
let p = foo().catch(fn(e) { "ok" })
let v = p.state
""")
        assert val(i) == "fulfilled"

    def test_async_try_catch_await_rejected(self):
        i = run("""
async fn foo() {
  try {
    await Promise.reject("err")
    return "no"
  } catch(e) {
    return "caught"
  }
}
let p = foo()
let v = p.value
""")
        assert "caught" in str(val(i))

    def test_async_propagates_to_caller(self):
        i = run("""
async fn inner() {
  throw new Error("from inner")
}
async fn outer() {
  return await inner()
}
let p = outer()
let v = p.state
""")
        assert val(i) == "rejected"
