"""Phase 111: Structural Microservice Pathway Primitives.

Tests covering:
  - EventBus — pub/sub event dispatch (loops over subscribers)
  - Supervisor — watches and restarts named services (loops until stable)
  - WorkerPool — drains a task queue through a worker function (loops until empty)
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
# EventBus
# ---------------------------------------------------------------------------


class TestEventBus:
    def test_eventbus_new_creates_instance(self):
        i = run("let bus = EventBus.new()")
        assert val(i, "bus") is not None

    def test_eventbus_subscribe_and_publish(self):
        i = run("""
            let bus = EventBus.new()
            var received = 0
            bus.subscribe("tick", fn(n) { received = n })
            bus.publish("tick", 42)
        """)
        assert val(i, "received") == 42

    def test_eventbus_publish_calls_all_subscribers(self):
        i = run("""
            let bus = EventBus.new()
            var calls = 0
            bus.subscribe("ev", fn(x) { calls = calls + 1 })
            bus.subscribe("ev", fn(x) { calls = calls + 1 })
            bus.subscribe("ev", fn(x) { calls = calls + 1 })
            bus.publish("ev", 1)
        """)
        assert val(i, "calls") == 3

    def test_eventbus_publish_returns_handler_count(self):
        i = run("""
            let bus = EventBus.new()
            bus.subscribe("x", fn(v) { })
            bus.subscribe("x", fn(v) { })
            let n = bus.publish("x", 0)
        """)
        assert val(i, "n") == 2

    def test_eventbus_publish_unknown_topic_returns_zero(self):
        i = run("""
            let bus = EventBus.new()
            let n = bus.publish("ghost", 1)
        """)
        assert val(i, "n") == 0

    def test_eventbus_subscriber_count(self):
        i = run("""
            let bus = EventBus.new()
            bus.subscribe("orders", fn(o) { })
            bus.subscribe("orders", fn(o) { })
            let n = bus.subscriberCount("orders")
        """)
        assert val(i, "n") == 2

    def test_eventbus_subscriber_count_unknown_topic(self):
        i = run("""
            let bus = EventBus.new()
            let n = bus.subscriberCount("missing")
        """)
        assert val(i, "n") == 0

    def test_eventbus_unsubscribe_removes_handler(self):
        i = run("""
            let bus = EventBus.new()
            var calls = 0
            fn h(v) { calls = calls + 1 }
            bus.subscribe("ev", h)
            bus.unsubscribe("ev", h)
            bus.publish("ev", 1)
        """)
        assert val(i, "calls") == 0

    def test_eventbus_topics_property(self):
        i = run("""
            let bus = EventBus.new()
            bus.subscribe("aaa", fn(v) { })
            bus.subscribe("bbb", fn(v) { })
            let t = bus.topics
        """)
        topics = val(i, "t")
        assert set(topics) == {"aaa", "bbb"}

    def test_eventbus_clear_removes_all_subscribers(self):
        i = run("""
            let bus = EventBus.new()
            var calls = 0
            bus.subscribe("ev", fn(v) { calls = calls + 1 })
            bus.clear()
            bus.publish("ev", 1)
        """)
        assert val(i, "calls") == 0

    def test_eventbus_accumulate_events_in_loop(self):
        """publish loops over all subscribers — integration with for loop."""
        i = run("""
            let bus = EventBus.new()
            var total = 0
            bus.subscribe("num", fn(n) { total = total + n })
            let nums = [1, 2, 3, 4, 5]
            for n in nums {
                bus.publish("num", n)
            }
        """)
        assert val(i, "total") == 15

    def test_eventbus_multiple_topics_independent(self):
        i = run("""
            let bus = EventBus.new()
            var a = 0
            var b = 0
            bus.subscribe("ping", fn(v) { a = a + v })
            bus.subscribe("pong", fn(v) { b = b + v })
            bus.publish("ping", 10)
            bus.publish("pong", 20)
        """)
        assert val(i, "a") == 10
        assert val(i, "b") == 20

    def test_eventbus_new_is_alias(self):
        i = run("""
            let bus = EventBus.new()
            var ok = bus !== null
        """)
        assert val(i, "ok") is True


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


class TestSupervisor:
    def test_supervisor_new_creates_instance(self):
        i = run("let sv = Supervisor.new(3)")
        assert val(i, "sv") is not None

    def test_supervisor_runs_healthy_service(self):
        i = run("""
            let sv = Supervisor.new(1)
            var ran = false
            sv.watch("svc", fn() { ran = true })
            sv.start()
        """)
        assert val(i, "ran") is True

    def test_supervisor_restarts_failing_service(self):
        i = run("""
            let sv = Supervisor.new(3)
            var tries = 0
            sv.watch("svc", fn() {
                tries = tries + 1
                if tries < 3 { throw "transient" }
            })
            sv.start()
        """)
        assert val(i, "tries") == 3
        assert val(i, "sv").restartCount == 2

    def test_supervisor_marks_service_failed_after_exhausting_restarts(self):
        i = run("""
            let sv = Supervisor.new(2)
            sv.watch("broken", fn() { throw "permanent failure" })
            let statusMap = sv.start()
        """)
        status = val(i, "statusMap")
        assert status["broken"] == "failed"

    def test_supervisor_restart_count_increments(self):
        i = run("""
            let sv = Supervisor.new(3)
            sv.watch("svc", fn() { throw "err" })
            sv.start()
            let rc = sv.restartCount
        """)
        assert val(i, "rc") == 3

    def test_supervisor_status_stopped_for_healthy(self):
        i = run("""
            let sv = Supervisor.new(1)
            sv.watch("ok", fn() { })
            sv.start()
            let s = sv.status
        """)
        status = val(i, "s")
        assert status["ok"] == "stopped"

    def test_supervisor_multiple_services_independent(self):
        i = run("""
            let sv = Supervisor.new(1)
            var aRan = false
            var bRan = false
            sv.watch("a", fn() { aRan = true })
            sv.watch("b", fn() { bRan = true })
            sv.start()
        """)
        assert val(i, "aRan") is True
        assert val(i, "bRan") is True

    def test_supervisor_healthy_plus_failing_services(self):
        i = run("""
            let sv = Supervisor.new(1)
            var ok = false
            sv.watch("good", fn() { ok = true })
            sv.watch("bad", fn() { throw "fail" })
            sv.start()
            let s = sv.status
        """)
        status = val(i, "s")
        assert status["good"] == "stopped"
        assert status["bad"] == "failed"
        assert val(i, "ok") is True

    def test_supervisor_zero_restarts_fails_immediately(self):
        i = run("""
            let sv = Supervisor.new(0)
            sv.watch("svc", fn() { throw "err" })
            sv.start()
            let rc = sv.restartCount
        """)
        assert val(i, "rc") == 0
        status = val(i, "sv").status
        assert status["svc"] == "failed"

    def test_supervisor_invalid_max_restarts_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let sv = Supervisor.new("bad")
            """)


