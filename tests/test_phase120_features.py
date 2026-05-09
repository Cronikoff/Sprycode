"""Phase 120: Orchestrator full cycle-history timeline."""

import pytest
from sprycode.interpreter import Interpreter, SpryOrchestrator, SpryRuntimeError
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


class TestOrchestratorCycleHistory:
    def test_cycle_history_empty_initially(self):
        i = run("""
            let orch = Orchestrator.new()
            let hist = orch.cycleHistory
        """)
        assert val(i, "hist") == []

    def test_cycle_history_records_single_cycle_unmanaged_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state + 2)
            orch.runCycle(0, 1)
            let hist = orch.cycleHistory
        """)
        assert val(i, "hist") == [{"a": 1, "b": 1}]

    def test_cycle_history_records_multiple_cycles(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.runCycle(0, 1)
            orch.runCycle(10, 2)
            let hist = orch.cycleHistory
        """)
        assert val(i, "hist") == [{"a": 1}, {"a": 1}]

    def test_cycle_history_includes_managed_attempt_counts(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "stabilize",
                fn(state, cycle, name, attempt) => attempt,
                fn(state, cycle, name, attempt) => attempt >= 3,
                5
            )
            orch.runCycle(undefined, 1)
            let hist = orch.cycleHistory
            let last = orch.lastCycleAttempts
        """)
        assert val(i, "hist") == [{"stabilize": 3}]
        assert val(i, "last") == {"stabilize": 3}

    def test_cycle_history_skips_disabled_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state + 2)
            orch.disableStep("b")
            orch.runCycle(0, 1)
            let hist = orch.cycleHistory
        """)
        assert val(i, "hist") == [{"a": 1}]

    def test_cycle_history_populated_during_run_managed(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            let out = orch.runManaged(fn(state, cycle) => state >= 3, 0, 5)
            let hist = orch.cycleHistory
            let total = orch.totalCycles
        """)
        assert val(i, "out") == 3
        assert val(i, "hist") == [{"a": 1}, {"a": 1}, {"a": 1}]
        assert val(i, "total") == 3

    def test_cycle_history_cleared_by_reset_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.runCycle(0, 1)
            orch.resetHistory()
            let hist = orch.cycleHistory
            let last = orch.lastCycleAttempts
            let total = orch.totalCycles
        """)
        assert val(i, "hist") == []
        assert val(i, "last") == {}
        assert val(i, "total") == 0

    def test_cycle_history_is_copy_not_mutable_internal_state(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.runCycle(0, 1)
            let h1 = orch.cycleHistory
            h1[0]["a"] = 99
            let h2 = orch.cycleHistory
        """)
        assert val(i, "h2") == [{"a": 1}]

    def test_cycle_history_records_partial_cycle_before_managed_failure(self):
        orch = SpryOrchestrator(call_fn=None, truthy_fn=bool)
        orch.addStep("first", lambda state, cycle=1, name="first": state + 1)
        orch.addManagedStep(
            "stuck",
            lambda state, cycle=1, name="stuck", attempt=1: state + 1,
            lambda state, cycle=1, name="stuck", attempt=1: False,
            2,
        )
        with pytest.raises(SpryRuntimeError, match="never reached solved state"):
            orch.runCycle(0, 1)
        assert orch.cycleHistory == [{"first": 1, "stuck": 2}]
        assert orch.lastCycleAttempts == {"first": 1, "stuck": 2}
