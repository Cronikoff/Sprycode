"""Phase 148: Report-level state-gain attribution residual per-cycle metric.

stateGainAttributionResidualPerCycle =
    stateGainAttributionResidual / cycles (when cycles > 0)
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


class TestPathwayReportStateGainAttributionResidualPerCycle:
    def test_single_target_has_zero_residual_per_cycle(self):
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
        assert abs(rep["stateGainAttributionResidualPerCycle"]) < 1e-9

    def test_two_target_residual_per_cycle_matches_formula(self):
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
        expected = rep["stateGainAttributionResidual"] / rep["cycles"]
        assert abs(rep["stateGainAttributionResidualPerCycle"] - expected) < 1e-9

    def test_no_managed_steps_returns_none_residual_per_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addStep("plain", fn(state) => state + 1)
            let rep = orch.runCapabilityPathwayManagedReport(0, 5)
        """)
        rep = val(i, "rep")
        assert rep["stateGainAttributionResidual"] == 0
        assert rep["stateGainAttributionResidualPerCycle"] is None

    def test_zero_report_gain_with_managed_target_has_zero_residual_per_cycle(self):
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
        assert rep["stateGainAttributionResidualPerCycle"] == 0.0

    def test_non_numeric_report_gain_has_none_residual_per_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            orch.addManagedStep(
                "svc",
                fn(state, cycle, name, attempt) => "steady",
                fn(state, cycle, name, attempt) => attempt >= (6 - cycle),
                10
            )
            let rep = orch.runCapabilityPathwayManagedReport("start", 10)
        """)
        rep = val(i, "rep")
        assert rep["reportStateGain"] is None
        assert rep["stateGainAttributionResidualPerCycle"] is None

    def test_zero_cycle_report_has_none_residual_per_cycle(self):
        i = run("""
            let orch = Orchestrator.new()
            let rep = orch.runCapabilityPathwayManagedReport(0, 0)
        """)
        rep = val(i, "rep")
        assert rep["cycles"] == 0
        assert rep["stateGainAttributionResidual"] == 0
        assert rep["stateGainAttributionResidualPerCycle"] is None