# ---------------------------------------------------------------------------
# WorkerPool
# ---------------------------------------------------------------------------


class TestWorkerPool:
    def test_workerpool_new_creates_instance(self):
        i = run("let pool = WorkerPool.new(fn(x) => x)")
        assert val(i, "pool") is not None

    def test_workerpool_run_returns_results(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) => x * 2)
            pool.submit(1)
            pool.submit(2)
            pool.submit(3)
            let res = pool.run()
        """)
        assert val(i, "res") == [2, 4, 6]

    def test_workerpool_results_property(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) => x + 10)
            pool.submit(5)
            pool.submit(6)
            pool.run()
            let res = pool.results
        """)
        assert val(i, "res") == [15, 16]

    def test_workerpool_errors_captured(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) {
                if x == 2 { throw "bad item" }
                return x
            })
            pool.submit(1)
            pool.submit(2)
            pool.submit(3)
            pool.run()
            let errs = pool.errors
            let res = pool.results
        """)
        assert val(i, "res") == [1, 3]
        errs = val(i, "errs")
        assert len(errs) == 1
        assert errs[0]["item"] == 2

    def test_workerpool_pending_decreases_after_run(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) => x)
            pool.submit(1)
            pool.submit(2)
            let before = pool.pending
            pool.run()
            let after = pool.pending
        """)
        assert val(i, "before") == 2
        assert val(i, "after") == 0

    def test_workerpool_empty_run_returns_empty(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) => x)
            let res = pool.run()
        """)
        assert val(i, "res") == []

    def test_workerpool_submit_returns_queue_length(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) => x)
            let n1 = pool.submit("a")
            let n2 = pool.submit("b")
        """)
        assert val(i, "n1") == 1
        assert val(i, "n2") == 2

    def test_workerpool_clear_discards_pending(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) => x)
            pool.submit(1)
            pool.submit(2)
            pool.clear()
            let res = pool.run()
        """)
        assert val(i, "res") == []

    def test_workerpool_reset_clears_everything(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) => x)
            pool.submit(1)
            pool.run()
            pool.reset()
            let res = pool.results
            let errs = pool.errors
            let pending = pool.pending
        """)
        assert val(i, "res") == []
        assert val(i, "errs") == []
        assert val(i, "pending") == 0

    def test_workerpool_run_multiple_times_accumulates(self):
        i = run("""
            let pool = WorkerPool.new(fn(x) => x * 3)
            pool.submit(1)
            pool.run()
            pool.submit(2)
            pool.run()
            let res = pool.results
        """)
        assert val(i, "res") == [3, 6]

    def test_workerpool_loop_submit_then_run(self):
        """Use loop to submit items then run — loop until solved pattern."""
        i = run("""
            let pool = WorkerPool.new(fn(x) => x * x)
            var counter = 1
            loop {
                if counter > 5 { break }
                pool.submit(counter)
                counter = counter + 1
            }
            pool.run()
            let res = pool.results
        """)
        assert val(i, "res") == [1, 4, 9, 16, 25]


