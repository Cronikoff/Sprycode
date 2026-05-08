"""Phase 110: Microservice primitives.

Tests covering:
  - loop statement (infinite loop until break)
  - retry block (retry on error up to N times)
  - Queue (FIFO enqueue/dequeue/peek/size/isEmpty/clear/toArray)
  - Channel (send/receive/tryReceive/close/size/capacity)
  - CircuitBreaker (call/state/reset/threshold/failures)
  - throttle(fn, ms)
  - debounce(fn, ms)
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
    def test_loop_breaks_immediately(self):
        i = run("""
let n = 0
loop {
    n = n + 1
    break
}
""")
        assert val(i, "n") == 1

    def test_loop_counts_to_five(self):
        i = run("""
let n = 0
loop {
    n = n + 1
    if n >= 5 { break }
}
""")
        assert val(i, "n") == 5

    def test_loop_continue(self):
        i = run("""
let sum = 0
let k = 0
loop {
    k = k + 1
    if k > 10 { break }
    if k % 2 == 0 { continue }
    sum = sum + k
}
""")
        # sum of odd numbers 1..9 = 1+3+5+7+9 = 25
        assert val(i, "sum") == 25

    def test_loop_scope_isolation(self):
        i = run("""
let outer = 0
loop {
    let inner = 99
    outer = inner
    break
}
""")
        assert val(i, "outer") == 99

    def test_loop_nested(self):
        i = run("""
let count = 0
loop {
    loop {
        count = count + 1
        if count >= 3 { break }
    }
    break
}
""")
        assert val(i, "count") == 3

    def test_loop_exceeds_limit_raises(self):
        with pytest.raises(Exception):
            run("""
loop {
    let x = 1
}
""")


# ---------------------------------------------------------------------------
# retry block
# ---------------------------------------------------------------------------

class TestRetryBlock:
    def test_retry_success_on_first_attempt(self):
        i = run("""
let attempts = 0
retry(3) {
    attempts = attempts + 1
}
""")
        assert val(i, "attempts") == 1

    def test_retry_counts_attempts(self):
        i = run("""
let count = 0
retry(3) {
    count = count + 1
    if count < 3 {
        throw "fail"
    }
}
""")
        assert val(i, "count") == 3

    def test_retry_exhausted_raises(self):
        with pytest.raises(Exception):
            run("""
retry(2) {
    throw "always fail"
}
""")

    def test_retry_one_attempt_minimum(self):
        i = run("""
let n = 0
retry(1) {
    n = n + 1
}
""")
        assert val(i, "n") == 1

    def test_retry_with_delay_option_accepted(self):
        """retry(n, { delay: ms }) syntax parses and runs correctly."""
        i = run("""
let n = 0
retry(3, { delay: 0 }) {
    n = n + 1
    if n < 3 { throw "retry" }
}
""")
        assert val(i, "n") == 3

    def test_retry_with_positional_delay(self):
        """retry(n, ms) positional delay syntax."""
        i = run("""
