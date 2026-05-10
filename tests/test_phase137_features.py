"""Phase 137: Per-target state-gain efficiency metrics in managed pathway report.

stateGain = stateAfter - stateBefore (how much state advanced during the target window)
stateGainPerCycle = stateGain / cycles
stateGainPerAttempt = stateGain / totalAttempts
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


class TestPathwayReportTargetStateGain:
    def test_single_target_state_gain(self):
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
        assert t["stateGain"] == 14
        assert abs(t["stateGainPerCycle"] - 3.5) < 1e-9
        assert abs(t["stateGainPerAttempt"] - 1.0) < 1e-9

    def test_state_gain_equals_state_after_minus_state_before(self):
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
        assert t["stateGain"] == t["stateAfter"] - t["stateBefore"]

    def test_state_gain_per_cycle_matches_formula(self):
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
        expected = t["stateGain"] / t["cycles"]
        assert abs(t["stateGainPerCycle"] - expected) < 1e-9

    def test_state_gain_per_attempt_matches_formula(self):
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
        expected = t["stateGain"] / t["totalAttempts"]
        assert abs(t["stateGainPerAttempt"] - expected) < 1e-9

    def test_two_service_target_state_gain(self):
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
        assert t["stateGain"] == 60
        assert abs(t["stateGainPerCycle"] - 60 / 11) < 1e-9
        assert abs(t["stateGainPerAttempt"] - 1.0) < 1e-9

    def test_state_gain_is_positive(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (5 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(0, 8)
            let t = rep["targets"][0]
        """)
        t = val(i, "t")
        assert t["stateGain"] > 0
        assert t["stateGainPerCycle"] > 0
        assert t["stateGainPerAttempt"] > 0

    def test_no_managed_steps_has_no_targets(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
            let targets = rep["targets"]
        """)
        assert val(i, "targets") == []
