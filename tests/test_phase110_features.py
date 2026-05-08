"""Phase 110: Microservice patterns.

Tests covering:
  - loop { } — infinite loop broken by break
  - retry N { } — block retry on exception
  - Queue built-in — FIFO message queue
  - Channel built-in — inter-service channel
  - CircuitBreaker built-in — circuit breaker pattern
  - throttle(fn, ms) / debounce(fn, ms) — rate limiting utilities
"""

import pytest
from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser


def run(src: str) -> Interpreter:
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(i: Interpreter, name: str):
    return i.globals.get(name)


# ---------------------------------------------------------------------------
# loop { } statement
# ---------------------------------------------------------------------------


class TestLoopStatement:
    def test_loop_exits_on_break(self):
        i = run('''
let v = 0
loop {
  v = v + 1
  if v >= 5 { break }
}
''')
        assert val(i, 'v') == 5

    def test_loop_break_on_first_iteration(self):
        i = run('''
let v = 0
loop {
  v = 42
  break
}
''')
        assert val(i, 'v') == 42

    def test_loop_accumulate(self):
        i = run('''
var total = 0
var n = 0
loop {
  n = n + 1
  total = total + n
  if n == 10 { break }
}
let v = total
''')
        assert val(i, 'v') == 55  # sum 1..10

    def test_loop_continue_then_break(self):
        i = run('''
var evens = 0
var n = 0
loop {
  n = n + 1
  if n % 2 != 0 { continue }
  evens = evens + 1
  if n >= 10 { break }
}
let v = evens
''')
        assert val(i, 'v') == 5  # 2,4,6,8,10

    def test_loop_nested_in_function(self):
        i = run('''
fn countTo(limit) {
  var c = 0
  loop {
    c = c + 1
    if c >= limit { break }
  }
  return c
}
let v = countTo(7)
''')
        assert val(i, 'v') == 7

    def test_loop_with_inner_variable(self):
        i = run('''
var result = ""
var i = 0
loop {
  i = i + 1
  result = result + String(i)
  if i == 4 { break }
}
let v = result
''')
        assert val(i, 'v') == '1234'

    def test_loop_exceeds_limit_throws(self):
        with pytest.raises(Exception):
            run('''
loop {
  let x = 1
}
''')

    def test_labeled_loop_break(self):
        i = run('''
var v = 0
outer: loop {
  var inner = 0
  loop {
    inner = inner + 1
    if inner >= 3 { break outer }
  }
  v = v + 1
}
''')
        assert val(i, 'v') == 0  # outer broken before v increments

    def test_loop_used_in_task(self):
        i = run('''
var processed = 0
task process {
  var items = [1, 2, 3]
  var idx = 0
  loop {
    if idx >= items.length { break }
    processed = processed + items[idx]
    idx = idx + 1
  }
}
process()
let v = processed
''')
        assert val(i, 'v') == 6


# ---------------------------------------------------------------------------
# retry N { } block
# ---------------------------------------------------------------------------


class TestRetryBlock:
    def test_retry_succeeds_first_try(self):
        i = run('''
var v = 0
retry 3 {
  v = 42
}
''')
        assert val(i, 'v') == 42

    def test_retry_succeeds_on_second_attempt(self):
        i = run('''
var attempts = 0
var v = false
retry 3 {
  attempts = attempts + 1
  if attempts < 2 {
    throw new Error("not yet")
  }
  v = true
}
''')
        assert val(i, 'v') is True
        assert val(i, 'attempts') == 2

    def test_retry_succeeds_on_last_attempt(self):
        i = run('''
var attempts = 0
retry 3 {
  attempts = attempts + 1
  if attempts < 3 {
    throw new Error("retry")
  }
}
let v = attempts
''')
        assert val(i, 'v') == 3

    def test_retry_exhausted_raises(self):
        with pytest.raises(Exception):
            run('''
retry 3 {
  throw new Error("always fails")
}
''')

    def test_retry_1_is_just_one_attempt(self):
        attempts = [0]
        i = run('''
var attempts = 0
var v = false
retry 1 {
  attempts = attempts + 1
  v = true
}
''')
        assert val(i, 'v') is True
        assert val(i, 'attempts') == 1

    def test_retry_with_times_keyword(self):
        i = run('''
var attempts = 0
retry 3 times {
  attempts = attempts + 1
  if attempts < 2 {
    throw new Error("oops")
  }
}
let v = attempts
''')
        assert val(i, 'v') == 2

    def test_retry_count_5_exhausted_raises(self):
        with pytest.raises(Exception):
            run('''
retry 5 {
  throw new Error("always fails")
}
''')

    def test_retry_in_function(self):
        i = run('''
fn fetchWithRetry() {
  var attempt = 0
  retry 3 {
    attempt = attempt + 1
    if attempt < 3 {
      throw new Error("network error")
    }
  }
  return attempt
}
let v = fetchWithRetry()
''')
        assert val(i, 'v') == 3