let n = 0
retry(2, 0) {
    n = n + 1
}
""")
        assert val(i, "n") == 1  # succeeds on first try


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

class TestQueue:
    def test_queue_basic_enqueue_dequeue(self):
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
q.enqueue("x")
q.enqueue("y")
let s = q.size
""")
        assert val(i, "s") == 2

    def test_queue_is_empty(self):
        i = run("""
let q = new Queue()
let empty1 = q.isEmpty()
q.enqueue(42)
let empty2 = q.isEmpty()
""")
        assert val(i, "empty1") is True
        assert val(i, "empty2") is False

    def test_queue_peek(self):
        i = run("""
let q = new Queue()
q.enqueue("first")
q.enqueue("second")
let front = q.peek()
let sizeAfterPeek = q.size
""")
        assert val(i, "front") == "first"
        assert val(i, "sizeAfterPeek") == 2

    def test_queue_clear(self):
        i = run("""
let q = new Queue()
q.enqueue(1)
q.enqueue(2)
q.clear()
let s = q.size
""")
        assert val(i, "s") == 0

    def test_queue_to_array(self):
        i = run("""
let q = new Queue()
q.enqueue(10)
q.enqueue(20)
let arr = q.toArray()
""")
        assert val(i, "arr") == [10, 20]

    def test_queue_dequeue_empty_raises(self):
        with pytest.raises(Exception):
            run("""
let q = new Queue()
q.dequeue()
""")

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

    def test_queue_loop_drain(self):
        """Queue used inside a loop."""
        i = run("""
let q = new Queue()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
let sum = 0
loop {
    if q.isEmpty() { break }
    sum = sum + q.dequeue()
}
""")
        assert val(i, "sum") == 6


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

    def test_channel_try_receive_ok(self):
        i = run("""
let ch = new Channel()
ch.send(99)
let res = ch.tryReceive()
let v = res.value
let ok = res.ok
""")
        assert val(i, "v") == 99
        assert val(i, "ok") is True

    def test_channel_try_receive_empty(self):
        i = run("""
let ch = new Channel()
let res = ch.tryReceive()
let ok = res.ok
""")
        assert val(i, "ok") is False

    def test_channel_receive_empty_raises(self):
        with pytest.raises(Exception):
            run("""
let ch = new Channel()
ch.receive()
""")

    def test_channel_close(self):
        i = run("""
let ch = new Channel()
ch.close()
let isClosed = ch.closed
""")
        assert val(i, "isClosed") is True

    def test_channel_send_after_close_raises(self):
        with pytest.raises(Exception):
            run("""
let ch = new Channel()
ch.close()
ch.send(1)
""")

    def test_channel_capacity(self):
        i = run("""
let ch = new Channel(5)
let cap = ch.capacity
""")
        assert val(i, "cap") == 5

    def test_channel_buffer_full_raises(self):
        with pytest.raises(Exception):
            run("""
let ch = new Channel(2)
ch.send(1)
ch.send(2)
ch.send(3)
""")

    def test_channel_fifo_order(self):
        i = run("""
let ch = new Channel()
ch.send("x")
ch.send("y")
let r1 = ch.receive()
let r2 = ch.receive()
""")
        assert val(i, "r1") == "x"
        assert val(i, "r2") == "y"

    def test_channel_loop_drain(self):
        """Channel used inside a loop."""
        i = run("""
let ch = new Channel()
ch.send(2)
ch.send(4)
ch.send(6)
let product = 1
loop {
    let res = ch.tryReceive()
    if !res.ok { break }
    product = product * res.value
}
""")
        assert val(i, "product") == 48


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_circuit_breaker_initial_state(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 3 })
let s = cb.state
""")
        assert val(i, "s") == "closed"

    def test_circuit_breaker_successful_call(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 3 })
let result = cb.call(fn() { return 42 })
""")
        assert val(i, "result") == 42

    def test_circuit_breaker_opens_after_threshold(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 2, timeout: 60000 })
let errors = 0
fn risky() { throw "fail" }
try { cb.call(risky) } catch(e) { errors = errors + 1 }
try { cb.call(risky) } catch(e) { errors = errors + 1 }
let s = cb.state
""")
        assert val(i, "s") == "open"
        assert val(i, "errors") == 2

    def test_circuit_breaker_open_rejects_fast(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 1, timeout: 60000 })
fn risky() { throw "fail" }
try { cb.call(risky) } catch(e) {}
let fast_rejected = false
try {
    cb.call(fn() { return 1 })
} catch(e) {
    fast_rejected = true
}
""")
        assert val(i, "fast_rejected") is True

    def test_circuit_breaker_reset(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 1, timeout: 60000 })
fn risky() { throw "fail" }
try { cb.call(risky) } catch(e) {}
cb.reset()
let s = cb.state
""")
        assert val(i, "s") == "closed"

    def test_circuit_breaker_failure_count(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 5, timeout: 60000 })
fn risky() { throw "fail" }
try { cb.call(risky) } catch(e) {}
try { cb.call(risky) } catch(e) {}
let f = cb.failures
""")
        assert val(i, "f") == 2

    def test_circuit_breaker_threshold_property(self):
        i = run("""
let cb = new CircuitBreaker({ threshold: 7 })
let t = cb.threshold
""")
        assert val(i, "t") == 7


# ---------------------------------------------------------------------------
# throttle
# ---------------------------------------------------------------------------

