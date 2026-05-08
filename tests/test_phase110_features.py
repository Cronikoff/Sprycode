"""Phase 110: Microservice Primitives.

Tests covering:
  - `loop { }` — infinite loop (break-able)
  - `retry(n) { }` — standalone retry block
  - Queue — in-memory FIFO queue (enqueue/dequeue/peek/size/isEmpty/clear/toArray)
  - Channel — sync message channel (send/receive/tryReceive/close/size/closed)
  - CircuitBreaker — closed/open/half-open fault-tolerance pattern
  - throttle(fn, ms) — rate-limit function calls
  - debounce(fn, ms) — debounce function calls
  - pipeline(...fns) — left-to-right function composition
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
# loop { } — infinite loop with break
# ---------------------------------------------------------------------------


class TestLoopStatement:
    def test_loop_breaks_immediately(self):
        i = run("""
            var x = 0
            loop {
                x = x + 1
                break
            }
        """)
        assert val(i, "x") == 1

    def test_loop_counts_to_five(self):
        i = run("""
            var count = 0
            loop {
                count = count + 1
                if count >= 5 { break }
            }
        """)
        assert val(i, "count") == 5

    def test_loop_accumulates(self):
        i = run("""
            var sum = 0
            var i = 0
            loop {
                i = i + 1
                sum = sum + i
                if i >= 4 { break }
            }
        """)
        assert val(i, "sum") == 10

    def test_loop_with_continue(self):
        """Loop with continue skips odd numbers."""
        i = run("""
            var sum = 0
            var n = 0
            loop {
                n = n + 1
                if n > 6 { break }
                if n % 2 != 0 { continue }
                sum = sum + n
            }
        """)
        # 2 + 4 + 6 = 12
        assert val(i, "sum") == 12

    def test_loop_variable_persists_after(self):
        i = run("""
            var result = 0
            loop {
                result = 42
                break
            }
        """)
        assert val(i, "result") == 42

    def test_loop_nested_break(self):
        """Break only exits the innermost loop."""
        i = run("""
            var outer = 0
            var inner = 0
            loop {
                outer = outer + 1
                loop {
                    inner = inner + 1
                    break
                }
                if outer >= 3 { break }
            }
        """)
        assert val(i, "outer") == 3
        assert val(i, "inner") == 3

    def test_loop_no_condition_needed(self):
        """loop requires no condition — it's always true."""
        i = run("""
            var done = false
            loop {
                done = true
                break
            }
        """)
        assert val(i, "done") is True

    def test_loop_body_executes_at_least_once(self):
        i = run("""
            var v = 0
            loop {
                v = 1
                break
            }
        """)
        assert val(i, "v") == 1

    def test_loop_collects_values(self):
        i = run("""
            var items = []
            var k = 0
            loop {
                k = k + 1
                items.push(k)
                if k >= 3 { break }
            }
        """)
        assert val(i, "items") == [1, 2, 3]

    def test_loop_exceeds_limit_raises(self):
        """A loop without break eventually hits the iteration limit."""
        with pytest.raises(SpryRuntimeError):
            run("""
                var x = 0
                loop {
                    x = x + 1
                }
            """)

    def test_loop_labeled_break(self):
        """Labeled break exits the outer loop."""
        i = run("""
            var outer = 0
            outer_loop: loop {
                outer = outer + 1
                loop {
                    break outer_loop
                }
            }
        """)
        assert val(i, "outer") == 1

    def test_loop_until_alias_matches_repeat_until(self):
        i = run("""
            var count = 0
            loop {
                count = count + 1
            } until count >= 3
        """)
        assert val(i, "count") == 3


# ---------------------------------------------------------------------------
# retry block
# ---------------------------------------------------------------------------


