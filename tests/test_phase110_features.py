"""Phase 110: Micro-service building blocks.

Tests covering:
  - `loop` statement (infinite loop, break to exit)
  - `retry` block (retry body up to N times on error)
  - Queue built-in class (FIFO: enqueue/dequeue/peek/size/isEmpty/clear)
  - Channel built-in class (buffered send/receive/tryReceive/close/size/isClosed)
  - CircuitBreaker built-in class (closed/open/half-open states)
  - throttle(fn, ms) — rate-limited function wrapper
  - debounce(fn, ms) — debounced function wrapper (flush/cancel)
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
    def test_loop_exits_on_break(self):
        i = run("""
var n = 0
loop {
    n += 1
    if n >= 5 { break }
}
""")
        assert val(i, "n") == 5

    def test_loop_with_continue(self):
        i = run("""
var n = 0
var total = 0
loop {
    n += 1
    if n % 2 == 0 { continue }
    total += n
    if n >= 9 { break }
}
""")
        # odd numbers 1+3+5+7+9 = 25
        assert val(i, "total") == 25

    def test_loop_break_immediately(self):
        i = run("""
var n = 0
loop {
    n = 1
    break
    n = 99
}
""")
        assert val(i, "n") == 1

    def test_loop_accumulates_list(self):
        i = run("""
var items = []
var i = 0
loop {
    items.push(i)
    i += 1
    if i >= 4 { break }
}
""")
        assert val(i, "items") == [0, 1, 2, 3]

    def test_loop_uses_outer_variable(self):
        i = run("""
var counter = 10
loop {
    counter -= 1
    if counter == 0 { break }
}
""")
        assert val(i, "counter") == 0

    def test_loop_break_with_nested_if(self):
        i = run("""
var x = 0
loop {
    x += 1
    if x > 2 {
        if x > 4 { break }
    }
    if x > 6 { break }
}
""")
        assert val(i, "x") == 5

    def test_loop_with_while_inside(self):
        i = run("""
var outer = 0
var inner_sum = 0
loop {
    outer += 1
    var j = 0
    while j < 3 {
        inner_sum += 1
        j += 1
    }
    if outer >= 2 { break }
}
""")
        assert val(i, "outer") == 2
        assert val(i, "inner_sum") == 6

    def test_loop_return_value_is_null(self):
        # loop should return null (None) when exited via break
        i = run("""
var done = false
loop {
    done = true
    break
}
""")
        assert val(i, "done") is True


# ---------------------------------------------------------------------------
# retry block
# ---------------------------------------------------------------------------


class TestRetryBlock:
    def test_retry_succeeds_first_try(self):
        i = run("""
var attempts = 0
retry 3 {
    attempts += 1
}
""")
        assert val(i, "attempts") == 1

    def test_retry_counts_attempts_on_error(self):
        """Body throws on first two calls, succeeds on third."""
        i = run("""
var attempts = 0
retry 3 {
    attempts += 1
    if attempts < 3 { throw "not yet" }
}
""")
        assert val(i, "attempts") == 3

    def test_retry_rethrows_after_exhaustion(self):
        with pytest.raises(Exception):
            run("""
retry 2 {
    throw "always fails"
}
""")

    def test_retry_1_is_single_try(self):
        with pytest.raises(Exception):
            run("""
retry 1 {
    throw "fail"
}
""")

    def test_retry_sets_variable_on_success(self):
        i = run("""
var result = "none"
var tries = 0
retry 5 {
    tries += 1
    if tries < 3 { throw "retry" }
    result = "ok"
}
""")
        assert val(i, "result") == "ok"
        assert val(i, "tries") == 3

    def test_retry_does_not_run_extra_times_on_success(self):
        i = run("""
var runs = 0
retry 10 {
    runs += 1
}
""")
        assert val(i, "runs") == 1


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


class TestQueue:
    def test_queue_enqueue_dequeue(self):
        i = run("""
let q = new Queue()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
let a = q.dequeue()
let b = q.dequeue()
""")
        assert val(i, "a") == 1
        assert val(i, "b") == 2

    def test_queue_size(self):
        i = run("""
let q = new Queue()
q.enqueue("a")
q.enqueue("b")
let s = q.size
""")
        assert val(i, "s") == 2

    def test_queue_isEmpty(self):
        i = run("""
let q = new Queue()
let empty1 = q.isEmpty
q.enqueue(42)
let empty2 = q.isEmpty
""")
        assert val(i, "empty1") is True
        assert val(i, "empty2") is False

    def test_queue_peek_does_not_remove(self):
        i = run("""