class TestThrottle:
    def test_throttle_calls_fn_first_time(self):
        i = run("""
let calls = 0
let inc = fn() { calls = calls + 1 }
let t = throttle(inc, 100)
t()
""")
        assert val(i, "calls") == 1

    def test_throttle_blocks_rapid_calls(self):
        i = run("""
let calls = 0
let inc = fn() { calls = calls + 1 }
let t = throttle(inc, 10000)
t()
t()
t()
""")
        # Second and third calls within interval are suppressed
        assert val(i, "calls") == 1

    def test_throttle_zero_interval_all_pass(self):
        """throttle with 0ms interval passes all calls."""
        i = run("""
let calls = 0
let inc = fn() { calls = calls + 1 }
let t = throttle(inc, 0)
t()
t()
t()
""")
        assert val(i, "calls") == 3


# ---------------------------------------------------------------------------
# debounce
# ---------------------------------------------------------------------------

class TestDebounce:
    def test_debounce_returns_undefined_immediately(self):
        """debounce defers execution; synchronous call returns undefined."""
        i = run("""
let calls = 0
let inc = fn() { calls = calls + 1 }
let d = debounce(inc, 100)
d()
""")
        # In sync SpryCode, debounce does not fire immediately
        assert val(i, "calls") == 0

    def test_debounce_flush_fires(self):
        i = run("""
let calls = 0
let inc = fn() { calls = calls + 1 }
let d = debounce(inc, 100)
d()
d.flush()
""")
        assert val(i, "calls") == 1

    def test_debounce_cancel(self):
        i = run("""
let calls = 0
let inc = fn() { calls = calls + 1 }
let d = debounce(inc, 100)
d()
d.cancel()
d.flush()
""")
        assert val(i, "calls") == 0

    def test_debounce_multiple_calls_then_flush(self):
        """Only the last call's args matter after multiple rapid calls."""
        i = run("""
let last = 0
let set = fn(x) { last = x }
let d = debounce(set, 100)
d(1)
d(2)
d(3)
d.flush()
""")
        assert val(i, "last") == 3


# ---------------------------------------------------------------------------
# Microservice integration: loop + Queue + Channel
# ---------------------------------------------------------------------------

class TestMicroserviceIntegration:
    def test_producer_consumer_via_queue(self):
        """Producer pushes items; consumer drains via loop."""
        i = run("""
let q = new Queue()
let results = []

fn produce(items) {
    for let item of items {
        q.enqueue(item)
    }
}

fn consume() {
    loop {
        if q.isEmpty() { break }
        results.push(q.dequeue())
    }
}

produce([10, 20, 30])
consume()
""")
        assert val(i, "results") == [10, 20, 30]

    def test_channel_pipeline(self):
        """Items pass through two channels as a pipeline stage."""
        i = run("""
let ch1 = new Channel()
let ch2 = new Channel()

ch1.send(1)
ch1.send(2)
ch1.send(3)

loop {
    let msg = ch1.tryReceive()
    if !msg.ok { break }
    ch2.send(msg.value * 2)
}

let out = []
loop {
    let msg = ch2.tryReceive()
    if !msg.ok { break }
    out.push(msg.value)
}
""")
        assert val(i, "out") == [2, 4, 6]

    def test_retry_with_circuit_breaker(self):
        """Circuit breaker + retry: after threshold failures, CB opens and retry fails."""
        i = run("""
let cb = new CircuitBreaker({ threshold: 2, timeout: 60000 })
fn unreliable() { throw "service unavailable" }
let final_state = "unknown"
try {
    retry(5) {
        cb.call(unreliable)
    }
} catch(e) {
    final_state = cb.state
}
""")
        assert val(i, "final_state") == "open"

    def test_queue_retry_processing(self):
        """Process queue items with retry, re-enqueue failed items."""
        i = run("""
let q = new Queue()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
let processed = []
let attempts = 0

loop {
    if q.isEmpty() { break }
    let item = q.dequeue()
    retry(2) {
        attempts = attempts + 1
        processed.push(item)
    }
}
""")
        assert val(i, "processed") == [1, 2, 3]
        assert val(i, "attempts") == 3