class TestRetryBlock:
    def test_retry_succeeds_first_attempt(self):
        """If body succeeds on first try, no retry needed."""
        i = run("""
            var attempts = 0
            retry(3) {
                attempts = attempts + 1
            }
        """)
        assert val(i, "attempts") == 1

    def test_retry_exhausts_all_attempts(self):
        """Body always throws — all retries consumed, exception propagated."""
        with pytest.raises(Exception):
            run("""
                retry(3) {
                    throw "always fails"
                }
            """)

    def test_retry_succeeds_on_second_attempt(self):
        """Body throws once then succeeds."""
        i = run("""
            var attempts = 0
            var done = false
            retry(3) {
                attempts = attempts + 1
                if attempts < 2 {
                    throw "not yet"
                }
                done = true
            }
        """)
        assert val(i, "attempts") == 2
        assert val(i, "done") is True

    def test_retry_one_attempt(self):
        """retry(1) tries exactly once."""
        with pytest.raises(Exception):
            run("""
                retry(1) {
                    throw "fail"
                }
            """)

    def test_retry_success_sets_value(self):
        i = run("""
            var x = 0
            retry(5) {
                x = 99
            }
        """)
        assert val(i, "x") == 99

    def test_retry_counter_tracks_attempts(self):
        """Verify retry increments attempt counter correctly."""
        i = run("""
            var count = 0
            retry(4) {
                count = count + 1
                if count < 3 { throw "retry me" }
            }
        """)
        assert val(i, "count") == 3


# ---------------------------------------------------------------------------
# retry(n) { } — retry block
# ---------------------------------------------------------------------------