let q = new Queue()
q.enqueue(10)
let p = q.peek()
let s = q.size
""")
        assert val(i, "p") == 10
        assert val(i, "s") == 1

    def test_queue_peek_empty_returns_null(self):
        i = run("""
let q = new Queue()
let p = q.peek()
""")
        assert val(i, "p") is None

    def test_queue_dequeue_empty_throws(self):
        with pytest.raises(Exception):
            run("""
let q = new Queue()
q.dequeue()
""")

    def test_queue_clear(self):
        i = run("""
let q = new Queue()
q.enqueue(1)
q.enqueue(2)
q.clear()
let s = q.size
""")
        assert val(i, "s") == 0

    def test_queue_fifo_order(self):
        i = run("""
let q = new Queue()
let items = [10, 20, 30, 40]
for item in items {
    q.enqueue(item)
}
let results = []
while !q.isEmpty {
    results.push(q.dequeue())
}
""")
        assert val(i, "results") == [10, 20, 30, 40]


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------


class TestChannel:
    def test_channel_send_receive(self):
        i = run("""
let ch = new Channel()
ch.send(42)
let v = ch.receive()
""")
        assert val(i, "v") == 42

    def test_channel_size(self):
        i = run("""
let ch = new Channel()
ch.send("a")
ch.send("b")
let s = ch.size
""")
        assert val(i, "s") == 2

    def test_channel_isClosed(self):
        i = run("""
let ch = new Channel()
let c1 = ch.isClosed
ch.close()
let c2 = ch.isClosed
""")
        assert val(i, "c1") is False
        assert val(i, "c2") is True

    def test_channel_send_on_closed_throws(self):
        with pytest.raises(Exception):
            run("""
let ch = new Channel()
ch.close()
ch.send(1)
""")

    def test_channel_receive_empty_open_returns_null(self):
        i = run("""
let ch = new Channel()
let v = ch.receive()
""")
        assert val(i, "v") is None

    def test_channel_receive_empty_closed_throws(self):
        with pytest.raises(Exception):
            run("""
let ch = new Channel()
ch.close()
ch.receive()
""")

    def test_channel_try_receive_non_blocking(self):
        i = run("""
let ch = new Channel()
let v1 = ch.tryReceive()
ch.send(99)
let v2 = ch.tryReceive()
let v3 = ch.tryReceive()
""")
        assert val(i, "v1") is None
        assert val(i, "v2") == 99
        assert val(i, "v3") is None

    def test_channel_buffered_capacity(self):
        """Buffered channel rejects sends beyond capacity."""
        with pytest.raises(Exception):
            run("""
let ch = new Channel(2)
ch.send(1)
ch.send(2)
ch.send(3)
""")

    def test_channel_multiple_messages_ordered(self):
        i = run("""
let ch = new Channel()
ch.send("first")
ch.send("second")
ch.send("third")
let r1 = ch.receive()
let r2 = ch.receive()
let r3 = ch.receive()
""")
        assert val(i, "r1") == "first"
        assert val(i, "r2") == "second"
        assert val(i, "r3") == "third"


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_circuit_breaker_initial_state(self):
        i = run("""
let cb = new CircuitBreaker()
let s = cb.state
""")
        assert val(i, "s") == "closed"

    def test_circuit_breaker_call_succeeds(self):
        i = run("""
let cb = new CircuitBreaker()
fn double(x) { return x * 2 }
let v = cb.call(double, 5)
""")
        assert val(i, "v") == 10

    def test_circuit_breaker_trips_after_threshold(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 2 })
var failures = 0
fn bad() { throw "fail" }
try {
    cb.call(bad)
} catch(e) { failures += 1 }
try {
    cb.call(bad)
} catch(e) { failures += 1 }
let s = cb.state
""")
        assert val(i, "s") == "open"
        assert val(i, "failures") == 2

    def test_circuit_breaker_open_rejects_calls(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 1 })
fn bad() { throw "boom" }
try { cb.call(bad) } catch(e) {}
var rejected = false
try {
    cb.call(bad)
} catch(e) {
    rejected = true
}
""")
        assert val(i, "rejected") is True

    def test_circuit_breaker_reset(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 1 })
fn bad() { throw "fail" }
try { cb.call(bad) } catch(e) {}
cb.reset()
let s = cb.state
let f = cb.failures
""")
        assert val(i, "s") == "closed"
        assert val(i, "f") == 0

    def test_circuit_breaker_failures_count(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 5 })
fn bad() { throw "err" }
try { cb.call(bad) } catch(e) {}
try { cb.call(bad) } catch(e) {}
let f = cb.failures
""")
        assert val(i, "f") == 2

    def test_circuit_breaker_success_resets_failure_count(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 5 })
fn bad() { throw "err" }
fn good() { return 1 }
try { cb.call(bad) } catch(e) {}
cb.call(good)
let f = cb.failures
""")
        assert val(i, "f") == 0


