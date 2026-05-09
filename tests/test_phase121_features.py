"""Phase 121: Orchestrator step-attempt aggregate analytics."""

from sprycode.interpreter import Interpreter
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


class TestOrchestratorStepAttemptAnalytics:
    def test_totals_and_peaks_empty_initially(self):
        i = run("""
            let orch = Orchestrator.new()
            let totals = orch.stepAttemptTotals
            let peaks = orch.stepAttemptPeaks
        """)
        assert val(i, "totals") == {}
        assert val(i, "peaks") == {}

    def test_totals_and_peaks_single_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addManagedStep(
                "b",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 3,
                5
            )
            orch.runCycle(0, 1)
            let totals = orch.stepAttemptTotals
            let peaks = orch.stepAttemptPeaks
        """)
        assert val(i, "totals") == {"a": 1, "b": 3}
        assert val(i, "peaks") == {"a": 1, "b": 3}

    def test_totals_and_peaks_multiple_cycles(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "x",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= cycle,
                5
            )
            orch.runCycle(0, 1)
            orch.runCycle(0, 2)
            orch.runCycle(0, 3)
            let totals = orch.stepAttemptTotals
            let peaks = orch.stepAttemptPeaks
        """)
        assert val(i, "totals") == {"x": 6}
        assert val(i, "peaks") == {"x": 3}

    def test_totals_and_peaks_skip_disabled_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state + 1)
            orch.disableStep("b")
            orch.runCycle(0, 1)
            let totals = orch.stepAttemptTotals
            let peaks = orch.stepAttemptPeaks
        """)
        assert val(i, "totals") == {"a": 1}
        assert val(i, "peaks") == {"a": 1}

    def test_totals_and_peaks_reset_with_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.runCycle(0, 1)
            orch.resetHistory()
            let totals = orch.stepAttemptTotals
            let peaks = orch.stepAttemptPeaks
            let hist = orch.cycleHistory
        """)
        assert val(i, "totals") == {}
        assert val(i, "peaks") == {}
        assert val(i, "hist") == []
