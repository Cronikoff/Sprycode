"""Phase 110: Microservice primitives for SpryCode.

Tests covering:
  - loop statement (infinite loop until break)
  - retry block (retry N attempts with optional catch)
  - Queue class (FIFO queue)
  - Channel class (synchronous message-passing)
  - CircuitBreaker class (microservice resilience pattern)
  - throttle() global function
  - debounce() global function
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
# loop statement
# ---------------------------------------------------------------------------


class TestLoopStatement:
    def test_loop_basic_break(self):
        i = run("""
let count = 0
loop {
  count = count + 1
  if count >= 5 { break }
}
""")
        assert val(i, "count") == 5

    def test_loop_accumulate(self):
        i = run("""
let total = 0
let n = 1
loop {
  if n > 10 { break }
  total = total + n
  n = n + 1
}
""")
        assert val(i, "total") == 55

    def test_loop_continue(self):
        i = run("""
let evens = []
let k = 0
loop {
  k = k + 1
  if k > 10 { break }
  if k % 2 != 0 { continue }
  evens.push(k)
}
""")
        assert val(i, "evens") == [2, 4, 6, 8, 10]

    def test_loop_with_break_value(self):
        i = run("""
let found = -1
let i = 0
loop {
  if i == 7 {
    found = i
    break
  }
  i = i + 1
}
""")
        assert val(i, "found") == 7

    def test_loop_immediate_break(self):
        i = run("""
let ran = false
loop {
  ran = true
  break
}
""")
        assert val(i, "ran") is True

    def test_loop_nested(self):
        i = run("""
let outer = 0
let inner_total = 0
loop {
  outer = outer + 1
  let j = 0
  loop {
    j = j + 1
    inner_total = inner_total + 1
    if j >= 3 { break }
  }
  if outer >= 3 { break }
}
""")
        assert val(i, "outer") == 3
        assert val(i, "inner_total") == 9

    def test_loop_with_list_building(self):
        i = run("""
let results = []
let x = 0
loop {
  x = x + 1
  results.push(x * x)
  if x >= 4 { break }
}
""")
        assert val(i, "results") == [1, 4, 9, 16]

    def test_loop_condition_change(self):
        i = run("""
let v = 1
loop {
  v = v * 2
  if v >= 64 { break }
}
""")
        assert val(i, "v") == 64

    def test_loop_empty_body_break(self):
        i = run("""
let done = false
loop {
  done = true
  break
}
""")
        assert val(i, "done") is True

    def test_loop_search_pattern(self):
        """Simulate a microservice polling loop."""
        i = run("""
let items = [3, 7, 12, 1, 9]
let idx = 0
let target = -1
loop {
  if idx >= items.length { break }
  if items[idx] == 12 {
    target = idx
    break
  }
  idx = idx + 1
}
""")
        assert val(i, "target") == 2

    def test_loop_labeled_break(self):
        """Outer loop break via label from inner loop."""
        i = run("""
let count = 0
outer: loop {
  let inner = 0
  loop {
    inner = inner + 1
    count = count + 1
    if inner >= 3 { break }
  }
  if count >= 6 { break outer }
}
""")
        assert val(i, "count") == 6


# ---------------------------------------------------------------------------
# retry block
# ---------------------------------------------------------------------------


class TestRetryBlock:
    def test_retry_succeeds_first_attempt(self):
        i = run("""
let calls = 0
retry 3 {
  calls = calls + 1
}
""")
        assert val(i, "calls") == 1

    def test_retry_succeeds_after_failures(self):
        i = run("""
let calls = 0
retry 3 {
  calls = calls + 1
  if calls < 3 { throw "fail" }
}
""")
        assert val(i, "calls") == 3

    def test_retry_exhausted_raises(self):
        with pytest.raises(Exception):
            run("""
retry 3 {
  throw "always fails"
}
""")

    def test_retry_with_catch_on_exhaustion(self):
        i = run("""
let errCaught = false
retry 3 {
  throw "boom"
} catch e {
  errCaught = true
}
""")
        assert val(i, "errCaught") is True

    def test_retry_default_attempts(self):
        """retry { } with no count uses default of 3."""
        i = run("""
let c = 0
retry {
  c = c + 1
  if c < 3 { throw "not yet" }
}
""")
        assert val(i, "c") == 3

    def test_retry_postfix_attempts(self):
        i = run("""
