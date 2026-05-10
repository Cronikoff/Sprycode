"""Phase 142: Report-level aggregate state metrics in managed pathway report.

reportStateGain      = final state − initial state (over the whole run)
reportStateGainPerCycle   = reportStateGain / total cycles in the report
reportStateGainPerAttempt = reportStateGain / total attempts across all targets
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


class TestPathwayReportAggregateState:
    def test_single_target_report_state_gain(self):
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
        # reportStateGain covers the full run (initial→final), including pre-target cycles
        assert rep["reportStateGain"] == rep["state"] - 0
        assert abs(rep["reportStateGainPerCycle"] - rep["reportStateGain"] / rep["cycles"]) < 1e-9

    def test_report_state_gain_equals_state_minus_initial(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => state + 1,
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport(5, 10)
        """)
        rep = val(i, "rep")
        assert rep["reportStateGain"] == rep["state"] - 5

    def test_report_state_gain_per_cycle_matches_formula(self):
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
        expected = rep["reportStateGain"] / rep["cycles"]
        assert abs(rep["reportStateGainPerCycle"] - expected) < 1e-9

    def test_report_state_gain_per_attempt_matches_formula(self):
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
        total_attempts = sum(t["totalAttempts"] for t in rep["targets"])
        expected = rep["reportStateGain"] / total_attempts
        assert abs(rep["reportStateGainPerAttempt"] - expected) < 1e-9

    def test_two_target_report_state_gain_covers_full_run(self):
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
        assert rep["reportStateGain"] == rep["state"] - 0
        assert rep["reportStateGainPerCycle"] == rep["reportStateGain"] / rep["cycles"]

    def test_report_state_gain_geq_target_state_gain_sum(self):
        # reportStateGain covers the whole run; target gains cover only target windows,
        # so the report gain is >= the sum of target gains.
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
        target_gain_sum = sum(t["stateGain"] for t in rep["targets"] if t["stateGain"] is not None)
        assert rep["reportStateGain"] >= target_gain_sum

    def test_no_managed_steps_has_zero_report_state_gain(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
        """)
        rep = val(i, "rep")
        # No managed targets → state stays at initial (0), gain is 0; no cycles → None per-cycle
        assert rep["reportStateGain"] == 0
        assert rep["reportStateGainPerCycle"] is None
        assert rep["reportStateGainPerAttempt"] is None
