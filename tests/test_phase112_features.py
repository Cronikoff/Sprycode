"""Phase 112: Registry + Orchestrator microservice loop primitives.

Tests covering:
  - ServiceRegistry — register/resolve/call named services
  - Orchestrator — loop configured steps until solved
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


class TestServiceRegistry:
    def test_new_creates_registry(self):
        i = run("let reg = ServiceRegistry.new()")
        assert val(i, "reg") is not None

    def test_register_has_get(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("sum", fn(x, y) => x + y)
            let exists = reg.has("sum")
            let svc = reg.get("sum")
        """)
        assert val(i, "exists") is True
        assert val(i, "svc") is not None

    def test_get_missing_returns_undefined(self):
        i = run("""
            let reg = ServiceRegistry.new()
            let missing = reg.get("none") === undefined
        """)
        assert val(i, "missing") is True

    def test_unregister_returns_true_when_removed(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("svc", fn() { })
            let removed = reg.unregister("svc")
        """)
        assert val(i, "removed") is True

    def test_unregister_returns_false_when_missing(self):
        i = run("""
            let reg = ServiceRegistry.new()
            let removed = reg.unregister("ghost")
        """)
        assert val(i, "removed") is False

    def test_size_and_names(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("a", fn() => 1)
            reg.register("b", fn() => 2)
            let n = reg.size
            let names = reg.names
        """)
        assert val(i, "n") == 2
        assert set(val(i, "names")) == {"a", "b"}

    def test_call_invokes_registered_service(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("double", fn(x) => x * 2)
            let out = reg.call("double", 21)
        """)
        assert val(i, "out") == 42

    def test_call_missing_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let reg = ServiceRegistry.new()
                reg.call("missing")
            """)

    def test_clear_resets_registry(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("a", fn() => 1)
            reg.register("b", fn() => 2)
            reg.clear()
            let n = reg.size
        """)
        assert val(i, "n") == 0


class TestOrchestrator:
    def test_new_creates_orchestrator(self):
        i = run("let orch = Orchestrator.new()")
        assert val(i, "orch") is not None

    def test_add_step_returns_count(self):
        i = run("""
            let orch = Orchestrator.new()
            let n1 = orch.addStep("a", fn(state) => state)
            let n2 = orch.addStep("b", fn(state) => state)
        """)
        assert val(i, "n1") == 1
        assert val(i, "n2") == 2

    def test_run_cycle_applies_steps_in_order(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("add2", fn(state) => state + 2)
            orch.addStep("times3", fn(state) => state * 3)
            let out = orch.runCycle(1)
        """)
        assert val(i, "out") == 9

    def test_run_cycle_passes_cycle_and_name(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("stepA", fn(state, cycle, name) => state + cycle)
            orch.addStep("stepB", fn(state, cycle, name) => state + len(name))
            let out = orch.runCycle(0, 3)
        """)
        assert val(i, "out") == 8

    def test_run_until_solved_loops_multiple_cycles(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("inc", fn(state) => state + 1)
            let out = orch.runUntilSolved(
                fn(state, cycle) => state >= 5,
                0,
                10
            )
        """)
        assert val(i, "out") == 5

    def test_run_until_solved_raises_when_not_solved(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let orch = Orchestrator.new()
                orch.addStep("noop", fn(state) => state)
                orch.runUntilSolved(fn(state) => false, 1, 3)
            """)

    def test_run_until_solved_invalid_max_loops_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let orch = Orchestrator.new()
                orch.addStep("noop", fn(state) => state)
                orch.runUntilSolved(fn(state) => true, 1, "bad")
            """)

    def test_remove_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state + 10)
            let removed = orch.removeStep("a")
            let out = orch.runCycle(0)
        """)
        assert val(i, "removed") is True
        assert val(i, "out") == 10

    def test_clear_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.clearSteps()
            let out = orch.runCycle(7)
            let count = orch.stepCount
        """)
        assert val(i, "out") == 7
        assert val(i, "count") == 0

    def test_step_names_and_count(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("alpha", fn(state) => state)
            orch.addStep("beta", fn(state) => state)
            let names = orch.stepNames
            let count = orch.stepCount
        """)
        assert val(i, "names") == ["alpha", "beta"]
        assert val(i, "count") == 2

    def test_load_registry_adds_services_as_steps(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("inc", fn(state) => state + 1)
            reg.register("mul2", fn(state) => state * 2)
            let orch = Orchestrator.new()
            let n = orch.loadRegistry(reg)
            let out = orch.runCycle(2)
        """)
        assert val(i, "n") == 2
        assert val(i, "out") == 6

    def test_load_registry_invalid_value_raises(self):
        with pytest.raises(SpryRuntimeError):
            run("""
                let orch = Orchestrator.new()
                orch.loadRegistry({})
            """)


class TestStructuralPathwayIntegration:
    def test_registry_orchestrator_micromanage_full_path(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("fetch", fn(state, cycle) {
                var base = state
                if base == undefined { base = 0 }
                return base + 2
            })
            reg.register("normalize", fn(state) => state - 1)

            let orch = Orchestrator.new()
            orch.loadRegistry(reg)
            var current = undefined

            let final = micromanage(
                fn(attempt) {
                    current = orch.runCycle(current, attempt)
                    return current
                },
                fn(last, attempt) => last >= 7,
                10
            )
        """)
        assert val(i, "final") == 7

    def test_supervisor_starts_orchestrated_service(self):
        i = run("""
            let reg = ServiceRegistry.new()
            reg.register("step", fn(state) {
                if state == undefined { return 1 }
                return state + 1
            })
            let orch = Orchestrator.new()
            orch.loadRegistry(reg)

            var final = 0
            let sv = Supervisor.new(2)
            sv.watch("orchestrated", fn() {
                final = orch.runUntilSolved(fn(state) => state >= 3, undefined, 5)
            })
            sv.start()
        """)
        assert val(i, "final") == 3
