"""Phase 123: Orchestrator per-step and full-summary analytics."""

from sprycode.interpreter import Interpreter, SPRY_UNDEFINED
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


class TestOrchestratorGetStepSummary:
    def test_step_summary_missing_returns_undefined(self):
        i = run("""
            let orch = Orchestrator.new()
            let s = orch.getStepSummary("ghost")
        """)
        assert val(i, "s") is SPRY_UNDEFINED

    def test_step_summary_unmanaged_no_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state + 1)
            let s = orch.getStepSummary("svc")
        """)
        s = val(i, "s")
        assert s["name"] == "svc"
        assert s["managed"] is False
        assert s["maxLoops"] is None
        assert s["enabled"] is True
        assert s["totalAttempts"] == 0
        assert s["peakAttempts"] == 0
        assert s["minAttempts"] == 0
        assert s["cycleCounts"] == 0
        assert s["avgAttempts"] is None

    def test_step_summary_managed_after_runs(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "m",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 3,
                5
            )
            orch.runCycle(0, 1)
            orch.runCycle(0, 2)
            let s = orch.getStepSummary("m")
        """)
        s = val(i, "s")
        assert s["name"] == "m"
        assert s["managed"] is True
        assert s["maxLoops"] == 5
        assert s["enabled"] is True
        assert s["totalAttempts"] == 6
        assert s["peakAttempts"] == 3
        assert s["minAttempts"] == 3
        assert s["cycleCounts"] == 2
        assert s["avgAttempts"] == 3.0

    def test_step_summary_asymmetric_attempts(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "x",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= cycle,
                5
            )
            orch.runCycle(0, 1)
            orch.runCycle(0, 3)
            let s = orch.getStepSummary("x")
        """)
        s = val(i, "s")
        assert s["totalAttempts"] == 4
        assert s["peakAttempts"] == 3
        assert s["minAttempts"] == 1
        assert s["cycleCounts"] == 2
        assert s["avgAttempts"] == 2.0

    def test_step_summary_disabled_step(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("svc", fn(state) => state)
            orch.disableStep("svc")
            let s = orch.getStepSummary("svc")
        """)
        s = val(i, "s")
        assert s["enabled"] is False

    def test_step_summary_reset_clears_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.runCycle(0, 1)
            orch.resetHistory()
            let s = orch.getStepSummary("a")
        """)
        s = val(i, "s")
        assert s["totalAttempts"] == 0
        assert s["cycleCounts"] == 0
        assert s["avgAttempts"] is None


class TestOrchestratorSummaryProperty:
    def test_summary_empty_orchestrator(self):
        i = run("""
            let orch = Orchestrator.new()
            let s = orch.summary
        """)
        assert val(i, "s") == []

    def test_summary_multiple_steps_no_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state)
            orch.addStep("b", fn(state) => state)
            let s = orch.summary
        """)
        s = val(i, "s")
        assert len(s) == 2
        assert s[0]["name"] == "a"
        assert s[1]["name"] == "b"
        assert s[0]["cycleCounts"] == 0
        assert s[1]["cycleCounts"] == 0

    def test_summary_after_run_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addManagedStep(
                "b",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= 2,
                5
            )
            orch.runCycle(0, 1)
            let s = orch.summary
        """)
        s = val(i, "s")
        assert len(s) == 2
        a = next(x for x in s if x["name"] == "a")
        b = next(x for x in s if x["name"] == "b")
        assert a["cycleCounts"] == 1
        assert a["totalAttempts"] == 1
        assert b["cycleCounts"] == 1
        assert b["totalAttempts"] == 2
        assert b["peakAttempts"] == 2
        assert b["minAttempts"] == 2
        assert b["avgAttempts"] == 2.0

    def test_summary_disabled_step_excluded_from_counts(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.addStep("b", fn(state) => state + 1)
            orch.disableStep("b")
            orch.runCycle(0, 1)
            let s = orch.summary
        """)
        s = val(i, "s")
        b = next(x for x in s if x["name"] == "b")
        assert b["enabled"] is False
        assert b["cycleCounts"] == 0

    def test_summary_reset_clears_history(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("a", fn(state) => state + 1)
            orch.runCycle(0, 1)
            orch.resetHistory()
            let s = orch.summary
        """)
        s = val(i, "s")
        assert s[0]["cycleCounts"] == 0
        assert s[0]["totalAttempts"] == 0