let c = 0
retry {
  c = c + 1
  if c < 4 { throw "not yet" }
} attempts 5
""")
        assert val(i, "c") == 4

    def test_retry_catch_receives_error(self):
        i = run("""
let errVal = ""
retry 2 {
  throw "service_down"
} catch err {
  errVal = "handled"
}
""")
        assert val(i, "errVal") == "handled"

    def test_retry_single_attempt(self):
        i = run("""
let ran = false
retry 1 {
  ran = true
}
""")
        assert val(i, "ran") is True

    def test_retry_single_attempt_failure_raises(self):
        with pytest.raises(Exception):
            run("""
retry 1 {
  throw "instant fail"
}
""")

    def test_retry_accumulates_across_attempts(self):
        i = run("""
let log = []
retry 4 {
  log.push(log.length + 1)
  if log.length < 4 { throw "retry" }
}
""")
        assert val(i, "log") == [1, 2, 3, 4]

    def test_retry_no_exception_skips_catch(self):
        i = run("""
let caught = false
retry 3 {
  let x = 1 + 1
} catch e {
  caught = true
}
""")
        assert val(i, "caught") is False

    def test_retry_in_function(self):
        i = run("""
fn fetchData(attempts) {
  let count = 0
  retry 3 {
    count = count + 1
    if count < attempts { throw "not ready" }
  }
  return count
}
let v = fetchData(2)
""")
        assert val(i, "v") == 2


# ---------------------------------------------------------------------------
# Queue class
# ---------------------------------------------------------------------------


class TestQueueClass:
    def test_queue_enqueue_dequeue(self):
        i = run("""
let q = new Queue()
q.enqueue(10)
q.enqueue(20)
q.enqueue(30)
let v = q.dequeue()
""")
        assert val(i, "v") == 10

    def test_queue_fifo_order(self):
        i = run("""
let q = new Queue()
q.enqueue("a")
q.enqueue("b")
q.enqueue("c")
let r1 = q.dequeue()
let r2 = q.dequeue()
let r3 = q.dequeue()
""")
        assert val(i, "r1") == "a"
        assert val(i, "r2") == "b"
        assert val(i, "r3") == "c"

    def test_queue_push_alias(self):
        i = run("""
let q = new Queue()
q.push(1)
q.push(2)
let v = q.pop()
""")
        assert val(i, "v") == 1

    def test_queue_size(self):
        i = run("""
let q = new Queue()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
let sz = q.size
""")
        assert val(i, "sz") == 3

    def test_queue_is_empty_true(self):
        i = run("""
let q = new Queue()
let e = q.isEmpty
""")
        assert val(i, "e") is True

    def test_queue_is_empty_false(self):
        i = run("""
let q = new Queue()
q.enqueue(1)
let e = q.isEmpty
""")
        assert val(i, "e") is False

    def test_queue_peek(self):
        i = run("""
let q = new Queue()
q.enqueue(42)
q.enqueue(99)
let p = q.peek()
let sz = q.size
""")
        assert val(i, "p") == 42
        assert val(i, "sz") == 2  # peek does not remove

    def test_queue_dequeue_empty_returns_undefined(self):
        i = run("""
let q = new Queue()
let v = q.dequeue()
let isU = v === undefined
""")
        assert val(i, "isU") is True

    def test_queue_clear(self):
        i = run("""
let q = new Queue()
q.enqueue(1)
q.enqueue(2)
q.clear()
let sz = q.size
let e = q.isEmpty
""")
        assert val(i, "sz") == 0
        assert val(i, "e") is True

    def test_queue_to_array(self):
        i = run("""
let q = new Queue()
q.enqueue("x")
q.enqueue("y")
q.enqueue("z")
let arr = q.toArray()
""")
        assert val(i, "arr") == ["x", "y", "z"]

    def test_queue_size_after_dequeue(self):
        i = run("""
let q = new Queue()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
q.dequeue()
let sz = q.size
""")
        assert val(i, "sz") == 2

    def test_queue_as_service_buffer(self):
        """Simulate message buffering between microservices."""
        i = run("""
