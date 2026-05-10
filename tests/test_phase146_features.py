"""Phase 146: Report-level per-attribution state-gain per-attempt metrics.

targetStateGainPerAttempt = targetStateGainSum / total report attempts
preTargetStateGainPerAttempt = preTargetStateGain / total report attempts
"""

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


class TestPathwayReportGainPerAttemptAttribution:
    def test_single_target_gain_per_attempt_values(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
        """)
        rep = val(i, "rep")
        attempts = sum(t["totalAttempts"] for t in rep["targets"])
        assert attempts > 0
        assert abs(rep["targetStateGainPerAttempt"] - rep["targetStateGainSum"] / attempts) < 1e-9
        assert abs(rep["preTargetStateGainPerAttempt"] - rep["preTargetStateGain"] / attempts) < 1e-9

    def test_two_target_gain_per_attempt_values(self):
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
        """)
        rep = val(i, "rep")
        attempts = sum(t["totalAttempts"] for t in rep["targets"])
        assert abs(rep["targetStateGainPerAttempt"] - 60 / attempts) < 1e-9
        assert abs(rep["preTargetStateGainPerAttempt"] - 13 / attempts) < 1e-9

    def test_attribution_per_attempt_sums_to_report_per_attempt(self):
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
        """)
        rep = val(i, "rep")
        total = rep["targetStateGainPerAttempt"] + rep["preTargetStateGainPerAttempt"]
        assert abs(total - rep["reportStateGainPerAttempt"]) < 1e-9

    def test_formula_consistency_for_target_gain_per_attempt(self):
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
        """)
        rep = val(i, "rep")
        attempts = sum(t["totalAttempts"] for t in rep["targets"])
        expected = rep["targetStateGainSum"] / attempts
        assert abs(rep["targetStateGainPerAttempt"] - expected) < 1e-9

    def test_formula_consistency_for_pre_target_gain_per_attempt(self):
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
        """)
        rep = val(i, "rep")
        attempts = sum(t["totalAttempts"] for t in rep["targets"])
        expected = rep["preTargetStateGain"] / attempts
        assert abs(rep["preTargetStateGainPerAttempt"] - expected) < 1e-9

    def test_no_managed_steps_has_none_per_attempt_attributions(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
        """)
        rep = val(i, "rep")
        assert rep["targetStateGainPerAttempt"] is None
        assert rep["preTargetStateGainPerAttempt"] is None

    def test_zero_report_gain_has_zero_per_attempt_attributions(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 10)
        """)
        rep = val(i, "rep")
        assert rep["reportStateGain"] == 0
        assert rep["targetStateGainPerAttempt"] == 0.0
        assert rep["preTargetStateGainPerAttempt"] == 0.0
