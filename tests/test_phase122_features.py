"""Phase 122: Orchestrator per-step participation and average attempt analytics."""

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


class TestOrchestratorStepParticipationAnalytics:
    def test_cycle_counts_and_averages_empty_initially(self):
        i = run("""
            let orch = Orchestrator.new()
            let counts = orch.stepCycleCounts
            let avgs = orch.stepAttemptAverages
        """)
        assert val(i, "counts") == {}
        assert val(i, "avgs") == {}

    def test_cycle_counts_and_averages_single_cycle(self):
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
            let counts = orch.stepCycleCounts
            let avgs = orch.stepAttemptAverages
        """)
        assert val(i, "counts") == {"a": 1, "b": 1}
        assert val(i, "avgs") == {"a": 1.0, "b": 3.0}

    def test_cycle_counts_and_averages_multiple_cycles(self):
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
            let counts = orch.stepCycleCounts
            let avgs = orch.stepAttemptAverages
        """)
        assert val(i, "counts") == {"x": 3}
        assert val(i, "avgs") == {"x": 2.0}

    def test_cycle_counts_and_averages_skip_disabled_steps(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state + 1)
            orch.disableStep("b")
            orch.runCycle(0, 1)
            let counts = orch.stepCycleCounts
            let avgs = orch.stepAttemptAverages
        """)
        assert val(i, "counts") == {"a": 1}
        assert val(i, "avgs") == {"a": 1.0}

    def test_cycle_counts_and_averages_reset_with_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.runCycle(0, 1)
            orch.resetHistory()
            let counts = orch.stepCycleCounts
            let avgs = orch.stepAttemptAverages
            let hist = orch.cycleHistory
        """)
        assert val(i, "counts") == {}
        assert val(i, "avgs") == {}
        assert val(i, "hist") == []