let inbox = new Queue()
let processed = []
inbox.push("msg1")
inbox.push("msg2")
inbox.push("msg3")
loop {
  if inbox.isEmpty { break }
  let msg = inbox.dequeue()
  processed.push(msg)
}
""")
        assert val(i, "processed") == ["msg1", "msg2", "msg3"]


# ---------------------------------------------------------------------------
# Channel class
# ---------------------------------------------------------------------------


class TestChannelClass:
    def test_channel_send_receive(self):
        i = run("""
let ch = new Channel()
ch.send("hello")
let msg = ch.receive()
""")
        assert val(i, "msg") == "hello"

    def test_channel_fifo_order(self):
        i = run("""
let ch = new Channel()
ch.send(1)
ch.send(2)
ch.send(3)
let a = ch.receive()
let b = ch.receive()
let c = ch.receive()
""")
        assert val(i, "a") == 1
        assert val(i, "b") == 2
        assert val(i, "c") == 3

    def test_channel_size(self):
        i = run("""
let ch = new Channel()
ch.send("x")
ch.send("y")
let sz = ch.size
""")
        assert val(i, "sz") == 2

    def test_channel_is_empty(self):
        i = run("""
let ch = new Channel()
let e1 = ch.isEmpty
ch.send("item")
let e2 = ch.isEmpty
""")
        assert val(i, "e1") is True
        assert val(i, "e2") is False

    def test_channel_receive_empty_returns_undefined(self):
        i = run("""
let ch = new Channel()
let v = ch.receive()
let isU = v === undefined
""")
        assert val(i, "isU") is True

    def test_channel_close(self):
        i = run("""
let ch = new Channel()
ch.close()
let closed = ch.isClosed
""")
        assert val(i, "closed") is True

    def test_channel_send_after_close_raises(self):
        with pytest.raises(Exception):
            run("""
let ch = new Channel()
ch.close()
ch.send("boom")
""")

    def test_channel_try_receive_alias(self):
        i = run("""
let ch = new Channel()
ch.send(99)
let v = ch.tryReceive()
""")
        assert val(i, "v") == 99

    def test_channel_is_closed_false_initially(self):
        i = run("""
let ch = new Channel()
let closed = ch.isClosed
""")
        assert val(i, "closed") is False

    def test_channel_producer_consumer_pattern(self):
        """Simulate producer feeding Channel, consumer draining it."""
        i = run("""
let ch = new Channel()
let results = []
let items = [10, 20, 30, 40, 50]
for item in items {
  ch.send(item * 2)
}
loop {
  if ch.isEmpty { break }
  results.push(ch.receive())
}
""")
        assert val(i, "results") == [20, 40, 60, 80, 100]

    def test_channel_size_decreases_on_receive(self):
        i = run("""
let ch = new Channel()
ch.send("a")
ch.send("b")
ch.send("c")
ch.receive()
let sz = ch.size
""")
        assert val(i, "sz") == 2


# ---------------------------------------------------------------------------
# CircuitBreaker class
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_circuit_breaker_initial_state(self):
        i = run("""
let cb = new CircuitBreaker()
let s = cb.state
let f = cb.failures
""")
        assert val(i, "s") == "CLOSED"
        assert val(i, "f") == 0

    def test_circuit_breaker_call_success(self):
        i = run("""
fn greet() { return "ok" }
let cb = new CircuitBreaker()
let result = cb.call(greet)
""")
        assert val(i, "result") == "ok"

    def test_circuit_breaker_stays_closed_on_success(self):
        i = run("""
