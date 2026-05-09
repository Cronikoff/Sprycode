"""Phase 116: Orchestrator loop-history tracking for micromanaged pathways."""

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


class TestOrchestratorHistoryTracking:
    def test_last_cycle_attempts_plain_step_is_one(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            orch.runCycle(0, 1)
            let hist = orch.lastCycleAttempts
        """)
        hist = val(i, "hist")
        assert isinstance(hist, dict)
        assert hist["plain"] == 1

    def test_last_cycle_attempts_managed_step_records_attempts(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "refine",
                fn(state, cycle, name, attempt) {
                    if state == undefined { return attempt }
                    return state + attempt
                },
                fn(state, cycle, name, attempt) => state >= 6,
                5
            )
            orch.runCycle(undefined, 1)
            let hist = orch.lastCycleAttempts
        """)
        hist = val(i, "hist")
        assert isinstance(hist, dict)
        # state reaches 6 at attempt 3 (1+2+3), so attempts should be 3
        assert hist["refine"] == 3

    def test_last_cycle_attempts_updates_on_each_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "s",
                fn(state, cycle, name, attempt) => attempt,
                fn(state, cycle, name, attempt) => attempt >= 2,
                5
            )
            orch.runCycle(0, 1)
            let hist1 = orch.lastCycleAttempts
            orch.runCycle(0, 2)
            let hist2 = orch.lastCycleAttempts
        """)
        assert val(i, "hist1")["s"] == 2
        assert val(i, "hist2")["s"] == 2

    def test_total_cycles_increments_with_run_managed(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("inc", fn(state) => state + 1)
            orch.runManaged(fn(state, cycle) => state >= 3, 0, 10)
            let total = orch.totalCycles
        """)
        assert val(i, "total") == 3

    def test_total_cycles_increments_with_run_until_solved(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("inc", fn(state) => state + 2)
            orch.runUntilSolved(fn(state) => state >= 6, 0, 10)
            let total = orch.totalCycles
        """)
        assert val(i, "total") == 3

    def test_total_cycles_start_at_zero(self):
        i = run("""
            let orch = Orchestrator.new()
            let total = orch.totalCycles
        """)
        assert val(i, "total") == 0

    def test_reset_history_clears_attempts_and_cycle_count(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("inc", fn(state) => state + 1)
            orch.runManaged(fn(state) => state >= 2, 0, 5)
            orch.resetHistory()
            let total = orch.totalCycles
            let hist = orch.lastCycleAttempts
        """)
        assert val(i, "total") == 0
        hist = val(i, "hist")
        assert hist == {}

    def test_last_cycle_attempts_mixed_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            orch.addManagedStep(
                "managed",
                fn(state, cycle, name, attempt) => state + attempt,
                fn(state, cycle, name, attempt) => attempt >= 2,
                4
            )
            orch.runCycle(0, 1)
            let hist = orch.lastCycleAttempts
        """)
        hist = val(i, "hist")
        assert hist["plain"] == 1
        assert hist["managed"] == 2

    def test_total_cycles_accumulates_across_run_managed_calls(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("inc", fn(state) => state + 1)
            orch.runManaged(fn(state) => state >= 2, 0, 5)
            orch.runManaged(fn(state) => state >= 4, 2, 5)
            let total = orch.totalCycles
        """)
        assert val(i, "total") == 4