# ---------------------------------------------------------------------------
# Integration: EventBus + Supervisor + WorkerPool + micromanage
# ---------------------------------------------------------------------------


class TestMicroserviceStructuralPathway:
    def test_eventbus_drives_workerpool(self):
        """EventBus subscriber fills a WorkerPool; pool drains on each event."""
        i = run("""
            let bus = EventBus.new()
            let pool = WorkerPool.new(fn(item) => item * 10)
            var drains = 0
            bus.subscribe("batch", fn(item) {
                pool.submit(item)
                pool.run()
                drains = drains + 1
            })
            bus.publish("batch", 1)
            bus.publish("batch", 2)
            bus.publish("batch", 3)
            let res = pool.results
        """)
        assert val(i, "res") == [10, 20, 30]
        assert val(i, "drains") == 3

    def test_supervisor_restarts_until_eventbus_ready(self):
        """Supervisor retries until service succeeds; bus receives final event."""
        i = run("""
            let bus = EventBus.new()
            var ready = false
            bus.subscribe("ready", fn(v) { ready = v })

            var tries = 0
            let sv = Supervisor.new(3)
            sv.watch("svc", fn() {
                tries = tries + 1
                if tries < 2 { throw "not ready" }
                bus.publish("ready", true)
            })
            sv.start()
        """)
        assert val(i, "ready") is True
        assert val(i, "tries") == 2

    def test_micromanage_with_workerpool(self):
        """micromanage loop processes workerpool in steps until all results collected."""
        i = run("""
            let pool = WorkerPool.new(fn(x) => x + 1)
            pool.submit(10)
            pool.submit(20)
            pool.submit(30)
            let finalResult = micromanage(
                fn(attempt) {
                    pool.run()
                    return pool.results
                },
                fn(results, attempt) => pool.pending == 0,
                5
            )
        """)
        assert val(i, "finalResult") == [11, 21, 31]

    def test_workerpool_with_circuit_breaker_in_worker(self):
        """WorkerPool worker uses CircuitBreaker for resilience."""
        i = run("""
            let cb = CircuitBreaker.new({ threshold: 5 })
            let pool = WorkerPool.new(fn(item) {
                return cb.call(fn() => item * 2)
            })
            pool.submit(1)
            pool.submit(2)
            pool.submit(3)
            pool.run()
            let res = pool.results
        """)
        assert val(i, "res") == [2, 4, 6]

    def test_full_structural_pathway(self):
        """Full pathway: EventBus → WorkerPool → Supervisor → micromanage."""
        i = run("""
            let bus = EventBus.new()
            let pool = WorkerPool.new(fn(item) => item * 2)
            var totalPublished = 0

            // EventBus fills the pool
            bus.subscribe("job", fn(item) {
                pool.submit(item)
                totalPublished = totalPublished + 1
            })

            // Supervisor publishes jobs reliably
            let sv = Supervisor.new(2)
            sv.watch("producer", fn() {
                let items = [1, 2, 3]
                for item in items {
                    bus.publish("job", item)
                }
            })
            sv.start()

            // micromanage drains the pool until empty
            let result = micromanage(
                fn(attempt) {
                    pool.run()
                    return pool.results
                },
                fn(results, attempt) => pool.pending == 0,
                5
            )
        """)
        assert val(i, "totalPublished") == 3
        assert val(i, "result") == [2, 4, 6]