fn ok() { return 1 }
let cb = new CircuitBreaker({ threshold: 3 })
cb.call(ok)
cb.call(ok)
let s = cb.state
""")
        assert val(i, "s") == "CLOSED"

    def test_circuit_breaker_trips_after_threshold(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 2, timeout: 99999 })
let s = "CLOSED"
let caught = 0
fn boom() { throw "fail" }
try {
  cb.call(boom)
} catch e { caught = caught + 1 }
try {
  cb.call(boom)
} catch e { caught = caught + 1 }
let s2 = cb.failures
""")
        assert val(i, "s2") == 2

    def test_circuit_breaker_open_rejects_calls(self):
        with pytest.raises(Exception):
            run("""
let cb = new CircuitBreaker({ threshold: 1, timeout: 99999 })
fn boom() { throw "fail" }
try { cb.call(boom) } catch e {}
cb.call(boom)
""")

    def test_circuit_breaker_reset(self):
        i = run("""
fn boom() { throw "fail" }
let cb = new CircuitBreaker({ threshold: 2, timeout: 99999 })
try { cb.call(boom) } catch e {}
try { cb.call(boom) } catch e {}
cb.reset()
let s = cb.state
let f = cb.failures
""")
        assert val(i, "s") == "CLOSED"
        assert val(i, "f") == 0

    def test_circuit_breaker_failures_reset_on_success(self):
        i = run("""
let count = 0
fn flaky() {
  count = count + 1
  if count < 2 { throw "fail" }
  return "ok"
}
let cb = new CircuitBreaker({ threshold: 5 })
try { cb.call(flaky) } catch e {}
let r = cb.call(flaky)
let f = cb.failures
""")
        assert val(i, "r") == "ok"
        assert val(i, "f") == 0

    def test_circuit_breaker_call_with_args(self):
        i = run("""
fn add(a, b) { return a + b }
let cb = new CircuitBreaker()
let v = cb.call(add, 3, 4)
""")
        assert val(i, "v") == 7

    def test_circuit_breaker_custom_threshold(self):
        i = run("""
fn boom() { throw "fail" }
let cb = new CircuitBreaker({ threshold: 3, timeout: 99999 })
try { cb.call(boom) } catch e {}
try { cb.call(boom) } catch e {}
let s1 = cb.state
try { cb.call(boom) } catch e {}
let s2 = cb.state
""")
        assert val(i, "s1") == "CLOSED"
        assert val(i, "s2") == "OPEN"


# ---------------------------------------------------------------------------
# throttle()
# ---------------------------------------------------------------------------


class TestThrottle:
    def test_throttle_first_call_passes_through(self):
        i = run("""
let calls = 0
fn inc() { calls = calls + 1; return calls }
let t = throttle(inc, 10000)
let r = t()
""")
        assert val(i, "r") == 1
        assert val(i, "calls") == 1

    def test_throttle_second_immediate_call_skipped(self):
        i = run("""
let calls = 0
fn inc() { calls = calls + 1; return calls }
let t = throttle(inc, 10000)
let r1 = t()
let r2 = t()
""")
        assert val(i, "r1") == 1
        assert val(i, "r2") == 1   # second call returns cached value
        assert val(i, "calls") == 1  # function only called once

    def test_throttle_returns_callable(self):
        i = run("""
fn noop() { return 0 }
let t = throttle(noop, 100)
let isFunc = typeof t == "function"
""")
        assert val(i, "isFunc") is True

    def test_throttle_zero_interval_always_calls(self):
        i = run("""
let calls = 0
fn inc() { calls = calls + 1; return calls }
let t = throttle(inc, 0)
let r1 = t()
let r2 = t()
let r3 = t()
""")
        assert val(i, "calls") == 3

    def test_throttle_with_args(self):
        i = run("""
fn add(a, b) { return a + b }
let t = throttle(add, 10000)
let r = t(3, 4)
""")
        assert val(i, "r") == 7

    def test_throttle_default_interval(self):
        """throttle(fn) with no interval should work."""
        i = run("""
let c = 0
fn inc() { c = c + 1; return c }
let t = throttle(inc)
let r = t()
""")
        assert val(i, "r") == 1

    def test_throttle_multiple_functions_independent(self):
        i = run("""
let c1 = 0
let c2 = 0
fn f1() { c1 = c1 + 1; return c1 }
fn f2() { c2 = c2 + 1; return c2 }
let t1 = throttle(f1, 10000)
let t2 = throttle(f2, 10000)
t1()
t1()
t2()
""")
        assert val(i, "c1") == 1
        assert val(i, "c2") == 1


# ---------------------------------------------------------------------------
# debounce()
# ---------------------------------------------------------------------------