class TestRetryStatement:
    def test_retry_succeeds_first_try(self):
        i = run('''
var v = 0
retry(3) {
    v = 42
}
''')
        assert val(i, 'v') == 42

    def test_retry_fails_and_throws_after_n(self):
        with pytest.raises(Exception):
            run('''
retry(3) {
    throw new Error("always fails")
}
''')

    def test_retry_succeeds_on_second_attempt(self):
        i = run('''
var attempts = 0
var v = 0
retry(3) {
    attempts = attempts + 1
    if attempts < 2 {
        throw new Error("not yet")
    }
    v = attempts
}
''')
        assert val(i, 'v') == 2
        assert val(i, 'attempts') == 2

    def test_retry_succeeds_on_third_attempt(self):
        i = run('''
var t = 0
retry(3) {
    t = t + 1
    if t < 3 { throw new Error("retry") }
}
let v = t
''')
        assert val(i, 'v') == 3

    def test_retry_with_one_always_fails(self):
        with pytest.raises(Exception):
            run('''
retry(1) {
    throw new Error("fail")
}
''')

    def test_retry_result_is_last_statement(self):
        i = run('''
var n = 0
retry(5) {
    n = n + 1
    if n < 4 { throw new Error("x") }
}
let v = n
''')
        assert val(i, 'v') == 4

    def test_retry_does_not_retry_on_success(self):
        i = run('''
var calls = 0
retry(10) {
    calls = calls + 1
}
let v = calls
''')
        assert val(i, 'v') == 1


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

    def test_queue_peek_does_not_remove(self):
        i = run("""
            let q = new Queue()
            q.enqueue(42)
            let p = q.peek()
            let s = q.size
        """)
        assert val(i, "p") == 42
        assert val(i, "s") == 1

    def test_queue_size_namespace_ctor(self):
        i = run("""
            let q = new Queue()
            q.enqueue("a")
            q.enqueue("b")
            q.enqueue("c")
            let s = q.size
        """)
        assert val(i, "s") == 3

    def test_queue_is_empty(self):
        i = run("""
            let q = new Queue()
            let e1 = q.isEmpty()
            q.enqueue(1)
            let e2 = q.isEmpty()
        """)
        assert val(i, "e1") is True
        assert val(i, "e2") is False

    def test_queue_dequeue_empty_throws(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let q = new Queue()
                q.dequeue()
            """)

    def test_queue_peek_empty_throws(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let q = new Queue()
                q.peek()
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

    def test_queue_to_array(self):
        i = run("""
            let q = new Queue()
            q.enqueue(10)
            q.enqueue(20)
            q.enqueue(30)
            let arr = q.toArray()
        """)
        assert val(i, "arr") == [10, 20, 30]

    def test_queue_fifo_order(self):
        i = run("""
            let q = new Queue()
            q.enqueue("first")
            q.enqueue("second")
            q.enqueue("third")
            let r1 = q.dequeue()
            let r2 = q.dequeue()
            let r3 = q.dequeue()
        """)
        assert val(i, "r1") == "first"
        assert val(i, "r2") == "second"
        assert val(i, "r3") == "third"

    def test_queue_size_decrements_on_dequeue(self):
        i = run("""
            let q = new Queue()
            q.enqueue(1)
            q.enqueue(2)
            q.dequeue()
            let s = q.size
        """)
        assert val(i, "s") == 1

    def test_queue_process_loop(self):
        """Use loop + Queue to process all items."""
        i = run("""
            let q = new Queue()
            q.enqueue(1)
            q.enqueue(2)
            q.enqueue(3)
            var total = 0
            loop {
                if q.isEmpty() { break }
                total = total + q.dequeue()
            }
        """)
        assert val(i, "total") == 6

    def test_queue_callable_without_new(self):
        i = run("""
            let q = Queue()
            q.enqueue(5)
            let v = q.dequeue()
        """)
        assert val(i, "v") == 5

    def test_queue_to_list_alias_and_create_ctor(self):
        i = run("""
            let q = Queue.create([1, 2])
            let items = q.toList()
        """)
        assert val(i, "items") == [1, 2]

    def test_queue_size(self):
        i = run('''
let q = Queue.new()
q.enqueue(10)
q.enqueue(20)
let v = q.size
''')
        assert val(i, 'v') == 2

    def test_queue_is_empty_initially(self):
        i = run('''
let q = Queue.new()
let v = q.isEmpty()
''')
        assert val(i, 'v') is True

    def test_queue_not_empty_after_enqueue(self):
        i = run('''
let q = Queue.new()
q.enqueue(99)
let v = q.isEmpty()
''')
        assert val(i, 'v') is False

    def test_queue_peek_does_not_remove_namespace_ctor(self):
        i = run('''
let q = Queue.new()
q.enqueue(42)
let p = q.peek()
let s = q.size
let v = p + s
''')
        assert val(i, 'v') == 43  # 42 + 1

    def test_queue_clear_namespace_ctor(self):
        i = run('''
let q = Queue.new()
q.enqueue(1)
q.enqueue(2)
q.clear()
let v = q.size
''')
        assert val(i, 'v') == 0

    def test_queue_to_array(self):
        i = run('''
let q = Queue.new()
q.enqueue(10)
q.enqueue(20)
q.enqueue(30)
let v = q.toArray()
''')
        assert val(i, 'v') == [10, 20, 30]

    def test_queue_dequeue_throws_when_empty(self):
        with pytest.raises(Exception):
            run('''
let q = Queue.new()
q.dequeue()
''')

    def test_queue_peek_throws_when_empty(self):
        with pytest.raises(Exception):
            run('''
let q = Queue.new()
q.peek()
''')

    def test_queue_drain_with_loop(self):
        i = run('''
let q = Queue.new()
q.enqueue(1)
q.enqueue(2)
q.enqueue(3)
var sum = 0
loop {
    if q.isEmpty() { break }
    sum = sum + q.dequeue()
}
let v = sum
''')
        assert val(i, 'v') == 6

    def test_queue_size_decreases_on_dequeue(self):
        i = run('''
let q = Queue.new()
q.enqueue("x")
q.enqueue("y")
q.dequeue()
let v = q.size
''')
        assert val(i, 'v') == 1


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------


class TestChannel:
    def test_channel_send_receive(self):
        i = run("""
            let ch = new Channel()
            ch.send(99)
            let v = ch.receive()
        """)
        assert val(i, "v") == 99

    def test_channel_fifo_order(self):
        i = run("""
            let ch = new Channel()
            ch.send("a")
            ch.send("b")
            ch.send("c")
            let r1 = ch.receive()
            let r2 = ch.receive()
            let r3 = ch.receive()
        """)
        assert val(i, "r1") == "a"
        assert val(i, "r2") == "b"
        assert val(i, "r3") == "c"

    def test_channel_buffered_count(self):
        i = run("""
            let ch = new Channel()
            ch.send(1)
            ch.send(2)
            let b = ch.buffered
        """)
        assert val(i, "b") == 2

    def test_channel_closed(self):
        i = run("""
            let ch = new Channel()
            let c1 = ch.closed
            ch.close()
            let c2 = ch.closed
        """)
        assert val(i, "c1") is False
        assert val(i, "c2") is True

    def test_channel_receive_empty_throws(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let ch = new Channel()
                ch.receive()
            """)

    def test_channel_send_after_close_throws(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let ch = new Channel()
                ch.close()
                ch.send(1)
            """)

    def test_channel_try_receive_empty_returns_undefined(self):
        from sprycode.interpreter import SPRY_UNDEFINED
        i = run("""
            let ch = new Channel()
            let v = ch.tryReceive()
        """)
        assert val(i, "v") is SPRY_UNDEFINED

    def test_channel_try_receive_has_value(self):
        i = run("""
            let ch = new Channel()
            ch.send(77)
            let v = ch.tryReceive()
        """)
        assert val(i, "v") == 77

    def test_channel_callable_without_new(self):
        i = run("""
            let ch = Channel()
            ch.send(42)
            let v = ch.receive()
        """)
        assert val(i, "v") == 42

    def test_channel_create_ctor_and_is_closed_alias(self):
        i = run("""
            let ch = Channel.create()
            let c1 = ch.isClosed
            ch.close()
            let c2 = ch.isClosed
        """)
        assert val(i, "c1") is False
        assert val(i, "c2") is True

    def test_channel_drain_with_loop(self):
        """Drain a channel into an array using loop."""
        from sprycode.interpreter import SPRY_UNDEFINED
        i = run("""
            let ch = new Channel()
            ch.send(10)
            ch.send(20)
            ch.send(30)
            ch.close()
            var results = []
            loop {
                let v = ch.tryReceive()
                if v === undefined { break }
                results.push(v)
            }
        """)
        assert val(i, "results") == [10, 20, 30]

    def test_channel_size(self):
        i = run('''
let ch = Channel.new()
ch.send("a")
ch.send("b")
let v = ch.size
''')
        assert val(i, 'v') == 2

    def test_channel_empty_initially(self):
        i = run('''
let ch = Channel.new()
let v = ch.isEmpty()
''')
        assert val(i, 'v') is True

    def test_channel_try_receive_empty(self):
        i = run('''
let ch = Channel.new()
let v = ch.tryReceive()
let ok = (v === undefined)
''')
        assert val(i, 'ok') is True

    def test_channel_close(self):
        i = run('''
let ch = Channel.new()
ch.close()
let v = ch.closed
''')
        assert val(i, 'v') is True

    def test_channel_receive_from_closed_empty_returns_undefined(self):
        i = run('''
let ch = Channel.new()
ch.send(42)
let a = ch.receive()
ch.close()
let b = ch.receive()
let v = (b === undefined)
''')
        assert val(i, 'v') is True

    def test_channel_send_throws_when_closed(self):
        with pytest.raises(Exception):
            run('''
let ch = Channel.new()
ch.close()
ch.send("boom")
''')

    def test_channel_bounded_capacity(self):
        with pytest.raises(Exception):
            run('''
let ch = Channel.new(2)
ch.send(1)
ch.send(2)
ch.send(3)
''')

    def test_channel_bounded_not_full(self):
        i = run('''
let ch = Channel.new(5)
ch.send("x")
ch.send("y")
let v = ch.size
''')
        assert val(i, 'v') == 2


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_circuit_breaker_starts_closed(self):
        i = run("""
            let cb = new CircuitBreaker({ threshold: 3, timeout: 1000 })
            let s = cb.state
        """)
        assert val(i, "s") == "closed"

    def test_circuit_breaker_call_success(self):
        i = run("""
            let cb = new CircuitBreaker({ threshold: 3, timeout: 1000 })
            let result = cb.call(fn() => 42)
        """)
        assert val(i, "result") == 42

    def test_circuit_breaker_opens_after_threshold_after_repeated_failures(self):
        """After 3 failures, circuit opens."""
        i = run("""
            let cb = new CircuitBreaker({ threshold: 3, timeout: 30000 })
            var failures = 0
            var i = 0
            loop {
                i = i + 1
                try {
                    cb.call(fn() { throw "fail" })
                } catch(e) {
                    failures = failures + 1
                }
                if i >= 4 { break }
            }
            let s = cb.state
        """)
        assert val(i, "s") == "open"

    def test_circuit_breaker_open_raises_fast(self):
        """Once open, calls fail immediately without executing fn."""
        with pytest.raises(SpryRuntimeError):
            run("""
                let cb = new CircuitBreaker({ threshold: 1, timeout: 30000 })
                try { cb.call(fn() { throw "fail" }) } catch(e) { }
                cb.call(fn() => 99)
            """)

    def test_circuit_breaker_reset_clears_state_and_failure_count(self):
        i = run("""
            let cb = new CircuitBreaker({ threshold: 2, timeout: 30000 })
            try { cb.call(fn() { throw "fail" }) } catch(e) { }
            try { cb.call(fn() { throw "fail" }) } catch(e) { }
            cb.reset()
            let s = cb.state
            let f = cb.failureCount
        """)
        assert val(i, "s") == "closed"
        assert val(i, "f") == 0

    def test_circuit_breaker_failure_count(self):
        i = run("""
            let cb = new CircuitBreaker({ threshold: 10, timeout: 30000 })
            try { cb.call(fn() { throw "fail" }) } catch(e) { }
            try { cb.call(fn() { throw "fail" }) } catch(e) { }
            let f = cb.failureCount
        """)
        assert val(i, "f") == 2

    def test_circuit_breaker_success_resets_failure_count(self):
        i = run("""
            let cb = new CircuitBreaker({ threshold: 10, timeout: 30000 })
            try { cb.call(fn() { throw "fail" }) } catch(e) { }
            cb.call(fn() => 1)
            let f = cb.failureCount
        """)
        assert val(i, "f") == 0

    def test_circuit_breaker_callable_without_new(self):
        i = run("""
            let cb = CircuitBreaker({ threshold: 5, timeout: 1000 })
            let s = cb.state
        """)
        assert val(i, "s") == "closed"

    def test_circuit_breaker_execute_alias_and_create_ctor(self):
        i = run("""
            let cb = CircuitBreaker.create(3, 1000)
            let v = cb.execute(fn(x) => x + 1, 41)
        """)
        assert val(i, "v") == 42

    def test_circuit_breaker_passes_successful_calls(self):
        i = run('''
fn add(x) { return x + 1 }
let cb = CircuitBreaker.new(3, 60000)
let v = cb.call(add, 41)
''')
        assert val(i, 'v') == 42

    def test_circuit_breaker_tracks_failures(self):
        i = run('''
fn boom() { throw new Error("fail") }
let cb = CircuitBreaker.new(3, 60000)
try { cb.call(boom) } catch(e) {}
try { cb.call(boom) } catch(e) {}
let v = cb.failures
''')
        assert val(i, 'v') == 2

    def test_circuit_breaker_opens_after_threshold(self):
        i = run('''
fn boom() { throw new Error("fail") }
let cb = CircuitBreaker.new(3, 60000)
try { cb.call(boom) } catch(e) {}
try { cb.call(boom) } catch(e) {}
try { cb.call(boom) } catch(e) {}
let v = cb.state
''')
        assert val(i, 'v') == "open"

    def test_circuit_breaker_rejects_when_open(self):
        with pytest.raises(Exception):
            run('''
fn boom() { throw new Error("fail") }
let cb = CircuitBreaker.new(1, 60000)
try { cb.call(boom) } catch(e) {}
cb.call(boom)
''')

    def test_circuit_breaker_reset(self):
        i = run('''
fn boom() { throw new Error("fail") }
let cb = CircuitBreaker.new(2, 60000)
try { cb.call(boom) } catch(e) {}
try { cb.call(boom) } catch(e) {}
cb.reset()
let v = cb.state
''')
        assert val(i, 'v') == "closed"

    def test_circuit_breaker_reset_clears_failures(self):
        i = run('''
fn boom() { throw new Error("fail") }
let cb = CircuitBreaker.new(5, 60000)
try { cb.call(boom) } catch(e) {}
try { cb.call(boom) } catch(e) {}
cb.reset()
let v = cb.failures
''')
        assert val(i, 'v') == 0

    def test_circuit_breaker_success_clears_failures(self):
        i = run('''
fn boom() { throw new Error("fail") }
fn ok() { return 1 }
let cb = CircuitBreaker.new(5, 60000)
try { cb.call(boom) } catch(e) {}
cb.call(ok)
let v = cb.failures
''')
        assert val(i, 'v') == 0

    def test_circuit_breaker_default_threshold(self):
        i = run('''
let cb = CircuitBreaker.new()
let v = cb.state
''')
        assert val(i, 'v') == "closed"


# ---------------------------------------------------------------------------
# throttle
# ---------------------------------------------------------------------------


class TestThrottle:
    def test_throttle_returns_callable(self):
        i = run("""
            var calls = 0
            let fn1 = fn() { calls = calls + 1 }
            let t = throttle(fn1, 1000)
            t()
        """)
        assert val(i, "calls") == 1

    def test_throttle_first_call_executes(self):
        """First call always executes."""
        i = run("""
            var result = 0
            let t = throttle(fn() { result = 42 }, 1000)
            t()
        """)
        assert val(i, "result") == 42

    def test_throttle_rapid_calls_skip(self):
        """Rapid successive calls are skipped if within delay window."""
        i = run("""
            var calls = 0
            let t = throttle(fn() { calls = calls + 1 }, 100000)
            t()
            t()
            t()
        """)
        # Only first call executes (delay is very large)
        assert val(i, "calls") == 1

    def test_throttle_zero_delay_passes_all(self):
        """With 0 delay, all calls execute."""
        i = run("""
            var calls = 0
            let t = throttle(fn() { calls = calls + 1 }, 0)
            t()
            t()
            t()
        """)
        assert val(i, "calls") == 3
    def test_throttle_calls_fn_first_time(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let throttled = throttle(inc, 1000)
throttled()
let v = called
''')
        assert val(i, 'v') == 1

    def test_throttle_suppresses_rapid_calls(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let throttled = throttle(inc, 10000)
throttled()
throttled()
throttled()
let v = called
''')
        assert val(i, 'v') == 1

    def test_throttle_zero_interval_always_calls(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let throttled = throttle(inc, 0)
throttled()
throttled()
throttled()
let v = called
''')
        assert val(i, 'v') == 3

    def test_throttle_returns_value(self):
        i = run('''
fn id(x) { return x }
let throttled = throttle(id, 0)
let v = throttled(42)
''')
        assert val(i, 'v') == 42

    def test_throttle_returns_last_value_on_suppressed(self):
        i = run('''
var counter = 0
fn nextVal() {
    counter = counter + 1
    return counter
}
let throttled = throttle(nextVal, 10000)
let a = throttled()
let b = throttled()
let v = b
''')
        assert val(i, 'v') == 1  # suppressed call returns last result


# ---------------------------------------------------------------------------
# debounce
# ---------------------------------------------------------------------------


class TestDebounce:
    def test_debounce_returns_callable(self):
        i = run("""
            var calls = 0
            let fn1 = fn() { calls = calls + 1 }
            let d = debounce(fn1, 500)
            d()
        """)
        # debounce defers — call count should be 0 (pending)
        assert val(i, "calls") == 0

    def test_debounce_flush_executes(self):
        """Calling flush() triggers the pending debounced call."""
        i = run("""
            var result = 0
            let fn1 = fn() { result = 99 }
            let d = debounce(fn1, 1000)
            d()
            d.flush()
        """)
        assert val(i, "result") == 99

    def test_debounce_only_last_call_executes_on_flush(self):
        """Multiple debounced calls: flush fires once."""
        i = run("""
            var calls = 0
            let fn1 = fn() { calls = calls + 1 }
            let d = debounce(fn1, 1000)
            d()
            d()
            d()
            d.flush()
        """)
        assert val(i, "calls") == 1

    def test_debounce_flush_without_pending_no_op(self):
        """Flush with no pending call is a no-op."""
        i = run("""
            var calls = 0
            let fn1 = fn() { calls = calls + 1 }
            let d = debounce(fn1, 1000)
            d.flush()
        """)
        assert val(i, "calls") == 0

    def test_debounce_repeated_flush(self):
        """Second flush after first doesn't re-execute."""
        i = run("""
            var calls = 0
            let fn1 = fn() { calls = calls + 1 }
            let d = debounce(fn1, 1000)
            d()
            d.flush()
            d.flush()
        """)
        assert val(i, "calls") == 1


# ---------------------------------------------------------------------------
# Integration: loop + retry + Queue + Channel + CircuitBreaker
# ---------------------------------------------------------------------------


class TestMicroServiceIntegration:
    def test_micromanage_loops_until_queue_is_empty(self):
        i = run("""
            let q = Queue.new([1, 2, 3, 4])
            var total = 0
            let result = micromanage(
                fn(attempt) {
                    if !q.isEmpty() {
                        total = total + q.dequeue()
                    }
                    return total
                },
                fn(last) => q.isEmpty(),
                10
            )
        """)
        assert val(i, "total") == 10
        assert val(i, "result") == 10

    def test_micromanage_tracks_attempts_in_structural_path(self):
        i = run("""
            var attempts = []
            let result = micromanage(
                fn(attempt) {
                    attempts.push(attempt)
                    return attempt
                },
                fn(last, attempt) => attempt >= 3,
                10
            )
        """)
        assert val(i, "attempts") == [1, 2, 3]
        assert val(i, "result") == 3

    def test_micromanage_raises_if_not_solved(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                micromanage(
                    fn(attempt) { return attempt },
                    fn(last, attempt) => false,
                    2
                )
            """)

    def test_micromanage_invalid_max_loops_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                micromanage(
                    fn(attempt) { return attempt },
                    fn(last, attempt) => true,
                    "not-a-number"
                )
            """)

    def test_micromanage_with_retry_and_circuit_breaker(self):
        i = run("""
            let cb = CircuitBreaker.new({ threshold: 5, timeout: 30000 })
            var tries = 0
            var done = false
            let result = micromanage(
                fn(attempt) {
                    retry(3) {
                        cb.call(fn() {
                            tries = tries + 1
                            if tries < 2 { throw "transient" }
                        })
                    }
                    done = true
                    return tries
                },
                fn(last) => done,
                5
            )
        """)
        assert val(i, "result") == 2
        assert val(i, "tries") == 2

    def test_queue_retry_process(self):
        """Process queue items with retry on failure."""
        i = run("""
            let q = new Queue()
            q.enqueue(1)
            q.enqueue(2)
            q.enqueue(3)
            var processed = []
            loop {
                if q.isEmpty() { break }
                let item = q.dequeue()
                retry(2) {
                    processed.push(item)
                }
            }
        """)
        assert val(i, "processed") == [1, 2, 3]
    def test_channel_loop_producer_consumer(self):
        """Producer sends to channel, consumer reads with loop."""
        i = run("""
            let ch = new Channel()
            ch.send(100)
            ch.send(200)
            ch.send(300)
            var total = 0
            var count = 0
            loop {
                if ch.buffered == 0 { break }
                total = total + ch.receive()
                count = count + 1
            }
        """)
        assert val(i, "total") == 600
        assert val(i, "count") == 3

    def test_circuit_breaker_with_retry(self):
        """CircuitBreaker protects a service; retry attempts recover."""
        i = run("""
            let cb = new CircuitBreaker({ threshold: 5, timeout: 30000 })
            var successes = 0
            retry(3) {
                cb.call(fn() { successes = successes + 1 })
            }
        """)
        assert val(i, "successes") == 1

    def test_loop_with_queue_and_channel(self):
        """Loop reads from queue, sends to channel."""
        i = run("""
            let q = new Queue()
            let ch = new Channel()
            q.enqueue("msg1")
            q.enqueue("msg2")
            loop {
                if q.isEmpty() { break }
                ch.send(q.dequeue())
            }
            let r1 = ch.receive()
            let r2 = ch.receive()
        """)
        assert val(i, "r1") == "msg1"
        assert val(i, "r2") == "msg2"
    def test_debounce_zero_delay_calls_immediately(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let debounced = debounce(inc, 0)
debounced()
let v = called
''')
        assert val(i, 'v') == 1

    def test_debounce_zero_delay_multiple_calls(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let debounced = debounce(inc, 0)
debounced()
debounced()
debounced()
let v = called
''')
        assert val(i, 'v') == 3

    def test_debounce_returns_result(self):
        i = run('''
fn double(x) { return x * 2 }
let debounced = debounce(double, 0)
let v = debounced(21)
''')
        assert val(i, 'v') == 42

    def test_debounce_flush(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let debounced = debounce(inc, 99999)
debounced()
debounced.flush()
let v = called
''')
        # With delay > 0, the first call is pending; flush forces it
        assert val(i, 'v') >= 1

    def test_debounce_cancel_prevents_call(self):
        i = run('''
var called = 0
fn inc() { called = called + 1 }
let debounced = debounce(inc, 99999)
debounced()
debounced.cancel()
let v = called
''')
        # cancel removes pending; zero calls should have occurred
        assert val(i, 'v') == 0


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_pipeline_single_fn(self):
        i = run('''
fn double(x) { return x * 2 }
let process = pipeline(double)
let v = process(21)
''')
        assert val(i, 'v') == 42

    def test_pipeline_two_fns(self):
        i = run('''
fn addOne(x) { return x + 1 }
fn double(x) { return x * 2 }
let process = pipeline(addOne, double)
let v = process(4)
''')
        assert val(i, 'v') == 10  # (4+1)*2

    def test_pipeline_three_fns(self):
        i = run('''
fn addOne(x) { return x + 1 }
fn double(x) { return x * 2 }
fn square(x) { return x * x }
let process = pipeline(addOne, double, square)
let v = process(2)
''')
        assert val(i, 'v') == 36  # ((2+1)*2)^2 = 6^2

    def test_pipeline_string_transforms(self):
        i = run('''
fn trim(s) { return s.trim() }
fn upper(s) { return s.toUpperCase() }
let process = pipeline(trim, upper)
let v = process("  hello  ")
''')
        assert val(i, 'v') == "HELLO"

    def test_pipeline_can_be_reused(self):
        i = run('''
fn inc(x) { return x + 1 }
let process = pipeline(inc, inc, inc)
let a = process(0)
let b = process(10)
let v = a + b
''')
        assert val(i, 'v') == 3 + 13  # 3 + 13

    def test_pipeline_identity(self):
        i = run('''
fn id(x) { return x }
let process = pipeline(id)
let v = process(99)
''')
        assert val(i, 'v') == 99

    def test_pipeline_with_array(self):
        i = run('''
fn doubled(arr) { return arr.map(x => x * 2) }
fn filtered(arr) { return arr.filter(x => x > 4) }
let process = pipeline(doubled, filtered)
let v = process([1, 2, 3, 4, 5])
''')
        assert val(i, 'v') == [6, 8, 10]

    def test_pipeline_composable(self):
        i = run('''
fn negate(x) { return -x }
fn abs(x) { return Math.abs(x) }
let process = pipeline(negate, abs)
let v = process(-5)
''')
        assert val(i, 'v') == 5
