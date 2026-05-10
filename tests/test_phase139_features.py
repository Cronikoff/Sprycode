"""Phase 139: Report-level spry summary metrics in managed pathway report."""

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


class TestPathwayReportSprySummary:
    def test_single_target_summary_fields_match_target(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let t = rep["targets"][0]
            let avg = rep["spryAverageScore"]
            let peak = rep["spryPeakScore"]
            let dist = rep["spryDistribution"]
        """)
        t = val(i, "t")
        assert abs(val(i, "avg") - t["spryScore"]) < 1e-9
        assert abs(val(i, "peak") - t["spryScore"]) < 1e-9
        dist = val(i, "dist")
        assert dist["brisk"] == 1
        assert dist["lively"] == 0
        assert dist["active"] == 0
        assert dist["vigorous"] == 0

    def test_summary_formula_with_single_target(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 0.2,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let t = rep["targets"][0]
            let avg = rep["spryAverageScore"]
            let peak = rep["spryPeakScore"]
        """)
        t = val(i, "t")
        expected = t["stateGainPerCycle"] * t["stateGainPerAttempt"]
        assert abs(val(i, "avg") - expected) < 1e-9
        assert abs(val(i, "peak") - expected) < 1e-9

    def test_no_managed_steps_has_zero_distribution_and_none_scores(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
            let avg = rep["spryAverageScore"]
            let peak = rep["spryPeakScore"]
            let dist = rep["spryDistribution"]
        """)
        assert val(i, "avg") is None
        assert val(i, "peak") is None
        dist = val(i, "dist")
        assert dist["lively"] == 0
        assert dist["active"] == 0
        assert dist["brisk"] == 0
        assert dist["vigorous"] == 0