class TestDebounce:
    def test_debounce_returns_callable(self):
        i = run("""
fn noop() { return 0 }
let d = debounce(noop, 100)
let isFunc = typeof d == "function"
""")
        assert val(i, "isFunc") is True

    def test_debounce_flush_executes_pending(self):
        i = run("""
let calls = 0
fn inc() { calls = calls + 1; return calls }
let d = debounce(inc, 10000)
d()
let r = d.flush()
""")
        assert val(i, "calls") == 1
        assert val(i, "r") == 1

    def test_debounce_cancel_prevents_call(self):
        i = run("""
let calls = 0
fn inc() { calls = calls + 1 }
let d = debounce(inc, 10000)
d()
d.cancel()
d.flush()
""")
        assert val(i, "calls") == 0

    def test_debounce_zero_delay_executes(self):
        i = run("""
let calls = 0
fn inc() { calls = calls + 1; return calls }
let d = debounce(inc, 0)
let r = d()
""")
        # With 0 delay, elapsed >= delay, so should execute
        assert val(i, "calls") == 1

    def test_debounce_with_args_on_flush(self):
        i = run("""
let last = 0
fn store(x) { last = x }
let d = debounce(store, 10000)
d(42)
d.flush()
""")
        assert val(i, "last") == 42

    def test_debounce_default_delay(self):
        i = run("""
fn noop() { return 1 }
let d = debounce(noop)
let r = d.flush()
""")
        # flush with no pending call returns undefined
        # (no pending args = no-op)

    def test_debounce_multiple_calls_only_latest_flushed(self):
        i = run("""
let last = 0
fn store(x) { last = x }
let d = debounce(store, 10000)
d(1)
d(2)
d(3)
d.flush()
""")
        assert val(i, "last") == 3


# ---------------------------------------------------------------------------
# Integration: loop + retry + Queue + Channel in microservice pattern
# ---------------------------------------------------------------------------


class TestMicroserviceIntegration:
    def test_retry_feeds_queue(self):
        """A retry block sends a result to a Queue on success."""
        i = run("""
let q = new Queue()
let attempt = 0
retry 3 {
  attempt = attempt + 1
  if attempt < 2 { throw "transient" }
  q.enqueue("success")
}
let result = q.dequeue()
""")
        assert val(i, "result") == "success"

    def test_loop_drains_channel(self):
        """A loop drains all messages from a Channel into a list."""
        i = run("""
let ch = new Channel()
ch.send("event1")
ch.send("event2")
ch.send("event3")
let events = []
loop {
  if ch.isEmpty { break }
  events.push(ch.receive())
}
""")
        assert val(i, "events") == ["event1", "event2", "event3"]

    def test_circuit_breaker_with_retry(self):
        """CircuitBreaker + retry: retry gives up; catch logs error."""
        i = run("""
let logged = false
fn unreliable() { throw "timeout" }
let cb = new CircuitBreaker({ threshold: 5, timeout: 99999 })
retry 2 {
  cb.call(unreliable)
} catch e {
  logged = true
}
""")
        assert val(i, "logged") is True

    def test_queue_pipeline_loop(self):
        """Enqueue computed values, drain with loop, verify results."""
        i = run("""
let q = new Queue()
let nums = [1, 2, 3, 4, 5]
for n in nums {
  q.enqueue(n * n)
}
let squares = []
loop {
  if q.isEmpty { break }
  squares.push(q.dequeue())
}
""")
        assert val(i, "squares") == [1, 4, 9, 16, 25]

    def test_throttle_in_loop(self):
        """Throttle is respected even when called inside a loop."""
        i = run("""
let calls = 0
fn inc() { calls = calls + 1 }
let t = throttle(inc, 10000)
let i = 0
loop {
  i = i + 1
  t()
  if i >= 5 { break }
}
""")
        assert val(i, "calls") == 1  # only first call goes through

    def test_channel_with_circuit_breaker_success(self):
        i = run("""
let ch = new Channel()
let cb = new CircuitBreaker({ threshold: 3 })
fn produce(v) { ch.send(v) }
cb.call(produce, 42)
let msg = ch.receive()
""")
        assert val(i, "msg") == 42

    def test_full_microservice_loop(self):
        """Complete microservice loop: produce → queue → process → channel."""
        i = run("""
let inbox = new Queue()
let outbox = new Channel()
let items = [1, 2, 3, 4, 5]
for item in items {
  inbox.enqueue(item)
}
loop {
  if inbox.isEmpty { break }
  let v = inbox.dequeue()
  outbox.send(v * 10)
}
let results = []
loop {
  if outbox.isEmpty { break }
  results.push(outbox.receive())
}
""")
        assert val(i, "results") == [10, 20, 30, 40, 50]