# ---------------------------------------------------------------------------
# Queue built-in
# ---------------------------------------------------------------------------


class TestQueue:
    def test_queue_enqueue_dequeue(self):
        i = run('''
let q = Queue.new()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
let v = q.dequeue()
''')
        assert val(i, 'v') == 1

    def test_queue_size(self):
        i = run('''
let q = Queue.new()
q.enqueue("a")
q.enqueue("b")
let v = q.size
''')
        assert val(i, 'v') == 2

    def test_queue_is_empty_true(self):
        i = run('''
let q = Queue.new()
let v = q.isEmpty
''')
        assert val(i, 'v') is True

    def test_queue_is_empty_false_after_enqueue(self):
        i = run('''
let q = Queue.new()
q.enqueue("hello")
let v = q.isEmpty
''')
        assert val(i, 'v') is False

    def test_queue_peek_does_not_remove(self):
        i = run('''
let q = Queue.new()
q.enqueue(10)
q.enqueue(20)
let first = q.peek()
let sizeAfterPeek = q.size
''')
        assert val(i, 'first') == 10
        assert val(i, 'sizeAfterPeek') == 2

    def test_queue_dequeue_fifo_order(self):
        i = run('''
let q = Queue.new()
q.enqueue("x")
q.enqueue("y")
q.enqueue("z")
let a = q.dequeue()
let b = q.dequeue()
let c = q.dequeue()
let v = a + b + c
''')
        assert val(i, 'v') == 'xyz'

    def test_queue_drain(self):
        i = run('''
let q = Queue.new()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
let v = q.drain()
let empty = q.isEmpty
''')
        assert val(i, 'v') == [1, 2, 3]
        assert val(i, 'empty') is True

    def test_queue_clear(self):
        i = run('''
let q = Queue.new()
q.enqueue(1)
q.enqueue(2)
q.clear()
let v = q.size
''')
        assert val(i, 'v') == 0

    def test_queue_dequeue_empty_throws(self):
        with pytest.raises(Exception):
            run('''
let q = Queue.new()
q.dequeue()
''')

    def test_queue_loop_pattern(self):
        i = run('''
let q = Queue.new()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
var total = 0
loop {
  if q.isEmpty { break }
  total = total + q.dequeue()
}
let v = total
''')
        assert val(i, 'v') == 6


# ---------------------------------------------------------------------------
# Channel built-in
# ---------------------------------------------------------------------------


class TestChannel:
    def test_channel_send_receive(self):
        i = run('''
let ch = Channel.new()
ch.send("hello")
let v = ch.receive()
''')
        assert val(i, 'v') == 'hello'

    def test_channel_size(self):
        i = run('''
let ch = Channel.new()
ch.send(1)
ch.send(2)
let v = ch.size
''')
        assert val(i, 'v') == 2

    def test_channel_receive_empty_returns_undefined(self):
        i = run('''
let ch = Channel.new()
let v = ch.receive() === undefined
''')
        assert val(i, 'v') is True

    def test_channel_close(self):
        i = run('''
let ch = Channel.new()
ch.close()
let v = ch.isClosed
''')
        assert val(i, 'v') is True

    def test_channel_send_after_close_throws(self):
        with pytest.raises(Exception):
            run('''
let ch = Channel.new()
ch.close()
ch.send("oops")
''')

    def test_channel_drain(self):
        i = run('''
let ch = Channel.new()
ch.send("a")
ch.send("b")
let v = ch.drain()
let s = ch.size
''')
        assert val(i, 'v') == ['a', 'b']
        assert val(i, 's') == 0

    def test_channel_fifo_order(self):
        i = run('''
let ch = Channel.new()
ch.send(10)
ch.send(20)
ch.send(30)
let a = ch.receive()
let b = ch.receive()
let c = ch.receive()
let v = a + b + c
''')
        assert val(i, 'v') == 60

    def test_channel_is_not_closed_initially(self):
        i = run('''
let ch = Channel.new()
let v = ch.isClosed
''')
        assert val(i, 'v') is False

    def test_channel_producer_consumer_pattern(self):
        i = run('''
let ch = Channel.new()
fn produce(c) {
  c.send(1)
  c.send(2)
  c.send(3)
}
fn consume(c) {
  var total = 0
  total = total + c.receive()
  total = total + c.receive()
  total = total + c.receive()
  return total
}
produce(ch)
let v = consume(ch)
''')
        assert val(i, 'v') == 6


