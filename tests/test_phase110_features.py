"""Phase 110 feature tests.

Coverage:
  - `loop { ... } until ...` keyword alias
  - retry helper
  - Queue / Channel / CircuitBreaker primitives
  - throttle / debounce helpers
  - loop(fn, limit) orchestration helper
"""

from sprycode.interpreter import Interpreter
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str = "v"):
    return i.globals.get(name)


def test_loop_keyword_alias_repeat_until():
    i = run(
        """
var i = 0
loop {
    i += 1
} until i >= 4
let v = i
"""
    )
    assert val(i) == 4


def test_retry_helper_retries_until_success():
    i = run(
        """
var attempts = 0
let v = retry((n) => {
    attempts = n
    if n < 3 { throw new Error("nope") }
    return n
}, 5)
"""
    )
    assert val(i) == 3
    assert val(i, "attempts") == 3


def test_queue_primitive_fifo():
    i = run(
        """
let q = Queue()
q.enqueue("a")
q.enqueue("b")
let first = q.dequeue()
let second = q.peek()
let v = [first, second, q.size, q.isEmpty]
"""
    )
    assert val(i) == ["a", "b", 1, False]


def test_channel_send_receive():
    i = run(
        """
let ch = Channel()
ch.send(10)
ch.send(20)
let a = ch.receive()
let b = ch.receive()
let v = [a, b, ch.size]
"""
    )
    assert val(i) == [10, 20, 0]


def test_circuit_breaker_opens_after_threshold():
    i = run(
        """
let cb = CircuitBreaker(2, 0)
var runs = 0
try { cb.execute(() => { runs += 1; throw new Error("boom") }) } catch(e) {}
try { cb.execute(() => { runs += 1; throw new Error("boom") }) } catch(e) {}
var blocked = false
try { cb.execute(() => { runs += 1; return 42 }) } catch(e) { blocked = true }
let v = [runs, cb.state, blocked]
"""
    )
    assert val(i) == [2, "open", True]


def test_throttle_helper_blocks_rapid_repeat():
    i = run(
        """
var count = 0
let f = throttle(() => { count += 1; return count }, 10000)
let a = f()
let b = f()
f.reset()
let c = f()
let v = [a, b, c, count]
"""
    )
    assert val(i) == [1, None, 2, 2]


def test_debounce_helper_flush_executes_once():
    i = run(
        """
var count = 0
let d = debounce(() => { count += 1; return count }, 0)
d()
d()
let before = count
let out = d.flush()
let after = count
let v = [before, out, after]
"""
    )
    assert val(i) == [0, 1, 1]


def test_loop_helper_until_solved_dict():
    i = run(
        """
let v = loop((i) => {
    if i >= 2 { return { solved: true, value: i + 1 } }
    return false
}, 10)
"""
    )
    assert val(i) == 3