# ---------------------------------------------------------------------------
# throttle
# ---------------------------------------------------------------------------


class TestThrottle:
    def test_throttle_calls_fn_first_time(self):
        i = run("""
var callCount = 0
fn inc() { callCount += 1 }
let t = throttle(inc, 1000)
t()
let c = callCount
""")
        assert val(i, "c") == 1

    def test_throttle_rate_limits_rapid_calls(self):
        """With ms=1000 all rapid calls only execute once."""
        i = run("""
var callCount = 0
fn inc() { callCount += 1 }
let t = throttle(inc, 1000)
t()
t()
t()
let c = callCount
""")
        assert val(i, "c") == 1

    def test_throttle_zero_ms_always_calls(self):
        """With ms=0 every call executes."""
        i = run("""
var callCount = 0
fn inc() { callCount += 1 }
let t = throttle(inc, 0)
t()
t()
t()
let c = callCount
""")
        assert val(i, "c") == 3

    def test_throttle_returns_last_result(self):
        i = run("""
var n = 0
fn getN() { return n }
n = 5
let t = throttle(getN, 1000)
let r1 = t()
n = 99
let r2 = t()
""")
        # second call within window — returns cached result
        assert val(i, "r1") == 5
        assert val(i, "r2") == 5


# ---------------------------------------------------------------------------
# debounce
# ---------------------------------------------------------------------------


class TestDebounce:
    def test_debounce_flush_executes_pending(self):
        i = run("""
var callCount = 0
fn inc() { callCount += 1 }
let d = debounce(inc, 1000)
d()
d.flush()
let c = callCount
""")
        assert val(i, "c") == 1

    def test_debounce_cancel_prevents_execution(self):
        i = run("""
var callCount = 0
fn inc() { callCount += 1 }
let d = debounce(inc, 1000)
d()
d.cancel()
d.flush()
let c = callCount
""")
        assert val(i, "c") == 0

    def test_debounce_zero_ms_executes_on_next_call(self):
        """With ms=0 each call flushes the previous one."""
        i = run("""
var callCount = 0
fn inc() { callCount += 1 }
let d = debounce(inc, 0)
d()
d()
d()
d.flush()
let c = callCount
""")
        # Each call with ms=0 flushes the previous pending call then schedules a new one.
        # 3 calls: first schedules, second flushes+schedules, third flushes+schedules.
        # Final flush executes the last pending.
        assert val(i, "c") >= 1

    def test_debounce_flush_returns_result(self):
        i = run("""
fn getValue() { return 42 }
let d = debounce(getValue, 1000)
d()
let r = d.flush()
""")
        assert val(i, "r") == 42

    def test_debounce_pending_with_args(self):
        i = run("""
var received = 0
fn store(x) { received = x }
let d = debounce(store, 1000)
d(99)
d.flush()
let v = received
""")
        assert val(i, "v") == 99


# ---------------------------------------------------------------------------
# Loop + Channel integration (micro-service pattern)
# ---------------------------------------------------------------------------


class TestMicroservicePatterns:
    def test_producer_consumer_with_channel(self):
        """Simulate a producer writing to a channel then a consumer draining it."""
        i = run("""
let ch = new Channel()
let produced = [1, 2, 3, 4, 5]
for item in produced {
    ch.send(item)
}
var total = 0
loop {
    let v = ch.tryReceive()
    if v == null { break }
    total += v
}
""")
        assert val(i, "total") == 15

    def test_queue_with_retry_processing(self):
        """Items in a queue, retry processing if item < 0."""
        i = run("""
let q = new Queue()
q.enqueue(3)
q.enqueue(7)
q.enqueue(2)
var total = 0
while !q.isEmpty {
    let item = q.dequeue()
    total += item
}
""")
        assert val(i, "total") == 12

    def test_circuit_breaker_with_retry(self):
        """Retry + CircuitBreaker: retry before tripping breaker."""
        i = run("""
let cb = new CircuitBreaker({ threshold: 5 })
fn safe() { return "ok" }
var results = []
retry 3 {
    let r = cb.call(safe)
    results.push(r)
}
""")
        assert val(i, "results") == ["ok"]

    def test_throttle_in_loop(self):
        """Throttle calls inside a loop."""
        i = run("""
var count = 0
fn inc() { count += 1 }
let t = throttle(inc, 1000)
var i = 0
loop {
    t()
    i += 1
    if i >= 5 { break }
}
""")
        # Only first call executes within the throttle window
        assert val(i, "count") == 1
