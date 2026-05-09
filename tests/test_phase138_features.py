"""Phase 138: Spry semantics (`lively`/`active`/`brisk`/`vigorous`) in target report."""

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


class TestPathwayReportSprySemantics:
    def test_single_target_brisk_score(self):
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
        """)
        t = val(i, "t")
        assert abs(t["spryScore"] - 3.5) < 1e-9
        assert t["spryMeaning"] == "brisk"

    def test_two_service_target_is_vigorous(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svcA",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            orch.addManagedStep(
                "svcB",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (9 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 20)
            let t = rep["targets"][0]
        """)
        t = val(i, "t")
        assert t["name"] == "svcB"
        assert abs(t["spryScore"] - (60 / 11)) < 1e-9
        assert t["spryMeaning"] == "vigorous"

    def test_spry_score_formula(self):
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
        """)
        t = val(i, "t")
        expected = t["stateGainPerCycle"] * t["stateGainPerAttempt"]
        assert abs(t["spryScore"] - expected) < 1e-9

    def test_active_band(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 0.6,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
            let t = rep["targets"][0]
        """)
        t = val(i, "t")
        assert 1 <= t["spryScore"] < 3
        assert t["spryMeaning"] == "active"

    def test_lively_band(self):
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
        """)
        t = val(i, "t")
        assert 0 < t["spryScore"] < 1
        assert t["spryMeaning"] == "lively"

    def test_no_managed_steps_has_no_targets(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
            let targets = rep["targets"]
        """)
        assert val(i, "targets") == []