# ---------------------------------------------------------------------------
# CircuitBreaker built-in
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_circuit_breaker_initial_state_closed(self):
        i = run('''
let cb = CircuitBreaker.new()
let v = cb.state
''')
        assert val(i, 'v') == 'CLOSED'

    def test_circuit_breaker_execute_success(self):
        i = run('''
let cb = CircuitBreaker.new()
let v = cb.execute(() => 42)
''')
        assert val(i, 'v') == 42

    def test_circuit_breaker_stays_closed_on_success(self):
        i = run('''
let cb = CircuitBreaker.new(3)
cb.execute(() => 1)
cb.execute(() => 2)
let v = cb.state
''')
        assert val(i, 'v') == 'CLOSED'

    def test_circuit_breaker_opens_after_threshold(self):
        i = run('''
let cb = CircuitBreaker.new(3)
var count = 0
try { cb.execute(() => { throw new Error("fail") }) } catch(e) { count = count + 1 }
try { cb.execute(() => { throw new Error("fail") }) } catch(e) { count = count + 1 }
try { cb.execute(() => { throw new Error("fail") }) } catch(e) { count = count + 1 }
let v = cb.state
''')
        assert val(i, 'v') == 'OPEN'

    def test_circuit_breaker_reset(self):
        i = run('''
let cb = CircuitBreaker.new(1)
try { cb.execute(() => { throw new Error("fail") }) } catch(e) {}
cb.reset()
let v = cb.state
''')
        assert val(i, 'v') == 'CLOSED'

    def test_circuit_breaker_failure_count(self):
        i = run('''
let cb = CircuitBreaker.new(5)
try { cb.execute(() => { throw new Error("f") }) } catch(e) {}
try { cb.execute(() => { throw new Error("f") }) } catch(e) {}
let v = cb.failureCount
''')
        assert val(i, 'v') == 2

    def test_circuit_breaker_threshold_property(self):
        i = run('''
let cb = CircuitBreaker.new(7)
let v = cb.threshold
''')
        assert val(i, 'v') == 7

    def test_circuit_breaker_open_then_reset_allows_execute(self):
        i = run('''
let cb = CircuitBreaker.new(1)
try { cb.execute(() => { throw new Error("fail") }) } catch(e) {}
cb.reset()
let v = cb.execute(() => "ok")
''')
        assert val(i, 'v') == 'ok'

    def test_circuit_breaker_open_rejects(self):
        i = run('''
let cb = CircuitBreaker.new(1)
try { cb.execute(() => { throw new Error("fail") }) } catch(e) {}
var rejected = false
try {
  cb.execute(() => "should not run")
} catch(e) {
  rejected = true
}
let v = rejected
''')
        assert val(i, 'v') is True

    def test_circuit_breaker_success_resets_failure_count(self):
        i = run('''
let cb = CircuitBreaker.new(5)
try { cb.execute(() => { throw new Error("f") }) } catch(e) {}
cb.execute(() => "success")
let v = cb.failureCount
''')
        assert val(i, 'v') == 0


# ---------------------------------------------------------------------------
# throttle / debounce built-ins
# ---------------------------------------------------------------------------


class TestThrottleDebounce:
    def test_throttle_creates_function(self):
        i = run('''
fn greet(x) { return x * 2 }
let t = throttle(greet, 100)
let v = typeof t
''')
        assert val(i, 'v') == 'function'

    def test_throttle_first_call_executes(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let t = throttle(inc, 1000)
t()
let v = called
''')
        assert val(i, 'v') == 1

    def test_throttle_second_call_within_window_skipped(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let t = throttle(inc, 10000)
t()
t()
t()
let v = called
''')
        # Only first call within window executes
        assert val(i, 'v') == 1

    def test_throttle_zero_ms_every_call_executes(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let t = throttle(inc, 0)
t()
t()
t()
let v = called
''')
        assert val(i, 'v') == 3

    def test_debounce_creates_function(self):
        i = run('''
fn greet(x) { return x }
let d = debounce(greet, 200)
let v = typeof d
''')
        assert val(i, 'v') == 'function'

    def test_debounce_executes_immediately_in_sync_model(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let d = debounce(inc, 500)
d()
d()
let v = called
''')
        # In sync model debounce executes each call immediately
        assert val(i, 'v') == 2

    def test_throttle_with_args(self):
        i = run('''
var last = 0
fn save(x) { last = x }
let t = throttle(save, 0)
t(10)
t(20)
t(30)
let v = last
''')
        assert val(i, 'v') == 30

    def test_debounce_passes_args(self):
        i = run('''
var last = 0
fn save(x) { last = x }
let d = debounce(save, 100)
d(99)
let v = last
''')
        assert val(i, 'v') == 99
